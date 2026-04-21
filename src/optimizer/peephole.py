"""Peephole optimization on the linear IR.

Rules applied (iterated to a fixed point):

  1. Redundant JMP:
        JMP L           drop the JMP if the very next instruction is LABEL L.
        LABEL L     ->  LABEL L

  2. Branch flip (avoids an extra unconditional jump):
        JMP_IF     c L1            JMP_IF_NOT c L2
        JMP        L2          ->  LABEL      L1
        LABEL      L1
     (and the symmetric rule for JMP_IF_NOT, which becomes JMP_IF.)

  3. Unreachable code after a terminator:
        JMP / RET / EXIT
        ...           ->  drop everything until the next LABEL.
        LABEL L

  4. Self-comparison folding:
        EQ d x x   ->  CONST d bool 1
        LE d x x   ->  CONST d bool 1
        GE d x x   ->  CONST d bool 1
        NE d x x   ->  CONST d bool 0
        LT d x x   ->  CONST d bool 0
        GT d x x   ->  CONST d bool 0
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ir.ir import CONST, Instruction, IRFunction, IRProgram

_TRUE_SELF = {"EQ", "LE", "GE"}
_FALSE_SELF = {"NE", "LT", "GT"}
_SELF_OPS = _TRUE_SELF | _FALSE_SELF
_TERMINATORS = {"JMP", "RET", "EXIT"}
_FLIP = {"JMP_IF": "JMP_IF_NOT", "JMP_IF_NOT": "JMP_IF"}


def _self_compare_fold(ins: Instruction) -> Instruction | None:
    """If `ins` compares a temp/var to itself, return a CONST replacement."""
    if len(ins.args) != 3:
        return None
    _, l, r = ins.args
    if not (isinstance(l, str) and isinstance(r, str) and l == r):
        return None
    if ins.op in _TRUE_SELF:
        return CONST(ins.args[0], "bool", 1)
    if ins.op in _FALSE_SELF:
        return CONST(ins.args[0], "bool", 0)
    return None


def _peephole_once(insns: List[Instruction]) -> Tuple[List[Instruction], int]:
    """Run one peephole sweep; return (new_instructions, changes_made)."""
    out: List[Instruction] = []
    changes = 0
    i = 0
    n = len(insns)

    while i < n:
        ins = insns[i]

        # Self-comparison folding.
        if ins.op in _SELF_OPS:
            folded = _self_compare_fold(ins)
            if folded is not None:
                out.append(folded)
                changes += 1
                i += 1
                continue

        # Branch flip:
        #   JMP_IF c L1 ; JMP L2 ; LABEL L1
        # becomes
        #   JMP_IF_NOT c L2 ; LABEL L1
        if (
            ins.op in _FLIP
            and i + 2 < n
            and insns[i + 1].op == "JMP"
            and insns[i + 2].op == "LABEL"
            and len(ins.args) == 2
            and ins.args[1] == insns[i + 2].args[0]
        ):
            flip_op = _FLIP[ins.op]
            cond = ins.args[0]
            target = insns[i + 1].args[0]
            out.append(Instruction(flip_op, [cond, target]))
            out.append(insns[i + 2])
            changes += 1
            i += 3
            continue

        # Redundant JMP to the very next label.
        if (
            ins.op == "JMP"
            and i + 1 < n
            and insns[i + 1].op == "LABEL"
            and len(ins.args) == 1
            and ins.args[0] == insns[i + 1].args[0]
        ):
            changes += 1
            i += 1
            continue

        # Unreachable code after a terminator: skip until the next LABEL.
        if ins.op in _TERMINATORS:
            out.append(ins)
            j = i + 1
            while j < n and insns[j].op != "LABEL":
                j += 1
                changes += 1
            i = j
            continue

        out.append(ins)
        i += 1

    return out, changes


def _peephole_func(func: IRFunction) -> Tuple[IRFunction, int]:
    insns = list(func.instructions)
    total = 0
    while True:
        insns, n = _peephole_once(insns)
        total += n
        if n == 0:
            break
    return (
        IRFunction(
            func.name,
            func.return_type,
            func.param_names,
            func.param_types,
            insns,
        ),
        total,
    )


class PeepholeResult:
    def __init__(self, program: IRProgram, per: Dict[str, int]) -> None:
        self.program = program
        self.changes_per_function = per

    @property
    def total_changes(self) -> int:
        return sum(self.changes_per_function.values())

    def summary(self) -> str:
        lines = ["Peephole Optimization Pass:"]
        for fn, n in self.changes_per_function.items():
            lines.append(f"  {fn}: {n} peephole rewrite(s)")
        lines.append(f"  Total: {self.total_changes} rewrite(s)")
        return "\n".join(lines)


def peephole(program: IRProgram) -> PeepholeResult:
    funcs: List[IRFunction] = []
    per: Dict[str, int] = {}
    for fn in program.functions:
        nf, n = _peephole_func(fn)
        funcs.append(nf)
        per[fn.name] = n
    return PeepholeResult(IRProgram(funcs), per)
