"""Constant Propagation on the linear IR.

Tracks two kinds of compile-time constant facts within a basic block:

  * cm_temp : %tN -> (kind, value)   for temps known to be constants.
  * cm_var  : x   -> (kind, value)   for scalar variables whose most
                                     recent STORE was a known-constant temp.

With those facts the pass rewrites:

    LOAD %t x       ->  CONST %t (kind:value)        when x is known-constant.

That replacement also makes %t a known-constant temp, so subsequent
constant-folding / strength-reduction / DCE / CSE passes can continue to
simplify the surrounding code.

Both maps are cleared at the standard intra-block barriers used by the
other passes (LABEL, JMP*, CALL, FUNC_ENTRY): control flow could reach a
LABEL from any other path, and a CALL's effect on caller state is
treated conservatively here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ir.ir import CONST, Instruction, IRFunction, IRProgram

_BARR = {"LABEL", "JMP", "JMP_IF", "JMP_IF_NOT", "FUNC_ENTRY", "CALL"}

# Ops whose first arg is a freshly defined temp.
_DEFS_TEMP = {
    "CONST", "LOAD", "LOAD_ARR", "READ_INT",
    "ADD", "SUB", "MUL", "DIV", "MOD",
    "NEG", "INC", "DEC",
    "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR", "NOT",
}


def _cp_func(func: IRFunction) -> Tuple[IRFunction, int]:
    cm_temp: Dict[str, Tuple[str, Any]] = {}
    cm_var: Dict[str, Tuple[str, Any]] = {}
    out: List[Instruction] = []
    propagated = 0

    for ins in func.instructions:
        op, a = ins.op, ins.args

        if op in _BARR:
            cm_temp.clear()
            cm_var.clear()
            out.append(ins)
            continue

        if op == "CONST":
            kind, val = a[1]
            cm_temp[a[0]] = (kind, val)
            out.append(ins)
            continue

        if op == "STORE" and len(a) == 2:
            var, src = a[0], a[1]
            if isinstance(src, str) and src.startswith("%") and src in cm_temp:
                cm_var[var] = cm_temp[src]
            else:
                cm_var.pop(var, None)
            out.append(ins)
            continue

        if op == "LOAD" and len(a) == 2:
            dest, var = a[0], a[1]
            if var in cm_var:
                kind, val = cm_var[var]
                new_ins = CONST(dest, kind, val)
                cm_temp[dest] = (kind, val)
                out.append(new_ins)
                propagated += 1
                continue
            cm_temp.pop(dest, None)
            out.append(ins)
            continue

        # Any other defining op invalidates its destination temp's known value.
        if op in _DEFS_TEMP and a and isinstance(a[0], str) and a[0].startswith("%"):
            cm_temp.pop(a[0], None)

        # STORE_ARR / PARAM / PRINT / RET / EXIT / ALLOC_ARRAY do not change
        # the scalar-variable constant map.
        out.append(ins)

    return (
        IRFunction(
            func.name,
            func.return_type,
            func.param_names,
            func.param_types,
            out,
        ),
        propagated,
    )


class ConstantPropagationResult:
    def __init__(self, program: IRProgram, per: Dict[str, int]) -> None:
        self.program = program
        self.propagated_per_function = per

    @property
    def total_propagated(self) -> int:
        return sum(self.propagated_per_function.values())

    def summary(self) -> str:
        lines = ["Constant Propagation Pass:"]
        for fn, n in self.propagated_per_function.items():
            lines.append(f"  {fn}: {n} LOAD(s) replaced with CONST")
        lines.append(f"  Total: {self.total_propagated} propagation(s)")
        return "\n".join(lines)


def constant_propagation(program: IRProgram) -> ConstantPropagationResult:
    funcs: List[IRFunction] = []
    per: Dict[str, int] = {}
    for fn in program.functions:
        nf, n = _cp_func(fn)
        funcs.append(nf)
        per[fn.name] = n
    return ConstantPropagationResult(IRProgram(funcs), per)
