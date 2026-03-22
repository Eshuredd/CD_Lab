"""
Constant Folding Optimization Pass (Week 7).

Walks the flat instruction list of each IR function and replaces operations
whose operands are all known compile-time constants with a single CONST
instruction.  Conditional jumps whose condition is a known constant are
either converted to an unconditional JMP (always taken) or dropped entirely
(never taken).

Folded operations
-----------------
  Arithmetic : ADD  SUB  MUL  DIV  MOD
  Unary      : NEG  NOT  INC  DEC
  Comparison : LT   LE   GT   GE   EQ   NE
  Logical    : AND  OR
  Branches   : JMP_IF  JMP_IF_NOT  (when condition is a constant)

Limitations (by design for this pass)
--------------------------------------
  - Only *forward* constant propagation within a single basic block.
    A STORE to a variable clears any knowledge of that variable from the
    map so later LOADs of that variable are not treated as constants.
  - Division by zero is left as-is rather than folded (runtime error).
  - Dead CONST instructions left behind are removed by the optional dead
    code elimination pass (Week 8).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ir.ir import CONST, Instruction, IRFunction, IRProgram


# ---------------------------------------------------------------------------
# Operator tables
# ---------------------------------------------------------------------------

_ARITH_OPS: Dict[str, Any] = {
    "ADD": lambda a, b: a + b,
    "SUB": lambda a, b: a - b,
    "MUL": lambda a, b: a * b,
    "DIV": None,   # handled specially (div-by-zero guard)
    "MOD": None,   # handled specially
}

_CMP_OPS: Dict[str, Any] = {
    "LT": lambda a, b: int(a < b),
    "LE": lambda a, b: int(a <= b),
    "GT": lambda a, b: int(a > b),
    "GE": lambda a, b: int(a >= b),
    "EQ": lambda a, b: int(a == b),
    "NE": lambda a, b: int(a != b),
}

_LOGIC_OPS: Dict[str, Any] = {
    "AND": lambda a, b: int(bool(a) and bool(b)),
    "OR":  lambda a, b: int(bool(a) or  bool(b)),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ConstMap = Dict[str, Tuple[str, Any]]   # temp -> (kind, value)


def _numeric_kind(ka: str, kb: str) -> str:
    """Promote int/uint32/float kinds: float wins, otherwise use left kind."""
    if ka == "float" or kb == "float":
        return "float"
    return ka


# ---------------------------------------------------------------------------
# Per-function pass
# ---------------------------------------------------------------------------

def _fold_function(func: IRFunction) -> Tuple[IRFunction, int]:
    """
    Return a new IRFunction with constants folded and a count of folds made.
    """
    const_map: ConstMap = {}
    new_insns: List[Instruction] = []
    folds = 0

    for insn in func.instructions:
        result = _fold_insn(insn, const_map)

        if result is None:
            # Instruction was eliminated (unreachable conditional branch).
            folds += 1
            continue

        if result is not insn:
            folds += 1

        new_insns.append(result)

        # Keep const_map up to date.
        if result.op == "CONST":
            dest = result.args[0]
            kind, val = result.args[1]
            const_map[dest] = (kind, val)
        elif result.op == "STORE":
            # A STORE to a named variable may change its value, so any
            # temp that was a LOAD of that variable is now stale.
            # We conservatively clear all entries that were loaded from
            # this variable (tracked indirectly: we simply don't add
            # variable-name entries to const_map so this is a no-op here,
            # but documented for clarity).
            pass

    new_func = IRFunction(
        name=func.name,
        return_type=func.return_type,
        param_names=func.param_names,
        param_types=func.param_types,
        instructions=new_insns,
    )
    return new_func, folds


def _fold_insn(insn: Instruction, const_map: ConstMap) -> Optional[Instruction]:
    op = insn.op

    # ------------------------------------------------------------------
    # Arithmetic: ADD SUB MUL DIV MOD
    # ------------------------------------------------------------------
    if op in ("ADD", "SUB", "MUL"):
        dest, left, right = insn.args
        if left in const_map and right in const_map:
            kl, vl = const_map[left]
            kr, vr = const_map[right]
            fn = _ARITH_OPS[op]
            rk = _numeric_kind(kl, kr)
            return CONST(dest, rk, fn(vl, vr))

    elif op == "DIV":
        dest, left, right = insn.args
        if left in const_map and right in const_map:
            kl, vl = const_map[left]
            kr, vr = const_map[right]
            if vr == 0:
                return insn  # leave division-by-zero for runtime
            rk = _numeric_kind(kl, kr)
            if rk == "float":
                result = vl / vr
            else:
                result = int(vl / vr)   # truncate toward zero (C semantics)
            return CONST(dest, rk, result)

    elif op == "MOD":
        dest, left, right = insn.args
        if left in const_map and right in const_map:
            kl, vl = const_map[left]
            _,  vr = const_map[right]
            if vr == 0:
                return insn
            return CONST(dest, kl, int(vl) % int(vr))

    # ------------------------------------------------------------------
    # Comparison: LT LE GT GE EQ NE
    # ------------------------------------------------------------------
    elif op in _CMP_OPS:
        dest, left, right = insn.args
        if left in const_map and right in const_map:
            _, vl = const_map[left]
            _, vr = const_map[right]
            return CONST(dest, "bool", _CMP_OPS[op](vl, vr))

    # ------------------------------------------------------------------
    # Logical: AND OR
    # ------------------------------------------------------------------
    elif op in _LOGIC_OPS:
        dest, left, right = insn.args
        if left in const_map and right in const_map:
            _, vl = const_map[left]
            _, vr = const_map[right]
            return CONST(dest, "bool", _LOGIC_OPS[op](vl, vr))

    # ------------------------------------------------------------------
    # Unary: NEG NOT INC DEC
    # ------------------------------------------------------------------
    elif op == "NEG":
        dest, src = insn.args
        if src in const_map:
            k, v = const_map[src]
            return CONST(dest, k, -v)

    elif op == "NOT":
        dest, src = insn.args
        if src in const_map:
            _, v = const_map[src]
            return CONST(dest, "bool", int(not bool(v)))

    elif op == "INC":
        dest, src = insn.args
        if src in const_map:
            k, v = const_map[src]
            return CONST(dest, k, v + 1)

    elif op == "DEC":
        dest, src = insn.args
        if src in const_map:
            k, v = const_map[src]
            return CONST(dest, k, v - 1)

    # ------------------------------------------------------------------
    # Conditional branches
    # ------------------------------------------------------------------
    elif op == "JMP_IF":
        cond, label = insn.args
        if cond in const_map:
            _, v = const_map[cond]
            if v:
                return Instruction("JMP", [label])   # always taken
            else:
                return None                          # never taken; drop

    elif op == "JMP_IF_NOT":
        cond, label = insn.args
        if cond in const_map:
            _, v = const_map[cond]
            if not v:
                return Instruction("JMP", [label])   # always taken
            else:
                return None                          # never taken; drop

    return insn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ConstantFoldingResult:
    """Wraps the optimized program together with simple statistics."""

    def __init__(self, program: IRProgram, folds_per_function: Dict[str, int]) -> None:
        self.program = program
        self.folds_per_function = folds_per_function

    @property
    def total_folds(self) -> int:
        return sum(self.folds_per_function.values())

    def summary(self) -> str:
        lines = ["Constant Folding Pass:"]
        for fname, n in self.folds_per_function.items():
            lines.append(f"  {fname}: {n} instruction(s) folded/eliminated")
        lines.append(f"  Total: {self.total_folds} fold(s)")
        return "\n".join(lines)


def constant_folding(program: IRProgram) -> ConstantFoldingResult:
    """
    Apply the constant folding pass to *program* and return a
    :class:`ConstantFoldingResult` containing the optimized program
    and per-function statistics.
    """
    new_functions: List[IRFunction] = []
    folds_per_function: Dict[str, int] = {}

    for func in program.functions:
        new_func, folds = _fold_function(func)
        new_functions.append(new_func)
        folds_per_function[func.name] = folds

    return ConstantFoldingResult(
        program=IRProgram(new_functions),
        folds_per_function=folds_per_function,
    )
