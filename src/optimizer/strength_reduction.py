"""
Strength reduction (Week 9) — replace expensive IR ops with cheaper equivalents.

Tracked forward from CONST definitions (same temp/value map idea as constant folding):

  * MUL by 0            → CONST 0
  * MUL by 1            → left unchanged (ADD with 0 via a fresh CONST 0 temp)
  * MUL by 2^k (int)    → chain of ADDs (doubling), cheaper than general MUL
  * MOD with modulus 1  → CONST 0 (integer remainder is always 0)

Float operands are left unchanged.  After this pass, run dead-code elimination
to clean up any redundant CONST 0 temps used only for x*1 / x/1 identities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ir.ir import (
    ADD,
    CONST,
    DIV,
    Instruction,
    IRFunction,
    IRProgram,
    MOD,
    is_temp,
)

ConstMap = Dict[str, Tuple[str, Any]]


def _is_int_kind(k: str) -> bool:
    return k in ("int", "uint32")


def _const_int_val(cm: ConstMap, name: str) -> Optional[int]:
    if name not in cm:
        return None
    k, v = cm[name]
    if not _is_int_kind(k):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _log2_int(n: int) -> int:
    """n must be a power of two >= 1."""
    return n.bit_length() - 1


def _invalidate_dest(cm: ConstMap, insn: Instruction) -> None:
    """Remove any temp that this instruction redefines from the constant map."""
    op = insn.op
    args = insn.args
    if op == "CONST":
        # About to replace const at dest — clear old binding first.
        cm.pop(args[0], None)
        return
    if op in (
        "LOAD",
        "LOAD_ARR",
        "READ_INT",
        "ADD",
        "SUB",
        "MUL",
        "DIV",
        "MOD",
        "NEG",
        "INC",
        "DEC",
        "LT",
        "LE",
        "GT",
        "GE",
        "EQ",
        "NE",
        "AND",
        "OR",
        "NOT",
    ):
        if args and isinstance(args[0], str) and is_temp(args[0]):
            cm.pop(args[0], None)
        return
    if op == "CALL" and args[0]:
        cm.pop(args[0], None)


def _fresh_temps(start: int, count: int) -> Tuple[List[str], int]:
    names = [f"%{start + i}" for i in range(count)]
    return names, start + count


def _mul_by_pow2_chain(
    dest: str,
    x: str,
    k: int,
    temp_start: int,
) -> Tuple[List[Instruction], int]:
    """
    dest = x * (2**k), k >= 1, using k ADDs that double an accumulator.
    """
    if k == 1:
        return [ADD(dest, x, x)], temp_start
    insns: List[Instruction] = []
    tnames, temp_start = _fresh_temps(temp_start, k - 1)
    insns.append(ADD(tnames[0], x, x))
    cur = tnames[0]
    for i in range(1, k - 1):
        insns.append(ADD(tnames[i], cur, cur))
        cur = tnames[i]
    insns.append(ADD(dest, cur, cur))
    return insns, temp_start


def _next_temp_id(func: IRFunction) -> int:
    m = 0
    for insn in func.instructions:
        for a in insn.args:
            if isinstance(a, str) and is_temp(a) and len(a) > 1 and a[1:].isdigit():
                m = max(m, int(a[1:]))
    return m + 1


def _transform_instruction(
    insn: Instruction,
    cm: ConstMap,
    temp_id: int,
) -> Tuple[List[Instruction], int, int]:
    """
    Returns (new instructions to emit, replacements_count, new_temp_id).
    """
    op = insn.op
    if op != "MUL" and op != "MOD" and op != "DIV":
        return [insn], 0, temp_id

    args = insn.args
    dest, left, right = args[0], args[1], args[2]
    replacements = 0

    if op == "MUL":
        li = _const_int_val(cm, left)
        ri = _const_int_val(cm, right)

        # 0 * x  or  x * 0
        if li == 0 or ri == 0:
            return [CONST(dest, "int", 0)], 1, temp_id

        # x * 1  or  1 * x  →  x + 0  (ADD is cheaper than MUL on many targets)
        if li == 1:
            z = f"%{temp_id}"
            temp_id += 1
            return [CONST(z, "int", 0), ADD(dest, right, z)], 1, temp_id
        if ri == 1:
            z = f"%{temp_id}"
            temp_id += 1
            return [CONST(z, "int", 0), ADD(dest, left, z)], 1, temp_id

        # x * 2^k  → doubling ADD chain (prefer constant on the right)
        if ri is not None and ri > 0 and _is_power_of_two(ri):
            k = _log2_int(ri)
            insns, temp_id = _mul_by_pow2_chain(dest, left, k, temp_id)
            return insns, 1, temp_id
        if li is not None and li > 0 and _is_power_of_two(li):
            k = _log2_int(li)
            insns, temp_id = _mul_by_pow2_chain(dest, right, k, temp_id)
            return insns, 1, temp_id

    if op == "DIV":
        # Integer division by 1: n / 1 → n + 0
        ri = _const_int_val(cm, right)
        if ri == 1:
            z = f"%{temp_id}"
            temp_id += 1
            return [CONST(z, "int", 0), ADD(dest, left, z)], 1, temp_id

    if op == "MOD":
        ri = _const_int_val(cm, right)
        if ri == 1:
            return [CONST(dest, "int", 0)], 1, temp_id

    return [insn], 0, temp_id


def _apply_const_to_map(cm: ConstMap, insn: Instruction) -> None:
    """Record a CONST instruction in the constant map."""
    dest = insn.args[0]
    cm.pop(dest, None)
    cm[dest] = (insn.args[1][0], insn.args[1][1])


def _strength_function(func: IRFunction) -> Tuple[IRFunction, int]:
    cm: ConstMap = {}
    temp_id = _next_temp_id(func)
    new_insns: List[Instruction] = []
    total_replacements = 0

    for insn in func.instructions:
        if insn.op == "CONST":
            _apply_const_to_map(cm, insn)
            new_insns.append(insn)
            continue

        if insn.op in ("MUL", "MOD", "DIV"):
            outs, nrep, temp_id = _transform_instruction(insn, cm, temp_id)
            total_replacements += nrep
            for out in outs:
                if out.op == "CONST":
                    _apply_const_to_map(cm, out)
                else:
                    _invalidate_dest(cm, out)
                new_insns.append(out)
            continue

        _invalidate_dest(cm, insn)
        new_insns.append(insn)

    return (
        IRFunction(
            name=func.name,
            return_type=func.return_type,
            param_names=func.param_names,
            param_types=func.param_types,
            instructions=new_insns,
        ),
        total_replacements,
    )


def strength_reduction(program: IRProgram) -> "StrengthReductionResult":
    """
    Apply strength reduction to every function.  Run after constant folding so
    CONST operands are easy to spot in the constant map.
    """
    funcs: List[IRFunction] = []
    per: Dict[str, int] = {}
    for func in program.functions:
        nf, n = _strength_function(func)
        funcs.append(nf)
        per[func.name] = n
    return StrengthReductionResult(program=IRProgram(funcs), replacements_per_function=per)


@dataclass
class StrengthReductionResult:
    program: IRProgram
    replacements_per_function: Dict[str, int] = field(default_factory=dict)

    @property
    def total_replacements(self) -> int:
        return sum(self.replacements_per_function.values())

    def summary(self) -> str:
        lines = ["Strength reduction pass:"]
        for fname, n in self.replacements_per_function.items():
            lines.append(f"  {fname}: {n} instruction sequence(s) simplified")
        lines.append(f"  Total: {self.total_replacements} replacement(s)")
        return "\n".join(lines)
