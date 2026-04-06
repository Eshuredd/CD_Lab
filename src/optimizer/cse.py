"""CSE within a block: reuse pure bin/unary results until a barrier (LABEL/JMP*/CALL/ENTRY/STORE_ARR)."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from ir.ir import IRFunction, IRProgram, Instruction

_COMM = {"ADD", "MUL", "EQ", "NE", "AND", "OR"}
_BIN = {
    "ADD", "SUB", "MUL", "DIV", "MOD", "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR",
}
_UN = {"NEG", "NOT", "INC", "DEC"}
_BARR = {"LABEL", "JMP", "JMP_IF", "JMP_IF_NOT", "FUNC_ENTRY", "CALL", "STORE_ARR"}


def _resolve(r: Dict[str, str], k: str) -> str:
    s: Set[str] = set()
    while k in r and k not in s:
        s.add(k)
        k = r[k]
    return k


def _apply(args: List[Any], r: Dict[str, str]) -> List[Any]:
    return [_resolve(r, a) if isinstance(a, str) and a.startswith("%") else a for a in args]


def _key(op: str, a1: Any, a2: Any) -> Tuple:
    if op in _COMM and isinstance(a1, str) and isinstance(a2, str) and a1 > a2:
        return (op, a2, a1)
    return (op, a1, a2)


def _cse_func(func: IRFunction):
    avail: Dict[Tuple, str] = {}
    red: Dict[str, str] = {}
    out: List[Instruction] = []
    elim = 0

    for ins in func.instructions:
        op = ins.op
        args = _apply(ins.args, red)
        ins = Instruction(op, args)

        if op in _BARR:
            avail.clear()
            out.append(ins)
            continue

        if op in _BIN and len(args) == 3:
            d, x, y = args[0], args[1], args[2]
            ek = _key(op, x, y)
            if ek in avail:
                red[d] = avail[ek]
                elim += 1
            else:
                avail[ek] = d
                out.append(ins)
        elif op in _UN and len(args) == 2:
            d, x = args[0], args[1]
            ek = (op, x)
            if ek in avail:
                red[d] = avail[ek]
                elim += 1
            else:
                avail[ek] = d
                out.append(ins)
        else:
            out.append(ins)

    return (
        IRFunction(func.name, func.return_type, func.param_names, func.param_types, out),
        elim,
    )


class CSEResult:
    def __init__(self, program: IRProgram, per: Dict[str, int]) -> None:
        self.program = program
        self.eliminated_per_function = per

    @property
    def total_eliminated(self) -> int:
        return sum(self.eliminated_per_function.values())

    def summary(self) -> str:
        lines = ["Common Subexpression Elimination (CSE) Pass:"]
        for fn, n in self.eliminated_per_function.items():
            lines.append(f"  {fn}: {n} redundant instruction(s) eliminated")
        lines.append(f"  Total: {self.total_eliminated} elimination(s)")
        return "\n".join(lines)


def cse(program: IRProgram) -> CSEResult:
    funcs, per = [], {}
    for fn in program.functions:
        nf, n = _cse_func(fn)
        funcs.append(nf)
        per[fn.name] = n
    return CSEResult(IRProgram(funcs), per)
