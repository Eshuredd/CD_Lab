"""IR → portable C++17. int temps; std::vector<int> for arrays."""

from __future__ import annotations

from typing import Callable, Dict, List, Set, Tuple

from ir.ir import IRFunction, IRProgram, Instruction, is_temp

_kw = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch "
    "char char8_t char16_t char32_t class compl concept const consteval constexpr "
    "constinit continue co_await co_return co_yield decltype default delete do "
    "double dynamic_cast else enum explicit export extern false float for friend "
    "goto if inline int long mutable namespace new noexcept not not_eq nullptr "
    "operator or or_eq private protected public register reinterpret_cast requires "
    "return short signed sizeof static static_assert static_cast struct switch "
    "template this thread_local throw true try typedef typeid typename union "
    "unsigned using virtual void volatile wchar_t while xor xor_eq".split()
)
_SYM = {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%"}
_CMP = {"LT": "<", "LE": "<=", "GT": ">", "GE": ">=", "EQ": "==", "NE": "!="}
_PRINT = {
    "string": lambda v: f'std::printf("%s\\n", reinterpret_cast<const char*>(static_cast<uintptr_t>({v})));',
    "char": lambda v: f'std::printf("%c\\n", static_cast<int>(static_cast<char>({v})));',
    "uint32": lambda v: f'std::printf("%lu\\n", static_cast<unsigned long>(static_cast<uint32_t>({v})));',
    "int": lambda v: f'std::printf("%d\\n", {v});',
}


class CppTranspileBackend:
    def __init__(self, prog: IRProgram) -> None:
        self.prog = prog
        self.lines: List[str] = []
        self.strs: List[Tuple[str, str]] = []

    def _cid(self, name: str) -> str:
        if not name:
            return ""
        if is_temp(name):
            return "_t" + name[1:]
        return "_" + name if name in _kw else name

    def _intern_str(self, val: str) -> str:
        for lbl, v in self.strs:
            if v == val:
                return lbl
        lbl = f"cd_s{len(self.strs)}"
        self.strs.append((lbl, val))
        return lbl

    @staticmethod
    def _cpp_string_literal(val: str) -> str:
        parts = []
        for ch in val:
            o = ord(ch)
            if ch == "\\":
                parts.append("\\\\")
            elif ch == '"':
                parts.append('\\"')
            elif ch in "\n\r\t":
                parts.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
            elif o < 32 or o > 126:
                parts.append(f"\\x{o:02x}")
            else:
                parts.append(ch)
        return '"' + "".join(parts) + '"'

    def _scan_function(self, func: IRFunction) -> Tuple[Set[str], Set[str], Dict[str, int]]:
        temps: Set[str] = set()
        arrays: Dict[str, int] = {}
        scalars: Set[str] = set(func.param_names)

        def note(x) -> None:
            if isinstance(x, str) and is_temp(x):
                temps.add(x)

        for ins in func.instructions:
            op, a = ins.op, ins.args
            for x in a:
                note(x)
            if op == "ALLOC_ARRAY":
                arrays[a[0]] = int(a[1])
            elif op == "STORE" and not is_temp(a[0]):
                scalars.add(a[0])
            elif op == "LOAD" and not is_temp(a[1]):
                scalars.add(a[1])
            elif op == "LOAD_ARR":
                arrays.setdefault(a[1], 0)
                note(a[2])
            elif op == "STORE_ARR":
                arrays.setdefault(a[0], 0)
                note(a[1])
                note(a[2])
        return temps, scalars, arrays

    def _ret_ctype(self, func: IRFunction) -> str:
        if func.name == "main":
            return "int"
        return "void" if func.return_type == "void" else "int"

    def _func_params(self, func: IRFunction) -> str:
        ps = ", ".join(f"int {self._cid(p)}" for p in func.param_names)
        if func.name == "main":
            return "void" if not ps else ps
        return ps if ps else "void"

    def generate(self) -> str:
        self.lines = []
        self.strs = []
        for fn in self.prog.functions:
            for ins in fn.instructions:
                if ins.op == "CONST" and isinstance(ins.args[1], tuple) and ins.args[1][0] == "string":
                    self._intern_str(ins.args[1][1])

        self._ln("// Generated from IR. Compile as C++17: g++ -std=c++17 -O2 -o prog out.cpp")
        for h in ("<cstdint>", "<cstdio>", "<cstdlib>", "<vector>"):
            self._ln(f"#include {h}")
        self._ln("")
        for lbl, val in self.strs:
            self._ln(f"static const char {lbl}[] = {self._cpp_string_literal(val)};")
        if self.strs:
            self._ln("")

        for fn in self.prog.functions:
            rt, nm, pr = self._ret_ctype(fn), self._cid(fn.name), self._func_params(fn)
            self._ln(f"{rt} {nm}({pr});")
        self._ln("")
        for fn in self.prog.functions:
            self._emit_func(fn)
            self._ln("")
        return "\n".join(self.lines).rstrip() + "\n"

    def _ln(self, s: str = "") -> None:
        self.lines.append(s)

    @staticmethod
    def _strip_unreachable_jmp_after_ret(instructions: List[Instruction]) -> List[Instruction]:
        """Drop JMP that follows RET — they are unreachable and break -Werror builds."""
        out: List[Instruction] = []
        i = 0
        n = len(instructions)
        while i < n:
            ins = instructions[i]
            out.append(ins)
            if (
                ins.op == "RET"
                and i + 1 < n
                and instructions[i + 1].op == "JMP"
            ):
                i += 2
            else:
                i += 1
        return out

    def _emit_func(self, func: IRFunction) -> None:
        temps, scalars, arrays = self._scan_function(func)
        for an in arrays:
            scalars.discard(an)

        rt, nm, pr = self._ret_ctype(func), self._cid(func.name), self._func_params(func)
        self._ln(f"{rt} {nm}({pr}) {{")
        for a in sorted(arrays):
            self._ln(f"    std::vector<int> {self._cid(a)};")
        pn = set(func.param_names)
        for s in sorted(scalars - pn):
            self._ln(f"    int {self._cid(s)} = 0;")
        key = lambda x: int(x[1:]) if x[1:].isdigit() else x
        for t in sorted(temps, key=key):
            self._ln(f"    int {self._cid(t)} = 0;")

        kinds: Dict[str, str] = {p: "int" for p in func.param_names}
        pend: List[str] = []
        for ins in self._strip_unreachable_jmp_after_ret(func.instructions):
            self._emit_ins(ins, kinds, pend, func)
        self._ln("}")

    def _emit_ins(self, ins, kinds: Dict[str, str], pend: List[str], func: IRFunction) -> None:
        op, a = ins.op, ins.args
        I: Callable[[str], None] = lambda s: self._ln(f"    {s}")
        c = self._cid

        if op == "FUNC_ENTRY":
            return
        if op == "LABEL":
            self._ln(f"  {c(a[0])}:")
            return
        if op == "JMP":
            I(f"goto {c(a[0])};")
            return
        if op == "JMP_IF":
            I(f"if ({c(a[0])}) goto {c(a[1])};")
            return
        if op == "JMP_IF_NOT":
            I(f"if (!{c(a[0])}) goto {c(a[1])};")
            return

        if op == "CONST":
            d, (kind, val) = a[0], a[1]
            kinds[d] = kind
            if kind in ("int", "uint32", "bool"):
                I(f"{c(d)} = {int(val)};")
            elif kind == "char":
                iv = int(val) if isinstance(val, int) else ord(val) if val else 0
                I(f"{c(d)} = {iv};")
            elif kind == "float":
                I(f"{c(d)} = 0; // float unsupported")
            else:
                I(f"{c(d)} = static_cast<int>(reinterpret_cast<uintptr_t>(static_cast<const void*>({self._intern_str(val)})));")
            return
        if op == "LOAD":
            kinds[a[0]] = kinds.get(a[1], "int")
            I(f"{c(a[0])} = {c(a[1])};")
            return
        if op == "STORE":
            kinds[a[0]] = kinds.get(a[1], "int")
            I(f"{c(a[0])} = {c(a[1])};")
            return
        if op == "ALLOC_ARRAY":
            I(f"{c(a[0])}.resize(static_cast<size_t>({int(a[1])}));")
            return
        if op == "LOAD_ARR":
            I(f"{c(a[0])} = {c(a[1])}[static_cast<size_t>({c(a[2])})];")
            return
        if op == "STORE_ARR":
            I(f"{c(a[0])}[static_cast<size_t>({c(a[1])})] = {c(a[2])};")
            return

        if op in _SYM:
            d, l, r = a
            kinds[d] = "int" if op == "MOD" else kinds.get(l, "int")
            I(f"{c(d)} = {c(l)} {_SYM[op]} {c(r)};")
            return
        if op == "NEG":
            kinds[a[0]] = kinds.get(a[1], "int")
            I(f"{c(a[0])} = -{c(a[1])};")
            return
        if op == "INC":
            kinds[a[0]] = kinds.get(a[1], "int")
            I(f"{c(a[0])} = {c(a[1])} + 1;")
            return
        if op == "DEC":
            kinds[a[0]] = kinds.get(a[1], "int")
            I(f"{c(a[0])} = {c(a[1])} - 1;")
            return

        if op in _CMP:
            kinds[a[0]] = "bool"
            I(f"{c(a[0])} = ({c(a[1])} {_CMP[op]} {c(a[2])}) ? 1 : 0;")
            return
        if op == "AND":
            kinds[a[0]] = "bool"
            I(f"{c(a[0])} = ({c(a[1])} != 0 && {c(a[2])} != 0) ? 1 : 0;")
            return
        if op == "OR":
            kinds[a[0]] = "bool"
            I(f"{c(a[0])} = ({c(a[1])} != 0 || {c(a[2])} != 0) ? 1 : 0;")
            return
        if op == "NOT":
            kinds[a[0]] = "bool"
            I(f"{c(a[0])} = (!{c(a[1])}) ? 1 : 0;")
            return

        if op == "PRINT":
            for arg in a:
                k = kinds.get(arg, "int")
                I(_PRINT.get(k, _PRINT["int"])(c(arg)))
            return
        if op == "READ_INT":
            kinds[a[0]] = "int"
            I(f'std::scanf("%d", static_cast<void*>(&{c(a[0])}));')
            return
        if op == "EXIT":
            I(f"std::exit(static_cast<int>({c(a[0])}));")
            return
        if op == "PARAM":
            pend.append(c(a[0]))
            return
        if op == "CALL":
            dest, name, n = a[0], a[1], int(a[2])
            args, callee = pend[:n], c(name)
            del pend[:n]
            if dest:
                kinds[dest] = "int"
                I(f"{c(dest)} = {callee}({', '.join(args)});")
            else:
                I(f"{callee}({', '.join(args)});")
            return
        if op == "RET":
            if func.name == "main":
                I(f"return static_cast<int>({c(a[0])});" if a[0] else "return 0;")
            elif func.return_type == "void":
                I("return;")
            else:
                I(f"return {c(a[0])};" if a[0] else "return 0;")
            return

        raise NotImplementedError(f"CppTranspile: unhandled IR {op!r} {a!r}")
