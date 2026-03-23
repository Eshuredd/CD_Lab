"""Strength Reduction (Week 9) — replace expensive ops with cheaper equivalents.

Rules applied (integers only; floats are left alone):
  MUL x, 0      → CONST 0
  MUL x, 1      → ADD x, CONST(0)      (cheaper than MUL on most targets)
  MUL x, 2^k    → k doubling ADDs
  DIV x, 1      → ADD x, CONST(0)
  MOD x, 1      → CONST 0

Run dead-code elimination afterwards to clean up the spare CONST(0) temps.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple
from ir.ir import ADD, CONST, Instruction, IRFunction, IRProgram, is_temp


def _int_val(cm: Dict, name: str):
    """Return the integer value of name if it's a known int constant, else None."""
    if name not in cm:
        return None
    k, v = cm[name]
    if k not in ("int","uint32"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _pow2_add_chain(dest: str, x: str, k: int, tid: int) -> Tuple[List[Instruction], int]:
    """Emit k doublings: dest = x * 2^k using only ADDs."""
    if k == 1:
        return [ADD(dest, x, x)], tid
    tmps = [f"%{tid+i}" for i in range(k-1)];  tid += k-1
    chain = [ADD(tmps[0], x, x)]
    for i in range(1, k-1):
        chain.append(ADD(tmps[i], tmps[i-1], tmps[i-1]))
    chain.append(ADD(dest, tmps[-1], tmps[-1]))
    return chain, tid


def _next_tid(func: IRFunction) -> int:
    m = 0
    for ins in func.instructions:
        for a in ins.args:
            if isinstance(a,str) and is_temp(a) and a[1:].isdigit():
                m = max(m, int(a[1:]))
    return m + 1


def _sr_func(func: IRFunction):
    cm: Dict[str, Any] = {}   # temp -> (kind, val) for known CONST temps
    out: List[Instruction] = []
    tid = _next_tid(func)
    reps = 0

    def invalidate(ins: Instruction):
        """Remove any temp that this instruction redefines from cm."""
        a = ins.args
        if ins.op == "CONST":
            cm.pop(a[0], None)
        elif ins.op in ("LOAD","LOAD_ARR","READ_INT","ADD","SUB","MUL","DIV","MOD",
                        "NEG","INC","DEC","LT","LE","GT","GE","EQ","NE","AND","OR","NOT"):
            if a and isinstance(a[0], str) and is_temp(a[0]):
                cm.pop(a[0], None)
        elif ins.op == "CALL" and a[0]:
            cm.pop(a[0], None)

    for ins in func.instructions:
        op, a = ins.op, ins.args

        if op == "CONST":
            cm.pop(a[0], None)
            cm[a[0]] = (a[1][0], a[1][1])
            out.append(ins);  continue

        if op in ("MUL","DIV","MOD"):
            dest, l, r = a[0], a[1], a[2]
            li, ri = _int_val(cm, l), _int_val(cm, r)
            replaced = []

            if op == "MUL":
                if li == 0 or ri == 0:
                    replaced = [CONST(dest, "int", 0)]
                elif li == 1:
                    z = f"%{tid}";  tid += 1
                    replaced = [CONST(z,"int",0), ADD(dest, r, z)]
                elif ri == 1:
                    z = f"%{tid}";  tid += 1
                    replaced = [CONST(z,"int",0), ADD(dest, l, z)]
                elif ri is not None and ri > 0 and (ri & (ri-1)) == 0:
                    replaced, tid = _pow2_add_chain(dest, l, ri.bit_length()-1, tid)
                elif li is not None and li > 0 and (li & (li-1)) == 0:
                    replaced, tid = _pow2_add_chain(dest, r, li.bit_length()-1, tid)

            elif op == "DIV" and ri == 1:
                z = f"%{tid}";  tid += 1
                replaced = [CONST(z,"int",0), ADD(dest, l, z)]

            elif op == "MOD" and ri == 1:
                replaced = [CONST(dest, "int", 0)]

            if replaced:
                reps += 1
                for new in replaced:
                    if new.op == "CONST":
                        cm.pop(new.args[0], None)
                        cm[new.args[0]] = (new.args[1][0], new.args[1][1])
                    else:
                        invalidate(new)
                    out.append(new)
                continue

        invalidate(ins)
        out.append(ins)

    return IRFunction(func.name, func.return_type, func.param_names, func.param_types, out), reps


class StrengthReductionResult:
    def __init__(self, program, per):
        self.program = program
        self.replacements_per_function = per

    @property
    def total_replacements(self):
        return sum(self.replacements_per_function.values())

    def summary(self):
        lines = ["Strength reduction pass:"]
        for fn, n in self.replacements_per_function.items():
            lines.append(f"  {fn}: {n} instruction sequence(s) simplified")
        lines.append(f"  Total: {self.total_replacements} replacement(s)")
        return "\n".join(lines)


def strength_reduction(program: IRProgram) -> StrengthReductionResult:
    funcs, per = [], {}
    for fn in program.functions:
        nf, n = _sr_func(fn)
        funcs.append(nf);  per[fn.name] = n
    return StrengthReductionResult(IRProgram(funcs), per)
