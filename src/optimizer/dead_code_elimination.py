"""
Dead Code Elimination (Week 8).

Removes *pure* instructions whose only effect is to define a temporary that
is never used by any remaining instruction.  Repeats until a fixed point so
that chains such as::

    CONST %0 ...
    CONST %1 ...
    ADD %2 %0 %1    # %2 unused → remove ADD
                    # → %0,%1 unused → remove CONSTs

are fully cleaned up after constant folding leaves redundant CONSTs.

Instructions with observable side effects are never removed: STORE, STORE_ARR,
ALLOC_ARRAY, PRINT, READ_INT, EXIT, RET, PARAM, CALL, FUNC_ENTRY, and all
control-flow ops (LABEL, JMP, JMP_IF, JMP_IF_NOT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from ir.ir import IRFunction, IRProgram, Instruction, is_temp


# Ops that must never be dropped (side effects or ABI / control flow).
_SIDE_EFFECT_OPS: Set[str] = {
    "FUNC_ENTRY",
    "STORE",
    "STORE_ARR",
    "ALLOC_ARRAY",  # allocation is observable for arrays
    "PRINT",
    "READ_INT",
    "EXIT",
    "RET",
    "PARAM",
    "CALL",
    "LABEL",
    "JMP",
    "JMP_IF",
    "JMP_IF_NOT",
}


def _def_temp(insn: Instruction) -> Optional[str]:
    """Temp defined by insn, or None if this op does not define a single temp."""
    op, args = insn.op, insn.args
    if op == "CONST":
        return args[0] if is_temp(args[0]) else None
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
        return args[0] if is_temp(args[0]) else None
    if op == "CALL" and args[0]:
        return args[0] if is_temp(args[0]) else None
    return None


def _uses_temps(insn: Instruction) -> Set[str]:
    """All temporaries read by this instruction."""
    op, args = insn.op, insn.args
    u: Set[str] = set()

    def add(x):
        if isinstance(x, str) and is_temp(x):
            u.add(x)

    if op == "CONST":
        pass
    elif op == "LOAD":
        add(args[1])
    elif op == "STORE":
        add(args[1])
    elif op == "LOAD_ARR":
        # LOAD_ARR dest array index
        add(args[2])
    elif op == "STORE_ARR":
        # STORE_ARR array index src
        add(args[1])
        add(args[2])
    elif op in (
        "ADD",
        "SUB",
        "MUL",
        "DIV",
        "MOD",
        "LT",
        "LE",
        "GT",
        "GE",
        "EQ",
        "NE",
        "AND",
        "OR",
    ):
        add(args[1])
        add(args[2])
    elif op in ("NEG", "NOT", "INC", "DEC"):
        add(args[1])
    elif op in ("JMP_IF", "JMP_IF_NOT"):
        add(args[0])
    elif op == "PARAM":
        add(args[0])
    elif op == "RET":
        if args[0]:
            add(args[0])
    elif op == "PRINT":
        for a in args:
            add(a)
    elif op == "EXIT":
        add(args[0])
    elif op == "CALL":
        pass
    # FUNC_ENTRY, LABEL, JMP, ALLOC_ARRAY: no temp uses here
    return u


def _is_removable_pure(insn: Instruction) -> bool:
    if insn.op in _SIDE_EFFECT_OPS:
        return False
    # READ_INT has side effect (input) — not pure for DCE
    if insn.op == "READ_INT":
        return False
    return _def_temp(insn) is not None


def _collect_used_temps(instructions: List[Instruction]) -> Set[str]:
    used: Set[str] = set()
    for insn in instructions:
        used |= _uses_temps(insn)
    return used


def _eliminate_once(instructions: List[Instruction]) -> tuple[List[Instruction], int]:
    used = _collect_used_temps(instructions)
    new_list: List[Instruction] = []
    removed = 0
    for insn in instructions:
        if _is_removable_pure(insn):
            d = _def_temp(insn)
            if d and d not in used:
                removed += 1
                continue
        new_list.append(insn)
    return new_list, removed


def _dce_function(func: IRFunction) -> tuple[IRFunction, int]:
    insns = list(func.instructions)
    total_removed = 0
    while True:
        insns, n = _eliminate_once(insns)
        total_removed += n
        if n == 0:
            break
    return (
        IRFunction(
            name=func.name,
            return_type=func.return_type,
            param_names=func.param_names,
            param_types=func.param_types,
            instructions=insns,
        ),
        total_removed,
    )


@dataclass
class DeadCodeEliminationResult:
    program: IRProgram
    removed_per_function: Dict[str, int] = field(default_factory=dict)

    @property
    def total_removed(self) -> int:
        return sum(self.removed_per_function.values())

    def summary(self) -> str:
        lines = ["Dead Code Elimination Pass:"]
        for fname, n in self.removed_per_function.items():
            lines.append(f"  {fname}: {n} pure instruction(s) removed")
        lines.append(f"  Total: {self.total_removed} instruction(s) removed")
        return "\n".join(lines)


def dead_code_elimination(program: IRProgram) -> DeadCodeEliminationResult:
    """
    Remove unused pure definitions.  Safe to run after constant folding.
    """
    new_funcs: List[IRFunction] = []
    per: Dict[str, int] = {}
    for func in program.functions:
        nf, n = _dce_function(func)
        new_funcs.append(nf)
        per[func.name] = n
    return DeadCodeEliminationResult(program=IRProgram(new_funcs), removed_per_function=per)
