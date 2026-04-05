"""RISC-V RV64 GAS (Linux). Frame: ra/s0 at top; locals at s0-16-8*k. a0–a7 args; a0 ret."""

from __future__ import annotations
from typing import Dict, List

from ir.ir import IRFunction, IRProgram

_AREG = ("a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7")
_BINOP = {"ADD": "add", "SUB": "sub", "MUL": "mul", "DIV": "div", "MOD": "rem"}
_CMP = {
    "LT": ["slt   t0, t0, t1"],
    "GT": ["slt   t0, t1, t0"],
    "LE": ["slt   t0, t1, t0", "xori  t0, t0, 1"],
    "GE": ["slt   t0, t0, t1", "xori  t0, t0, 1"],
    "EQ": ["xor   t0, t0, t1", "sltiu t0, t0, 1"],
    "NE": ["xor   t0, t0, t1", "sltu  t0, zero, t0"],
}
_DEF = frozenset({
    "CONST", "LOAD", "LOAD_ARR", "READ_INT", "ADD", "SUB", "MUL", "DIV", "MOD",
    "NEG", "INC", "DEC", "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR", "NOT",
})


class RiscVBackend:
    def __init__(self, prog: IRProgram):
        self.prog = prog
        self.out: List[str] = []
        self.strs: Dict[str, str] = {}
        self.scnt = 0
        self.fn = ""

    def _intern(self, val: str) -> str:
        if val not in self.strs:
            self.strs[val] = f"_str{self.scnt}"
            self.scnt += 1
        return self.strs[val]

    def e(self, s: str = "") -> None:
        self.out.append(s)

    def i(self, s: str) -> None:
        self.out.append("    " + s)

    def lbl(self, name: str) -> str:
        return f".L{self.fn}_{name}"

    def _build_frame(self, func: IRFunction):
        slots, arrs, cur = {}, {}, 0

        def alloc(name: str, n: int = 1) -> None:
            nonlocal cur
            if name not in slots:
                cur += n * 8
                slots[name] = cur

        for p in func.param_names:
            alloc(p)
        for ins in func.instructions:
            op, a = ins.op, ins.args
            if op == "ALLOC_ARRAY":
                arrs[a[0]] = cur + 8
                alloc(a[0], int(a[1]))
            elif op in _DEF:
                alloc(a[0])
            elif op == "STORE":
                alloc(a[0])
            elif op == "CALL" and a[0]:
                alloc(a[0])
        fsize = (cur + 16 + 15) & ~15
        return slots, arrs, fsize

    def ref(self, slots: Dict[str, int], name: str) -> str:
        return f"-{slots[name] + 16}(s0)"

    def generate(self) -> str:
        for fn in self.prog.functions:
            for ins in fn.instructions:
                if ins.op == "CONST" and isinstance(ins.args[1], tuple) and ins.args[1][0] == "string":
                    self._intern(ins.args[1][1])

        self.e()
        self.e("    .section .data")
        self.e('_fmt_int:  .string "%ld\\n"')
        self.e('_fmt_uint: .string "%lu\\n"')
        self.e('_fmt_char: .string "%c\\n"')
        self.e('_fmt_str:  .string "%s\\n"')
        self.e('_fmt_scan: .string "%ld"')
        for val, lbl in self.strs.items():
            self.e(f'{lbl}: .string "{val.replace(chr(34), chr(92)+chr(34))}"')
        self.e()
        self.e("    .section .text")
        if any(f.name == "main" for f in self.prog.functions):
            self.e("    .global main")
        self.e()
        for fn in self.prog.functions:
            self._gen_func(fn)
        return "\n".join(self.out)

    def _gen_func(self, func: IRFunction) -> None:
        slots, arrs, N = self._build_frame(func)
        self.fn = func.name
        r = lambda name: self.ref(slots, name)

        self.e(f"{func.name}:")
        self.i(f"addi  sp, sp, -{N}")
        self.i(f"sd    ra, {N-8}(sp)")
        self.i(f"sd    s0, {N-16}(sp)")
        self.i(f"addi  s0, sp, {N}")
        self.e()

        for idx, p in enumerate(func.param_names):
            if idx < 8:
                self.i(f"sd    {_AREG[idx]}, {r(p)}")
            else:
                self.i(f"ld    t0, {8 + (idx-8)*8}(s0)")
                self.i(f"sd    t0, {r(p)}")

        kinds: Dict[str, str] = {p: "int" for p in func.param_names}
        pend: List[str] = []

        for ins in func.instructions:
            op, a = ins.op, ins.args

            if op == "FUNC_ENTRY":
                pass
            elif op == "LABEL":
                self.e(f"{self.lbl(a[0])}:")
            elif op == "JMP":
                self.i(f"j     {self.lbl(a[0])}")
            elif op == "JMP_IF":
                self.i(f"ld    t0, {r(a[0])}")
                self.i(f"bnez  t0, {self.lbl(a[1])}")
            elif op == "JMP_IF_NOT":
                self.i(f"ld    t0, {r(a[0])}")
                self.i(f"beqz  t0, {self.lbl(a[1])}")

            elif op == "CONST":
                dest, (kind, val) = a[0], a[1]
                kinds[dest] = kind
                if kind in ("int", "uint32", "bool"):
                    self.i(f"li    t0, {int(val)}")
                    self.i(f"sd    t0, {r(dest)}")
                elif kind == "char":
                    self.i(f"li    t0, {int(val) if isinstance(val, int) else ord(val)}")
                    self.i(f"sd    t0, {r(dest)}")
                elif kind == "float":
                    self.i("# float -> 0")
                    self.i(f"sd    zero, {r(dest)}")
                elif kind == "string":
                    self.i(f"la    t0, {self._intern(val)}")
                    self.i(f"sd    t0, {r(dest)}")

            elif op == "LOAD":
                kinds[a[0]] = kinds.get(a[1], "int")
                self.i(f"ld    t0, {r(a[1])}")
                self.i(f"sd    t0, {r(a[0])}")
            elif op == "STORE":
                kinds[a[0]] = kinds.get(a[1], "int")
                self.i(f"ld    t0, {r(a[1])}")
                self.i(f"sd    t0, {r(a[0])}")
            elif op == "ALLOC_ARRAY":
                pass
            elif op == "LOAD_ARR":
                dest, arr, idx = a
                self.i(f"ld    t1, {r(idx)}")
                self.i("slli  t1, t1, 3")
                self.i(f"addi  t0, s0, -{arrs[arr]+16}")
                self.i("sub   t0, t0, t1")
                self.i("ld    t0, 0(t0)")
                self.i(f"sd    t0, {r(dest)}")
            elif op == "STORE_ARR":
                arr, idx, src = a
                self.i(f"ld    t1, {r(idx)}")
                self.i("slli  t1, t1, 3")
                self.i(f"addi  t0, s0, -{arrs[arr]+16}")
                self.i("sub   t0, t0, t1")
                self.i(f"ld    t2, {r(src)}")
                self.i("sd    t2, 0(t0)")

            elif op in _BINOP:
                dest, l, rv = a
                kinds[dest] = kinds.get(l, "int")
                self.i(f"ld    t0, {r(l)}")
                self.i(f"ld    t1, {r(rv)}")
                self.i(f"{_BINOP[op]:<5} t0, t0, t1")
                self.i(f"sd    t0, {r(dest)}")
            elif op == "NEG":
                kinds[a[0]] = kinds.get(a[1], "int")
                self.i(f"ld    t0, {r(a[1])}")
                self.i("neg   t0, t0")
                self.i(f"sd    t0, {r(a[0])}")
            elif op == "INC":
                kinds[a[0]] = kinds.get(a[1], "int")
                self.i(f"ld    t0, {r(a[1])}")
                self.i("addi  t0, t0, 1")
                self.i(f"sd    t0, {r(a[0])}")
            elif op == "DEC":
                kinds[a[0]] = kinds.get(a[1], "int")
                self.i(f"ld    t0, {r(a[1])}")
                self.i("addi  t0, t0, -1")
                self.i(f"sd    t0, {r(a[0])}")

            elif op in _CMP:
                dest, l, rv = a
                kinds[dest] = "bool"
                self.i(f"ld    t0, {r(l)}")
                self.i(f"ld    t1, {r(rv)}")
                for line in _CMP[op]:
                    self.i(line)
                self.i(f"sd    t0, {r(dest)}")
            elif op == "AND":
                dest, l, rv = a
                kinds[dest] = "bool"
                self.i(f"ld    t0, {r(l)}")
                self.i("sltu  t0, zero, t0")
                self.i(f"ld    t1, {r(rv)}")
                self.i("sltu  t1, zero, t1")
                self.i("and   t0, t0, t1")
                self.i(f"sd    t0, {r(dest)}")
            elif op == "OR":
                dest, l, rv = a
                kinds[dest] = "bool"
                self.i(f"ld    t0, {r(l)}")
                self.i("sltu  t0, zero, t0")
                self.i(f"ld    t1, {r(rv)}")
                self.i("sltu  t1, zero, t1")
                self.i("or    t0, t0, t1")
                self.i(f"sd    t0, {r(dest)}")
            elif op == "NOT":
                kinds[a[0]] = "bool"
                self.i(f"ld    t0, {r(a[1])}")
                self.i("sltiu t0, t0, 1")
                self.i(f"sd    t0, {r(a[0])}")

            elif op == "PRINT":
                fmts = {"string": "_fmt_str", "char": "_fmt_char", "uint32": "_fmt_uint"}
                for arg in a:
                    self.i(f"la    a0, {fmts.get(kinds.get(arg, 'int'), '_fmt_int')}")
                    self.i(f"ld    a1, {r(arg)}")
                    self.i("call  printf")
            elif op == "READ_INT":
                kinds[a[0]] = "int"
                self.i("la    a0, _fmt_scan")
                self.i(f"addi  a1, s0, -{slots[a[0]]+16}")
                self.i("call  scanf")
            elif op == "EXIT":
                self.i(f"ld    a0, {r(a[0])}")
                self.i("call  exit")
            elif op == "PARAM":
                pend.append(a[0])
            elif op == "CALL":
                dest_r = a[0] if a[0] else None
                extra = max(0, len(pend) - 8)
                eb = ((extra + 1) & ~1) * 8 if extra else 0
                if eb:
                    self.i(f"addi  sp, sp, -{eb}")
                    for j, p in enumerate(pend[8:]):
                        self.i(f"ld    t0, {r(p)}")
                        self.i(f"sd    t0, {j*8}(sp)")
                for j, p in enumerate(pend[:8]):
                    self.i(f"ld    {_AREG[j]}, {r(p)}")
                self.i(f"call  {a[1]}")
                if eb:
                    self.i(f"addi  sp, sp, {eb}")
                if dest_r:
                    kinds[dest_r] = "int"
                    self.i(f"sd    a0, {r(dest_r)}")
                pend.clear()
            elif op == "RET":
                if a[0]:
                    self.i(f"ld    a0, {r(a[0])}")
                else:
                    self.i("li    a0, 0")
                self.i(f"ld    ra, {N-8}(sp)")
                self.i(f"ld    s0, {N-16}(sp)")
                self.i(f"addi  sp, sp, {N}")
                self.i("ret")

        self.e()
