"""Dead Code Elimination (Week 8) — removes unused pure definitions.

Iterates until fixed point so that chains like:
    CONST %0 ... ; CONST %1 ... ; ADD %2 %0 %1   (all unused)
are fully cleaned up in multiple passes.
"""

from __future__ import annotations
from typing import Dict, List, Set
from ir.ir import IRFunction, IRProgram, Instruction

# Ops that can be removed if their result temp is never read
_PURE = {
    "CONST","LOAD","LOAD_ARR",
    "ADD","SUB","MUL","DIV","MOD",
    "NEG","INC","DEC",
    "LT","LE","GT","GE","EQ","NE","AND","OR","NOT",
}


def _used_temps(insns: List[Instruction]) -> Set[str]:
    """Collect every temp that appears as a *use* (not a define) in the list."""
    used: Set[str] = set()
    for ins in insns:
        # For pure ops the first arg is the destination; everything else is a use.
        # For all other ops every temp arg is a use.
        args = ins.args[1:] if ins.op in _PURE else ins.args
        for a in args:
            if isinstance(a, str) and a.startswith("%"):
                used.add(a)
    return used


def _dce_once(insns: List[Instruction]):
    used = _used_temps(insns)
    out, removed = [], 0
    for ins in insns:
        # Only pure ops with a temp dest can be dropped
        if ins.op in _PURE:
            dest = ins.args[0]
            if isinstance(dest, str) and dest.startswith("%") and dest not in used:
                removed += 1
                continue
        out.append(ins)
    return out, removed


def _dce_func(func: IRFunction):
    insns = list(func.instructions)
    total = 0
    while True:
        insns, n = _dce_once(insns)
        total += n
        if n == 0:
            break
    return IRFunction(func.name, func.return_type, func.param_names, func.param_types, insns), total


class DeadCodeEliminationResult:
    def __init__(self, program, per):
        self.program = program
        self.removed_per_function = per

    @property
    def total_removed(self):
        return sum(self.removed_per_function.values())

    def summary(self):
        lines = ["Dead Code Elimination Pass:"]
        for fn, n in self.removed_per_function.items():
            lines.append(f"  {fn}: {n} pure instruction(s) removed")
        lines.append(f"  Total: {self.total_removed} instruction(s) removed")
        return "\n".join(lines)


def dead_code_elimination(program: IRProgram) -> DeadCodeEliminationResult:
    funcs, per = [], {}
    for fn in program.functions:
        nf, n = _dce_func(fn)
        funcs.append(nf);  per[fn.name] = n
    return DeadCodeEliminationResult(IRProgram(funcs), per)
