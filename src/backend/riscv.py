"""RISC-V RV32 backend for the Ripes simulator (ripes.me).

Uses ``sw``/``lw``, 4-byte stack slots, and RARS-style ``ecall`` I/O (no libc):
a7=1 print int, a7=4 print string, a7=5 read int, a7=10 exit, a7=11 print char,
a7=93 exit with status. Entry is ``_start`` → ``call main`` → ``ecall`` exit.
"""

from __future__ import annotations
from typing import Dict, List

from ir.ir import IRFunction, IRProgram

# RV32 word size and load/store mnemonics (fixed for Ripes).
W = 4
LD = "lw"
SD = "sw"
SHIFT = 2  # log2(W) for array indexing

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
        self._t0: str | None = None
        self._t1: str | None = None

    def _ld_t0(self, addr: str) -> None:
        if self._t0 == addr:
            return
        self.i(f"{LD}    t0, {addr}")
        self._t0 = addr

    def _sd_t0(self, addr: str) -> None:
        self.i(f"{SD}    t0, {addr}")
        self._t0 = addr

    def _ld_t1(self, addr: str) -> None:
        if self._t1 == addr:
            return
        self.i(f"{LD}    t1, {addr}")
        self._t1 = addr

    def _kill_t0(self) -> None:
        self._t0 = None

    def _kill_t1(self) -> None:
        self._t1 = None

    def _kill_tmps(self) -> None:
        self._t0 = self._t1 = None

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
                cur += n * W
                slots[name] = cur

        for p in func.param_names:
            alloc(p)
        for ins in func.instructions:
            op, a = ins.op, ins.args
            if op == "ALLOC_ARRAY":
                arrs[a[0]] = cur + W
                alloc(a[0], int(a[1]))
            elif op in _DEF:
                alloc(a[0])
            elif op == "STORE":
                alloc(a[0])
            elif op == "CALL" and a[0]:
                alloc(a[0])
        fsize = (cur + 2 * W + 15) & ~15
        return slots, arrs, fsize

    def ref(self, slots: Dict[str, int], name: str) -> str:
        return f"-{slots[name] + 2 * W}(s0)"

    def _print_int(self, value_addr: str) -> None:
        self.i(f"{LD}    a0, {value_addr}")
        self.i("li    a7, 1")
        self.i("ecall")
        self.i("li    a0, 10")
        self.i("li    a7, 11")
        self.i("ecall")

    def _print_uint(self, value_addr: str) -> None:
        self._print_int(value_addr)

    def _print_char(self, value_addr: str) -> None:
        self.i(f"{LD}    a0, {value_addr}")
        self.i("li    a7, 11")
        self.i("ecall")

    def _print_string(self, value_addr: str) -> None:
        self.i(f"{LD}    a0, {value_addr}")
        self.i("li    a7, 4")
        self.i("ecall")
        self.i("li    a0, 10")
        self.i("li    a7, 11")
        self.i("ecall")

    def _read_int(self, slots: Dict[str, int], name: str) -> None:
        self.i("li    a7, 5")
        self.i("ecall")
        self.i(f"{SD}    a0, -{slots[name] + 2 * W}(s0)")

    def _exit(self, value_addr: str) -> None:
        self.i(f"{LD}    a0, {value_addr}")
        self.i("li    a7, 93")
        self.i("ecall")

    def generate(self) -> str:
        for fn in self.prog.functions:
            for ins in fn.instructions:
                if ins.op == "CONST" and isinstance(ins.args[1], tuple) and ins.args[1][0] == "string":
                    self._intern(ins.args[1][1])

        self.e()
        self.e("    .data")
        for val, lbl in self.strs.items():
            self.e(f'{lbl}: .string "{val.replace(chr(34), chr(92)+chr(34))}"')
        self.e()
        self.e("    .text")
        if any(f.name == "main" for f in self.prog.functions):
            self.e("    .globl main")
        self.e()

        if any(f.name == "main" for f in self.prog.functions):
            self.e("    .globl _start")
            self.e("_start:")
            self.i("call  main")
            self.i("li    a7, 10")
            self.i("ecall")
            self.e()

        for fn in self.prog.functions:
            self._gen_func(fn)
        return "\n".join(self.out)

    def _gen_func(self, func: IRFunction) -> None:
        slots, arrs, N = self._build_frame(func)
        self.fn = func.name
        self._kill_tmps()
        r = lambda name: self.ref(slots, name)

        self.e(f"{func.name}:")
        self.i(f"addi  sp, sp, -{N}")
        self.i(f"{SD}    ra, {N - W}(sp)")
        self.i(f"{SD}    s0, {N - 2*W}(sp)")
        self.i(f"addi  s0, sp, {N}")
        self.e()

        for idx, p in enumerate(func.param_names):
            if idx < 8:
                self.i(f"{SD}    {_AREG[idx]}, {r(p)}")
            else:
                self.i(f"{LD}    t0, {W + (idx-8)*W}(s0)")
                self._sd_t0(r(p))

        kinds: Dict[str, str] = {p: "int" for p in func.param_names}
        pend: List[str] = []

        for ins in func.instructions:
            op, a = ins.op, ins.args

            if op == "FUNC_ENTRY":
                pass
            elif op == "LABEL":
                self.e(f"{self.lbl(a[0])}:")
                self._kill_tmps()
            elif op == "JMP":
                self.i(f"j     {self.lbl(a[0])}")
            elif op == "JMP_IF":
                self._ld_t0(r(a[0]))
                self.i(f"bnez  t0, {self.lbl(a[1])}")
            elif op == "JMP_IF_NOT":
                self._ld_t0(r(a[0]))
                self.i(f"beqz  t0, {self.lbl(a[1])}")

            elif op == "CONST":
                dest, (kind, val) = a[0], a[1]
                kinds[dest] = kind
                if kind in ("int", "uint32", "bool"):
                    self.i(f"li    t0, {int(val)}")
                    self._kill_t0()
                    self._sd_t0(r(dest))
                elif kind == "char":
                    self.i(f"li    t0, {int(val) if isinstance(val, int) else ord(val)}")
                    self._kill_t0()
                    self._sd_t0(r(dest))
                elif kind == "float":
                    self.i("# float -> 0")
                    self.i(f"{SD}    zero, {r(dest)}")
                elif kind == "string":
                    self.i(f"la    t0, {self._intern(val)}")
                    self._kill_t0()
                    self._sd_t0(r(dest))

            elif op == "LOAD":
                kinds[a[0]] = kinds.get(a[1], "int")
                self._ld_t0(r(a[1]))
                self._sd_t0(r(a[0]))
            elif op == "STORE":
                kinds[a[0]] = kinds.get(a[1], "int")
                self._ld_t0(r(a[1]))
                self._sd_t0(r(a[0]))
            elif op == "ALLOC_ARRAY":
                pass
            elif op == "LOAD_ARR":
                dest, arr, idx = a
                self._ld_t1(r(idx))
                self.i(f"slli  t1, t1, {SHIFT}")
                self._kill_t1()
                self.i(f"addi  t0, s0, -{arrs[arr] + 2*W}")
                self._kill_t0()
                self.i("sub   t0, t0, t1")
                self.i(f"{LD}    t0, 0(t0)")
                self._sd_t0(r(dest))
            elif op == "STORE_ARR":
                arr, idx, src = a
                self._ld_t1(r(idx))
                self.i(f"slli  t1, t1, {SHIFT}")
                self._kill_t1()
                self.i(f"addi  t0, s0, -{arrs[arr] + 2*W}")
                self._kill_t0()
                self.i("sub   t0, t0, t1")
                self.i(f"{LD}    t2, {r(src)}")
                self.i(f"{SD}    t2, 0(t0)")

            elif op in _BINOP:
                dest, l, rv = a
                kinds[dest] = kinds.get(l, "int")
                self._ld_t0(r(l))
                self._ld_t1(r(rv))
                self.i(f"{_BINOP[op]:<5} t0, t0, t1")
                self._kill_t0()
                self._kill_t1()
                self._sd_t0(r(dest))
            elif op == "NEG":
                kinds[a[0]] = kinds.get(a[1], "int")
                self._ld_t0(r(a[1]))
                self.i("neg   t0, t0")
                self._kill_t0()
                self._sd_t0(r(a[0]))
            elif op == "INC":
                kinds[a[0]] = kinds.get(a[1], "int")
                self._ld_t0(r(a[1]))
                self.i("addi  t0, t0, 1")
                self._kill_t0()
                self._sd_t0(r(a[0]))
            elif op == "DEC":
                kinds[a[0]] = kinds.get(a[1], "int")
                self._ld_t0(r(a[1]))
                self.i("addi  t0, t0, -1")
                self._kill_t0()
                self._sd_t0(r(a[0]))

            elif op in _CMP:
                dest, l, rv = a
                kinds[dest] = "bool"
                self._ld_t0(r(l))
                self._ld_t1(r(rv))
                for line in _CMP[op]:
                    self.i(line)
                self._kill_t0()
                self._kill_t1()
                self._sd_t0(r(dest))
            elif op == "AND":
                dest, l, rv = a
                kinds[dest] = "bool"
                self._ld_t0(r(l))
                self.i("sltu  t0, zero, t0")
                self._kill_t0()
                self._ld_t1(r(rv))
                self.i("sltu  t1, zero, t1")
                self._kill_t1()
                self.i("and   t0, t0, t1")
                self._kill_t0()
                self._sd_t0(r(dest))
            elif op == "OR":
                dest, l, rv = a
                kinds[dest] = "bool"
                self._ld_t0(r(l))
                self.i("sltu  t0, zero, t0")
                self._kill_t0()
                self._ld_t1(r(rv))
                self.i("sltu  t1, zero, t1")
                self._kill_t1()
                self.i("or    t0, t0, t1")
                self._kill_t0()
                self._sd_t0(r(dest))
            elif op == "NOT":
                kinds[a[0]] = "bool"
                self._ld_t0(r(a[1]))
                self.i("sltiu t0, t0, 1")
                self._kill_t0()
                self._sd_t0(r(a[0]))

            elif op == "PRINT":
                for arg in a:
                    k = kinds.get(arg, "int")
                    addr = r(arg)
                    if k == "string":
                        self._print_string(addr)
                    elif k == "char":
                        self._print_char(addr)
                    elif k == "uint32":
                        self._print_uint(addr)
                    else:
                        self._print_int(addr)
                self._kill_tmps()
            elif op == "READ_INT":
                kinds[a[0]] = "int"
                self._read_int(slots, a[0])
                self._kill_tmps()
            elif op == "EXIT":
                self._exit(r(a[0]))
                self._kill_tmps()
            elif op == "PARAM":
                pend.append(a[0])
            elif op == "CALL":
                dest_r = a[0] if a[0] else None
                extra = max(0, len(pend) - 8)
                eb = ((extra * W + 15) & ~15) if extra else 0
                if eb:
                    self.i(f"addi  sp, sp, -{eb}")
                    for j, p in enumerate(pend[8:]):
                        self._ld_t0(r(p))
                        self.i(f"{SD}    t0, {j*W}(sp)")
                for j, p in enumerate(pend[:8]):
                    self.i(f"{LD}    {_AREG[j]}, {r(p)}")
                self.i(f"call  {a[1]}")
                if eb:
                    self.i(f"addi  sp, sp, {eb}")
                if dest_r:
                    kinds[dest_r] = "int"
                    self.i(f"{SD}    a0, {r(dest_r)}")
                self._kill_tmps()
                pend.clear()
            elif op == "RET":
                if a[0]:
                    self.i(f"{LD}    a0, {r(a[0])}")
                else:
                    self.i("li    a0, 0")
                self.i(f"{LD}    ra, {N - W}(sp)")
                self.i(f"{LD}    s0, {N - 2*W}(sp)")
                self.i(f"addi  sp, sp, {N}")
                self.i("ret")

        self.e()
