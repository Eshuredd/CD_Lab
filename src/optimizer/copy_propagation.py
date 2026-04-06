"""Copy propagation: drop redundant LOAD after STORE when no barrier (LABEL/JMP*/CALL/ENTRY)."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from ir.ir import IRFunction, IRProgram, Instruction

_BARR = {"LABEL", "JMP", "JMP_IF", "JMP_IF_NOT", "FUNC_ENTRY", "CALL"}


def _resolve(r: Dict[str, str], k: str) -> str:
    s: Set[str] = set()
    while k in r and k not in s:
        s.add(k)
        k = r[k]
    return k


def _apply(args: List[Any], r: Dict[str, str]) -> List[Any]:
    return [_resolve(r, a) if isinstance(a, str) and a.startswith("%") else a for a in args]


def _cp_func(func: IRFunction):
    v2t: Dict[str, str] = {}
    red: Dict[str, str] = {}
    out: List[Instruction] = []
    elim = 0

    for ins in func.instructions:
        op = ins.op
        args = _apply(ins.args, red)
        ins = Instruction(op, args)

        if op in _BARR:
            v2t.clear()
            out.append(ins)
            continue

        if op == "STORE" and len(args) == 2:
            vn, src = args[0], args[1]
            if isinstance(src, str) and src.startswith("%"):
                v2t[vn] = _resolve(red, src)
            else:
                v2t.pop(vn, None)
            out.append(ins)
        elif op == "LOAD" and len(args) == 2:
            dest, vn = args[0], args[1]
            if isinstance(vn, str) and vn in v2t:
                red[dest] = v2t[vn]
                elim += 1
            else:
                out.append(ins)
        else:
            out.append(ins)

    return (
        IRFunction(func.name, func.return_type, func.param_names, func.param_types, out),
        elim,
    )


class CopyPropagationResult:
    def __init__(self, program: IRProgram, per: Dict[str, int]) -> None:
        self.program = program
        self.eliminated_per_function = per

    @property
    def total_eliminated(self) -> int:
        return sum(self.eliminated_per_function.values())

    def summary(self) -> str:
        lines = ["Copy Propagation Pass:"]
        for fn, n in self.eliminated_per_function.items():
            lines.append(f"  {fn}: {n} redundant LOAD(s) eliminated")
        lines.append(f"  Total: {self.total_eliminated} elimination(s)")
        return "\n".join(lines)


def copy_propagation(program: IRProgram) -> CopyPropagationResult:
    funcs, per = [], {}
    for fn in program.functions:
        nf, n = _cp_func(fn)
        funcs.append(nf)
        per[fn.name] = n
    return CopyPropagationResult(IRProgram(funcs), per)
