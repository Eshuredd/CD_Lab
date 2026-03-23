"""Constant Folding (Week 7) — evaluates operations on known constants at compile time."""

from __future__ import annotations
from typing import Any, Dict, List
from ir.ir import CONST, Instruction, IRFunction, IRProgram

# Binary ops we can fold directly
_FOLD: Dict[str, Any] = {
    "ADD": lambda a,b: a+b,   "SUB": lambda a,b: a-b,   "MUL": lambda a,b: a*b,
    "LT":  lambda a,b: int(a<b),  "LE":  lambda a,b: int(a<=b),
    "GT":  lambda a,b: int(a>b),  "GE":  lambda a,b: int(a>=b),
    "EQ":  lambda a,b: int(a==b), "NE":  lambda a,b: int(a!=b),
    "AND": lambda a,b: int(bool(a) and bool(b)),
    "OR":  lambda a,b: int(bool(a) or  bool(b)),
}
_BOOL_OPS = {"LT","LE","GT","GE","EQ","NE","AND","OR"}

def _kind(ka, kb):
    return "float" if (ka=="float" or kb=="float") else ka


def _fold_func(func: IRFunction):
    cm = {}   # temp -> (kind, val)  — known constants at this point
    out: List[Instruction] = []
    folds = 0

    for ins in func.instructions:
        op, a = ins.op, ins.args
        new = ins   # default: keep unchanged

        if op in _FOLD and a[1] in cm and a[2] in cm:
            kl, vl = cm[a[1]];  kr, vr = cm[a[2]]
            rk = "bool" if op in _BOOL_OPS else _kind(kl, kr)
            new = CONST(a[0], rk, _FOLD[op](vl, vr));  folds += 1

        elif op == "DIV" and a[1] in cm and a[2] in cm:
            kl, vl = cm[a[1]];  vr = cm[a[2]][1]
            if vr != 0:
                rk = _kind(kl, cm[a[2]][0])
                v  = vl/vr if rk=="float" else int(vl/vr)
                new = CONST(a[0], rk, v);  folds += 1

        elif op == "MOD" and a[1] in cm and a[2] in cm:
            vl, vr = cm[a[1]][1], cm[a[2]][1]
            if vr != 0:
                new = CONST(a[0], cm[a[1]][0], int(vl) % int(vr));  folds += 1

        elif op == "NEG" and a[1] in cm:
            k, v = cm[a[1]];  new = CONST(a[0], k, -v);  folds += 1

        elif op == "NOT" and a[1] in cm:
            new = CONST(a[0], "bool", int(not bool(cm[a[1]][1])));  folds += 1

        elif op == "INC" and a[1] in cm:
            k, v = cm[a[1]];  new = CONST(a[0], k, v+1);  folds += 1

        elif op == "DEC" and a[1] in cm:
            k, v = cm[a[1]];  new = CONST(a[0], k, v-1);  folds += 1

        elif op == "JMP_IF" and a[0] in cm:
            _, v = cm[a[0]]
            new = Instruction("JMP", [a[1]]) if v else None
            folds += 1

        elif op == "JMP_IF_NOT" and a[0] in cm:
            _, v = cm[a[0]]
            new = Instruction("JMP", [a[1]]) if not v else None
            folds += 1

        if new is not None:
            out.append(new)
            if new.op == "CONST":
                cm[new.args[0]] = new.args[1]   # (kind, val)

    return IRFunction(func.name, func.return_type, func.param_names, func.param_types, out), folds


class ConstantFoldingResult:
    def __init__(self, program, per):
        self.program = program
        self.folds_per_function = per

    @property
    def total_folds(self):
        return sum(self.folds_per_function.values())

    def summary(self):
        lines = ["Constant Folding Pass:"]
        for fn, n in self.folds_per_function.items():
            lines.append(f"  {fn}: {n} instruction(s) folded/eliminated")
        lines.append(f"  Total: {self.total_folds} fold(s)")
        return "\n".join(lines)


def constant_folding(program: IRProgram) -> ConstantFoldingResult:
    funcs, per = [], {}
    for fn in program.functions:
        nf, n = _fold_func(fn)
        funcs.append(nf);  per[fn.name] = n
    return ConstantFoldingResult(IRProgram(funcs), per)
