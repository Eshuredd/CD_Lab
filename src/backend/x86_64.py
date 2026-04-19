"""x86-64 NASM backend for bare ``nasm`` + ``ld`` (typical online assemblers).

Uses ``global _start``, Linux syscalls only (``sys_read``, ``sys_write``,
``sys_exit``) — no libc. Entry is ``_start`` → ``call main`` → ``syscall`` exit.
Locals: ``qword [rbp - N]``; args per SysV (rdi…r9). Emits only the runtime
helpers that IR actually uses (``_print_int``, ``_print_str``, ``_print_char``,
``_read_int``).
"""

from __future__ import annotations

import io
from typing import Callable, Dict, List, Tuple

from ir.ir import Instruction, IRFunction, IRProgram

_REGS = ("rdi", "rsi", "rdx", "rcx", "r8", "r9")
_SETCC = {"LT": "setl", "LE": "setle", "GT": "setg", "GE": "setge", "EQ": "sete", "NE": "setne"}
_DEF = frozenset({
    "CONST", "LOAD", "LOAD_ARR", "READ_INT", "ADD", "SUB", "MUL", "DIV", "MOD",
    "NEG", "INC", "DEC", "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR", "NOT",
})


def _nasm_string(val: str) -> str:
    parts, buf, i = [], "", 0
    while i < len(val):
        c = val[i]
        if c == "\\" and i + 1 < len(val):
            esc = val[i + 1]
            if buf:
                parts.append(f'"{buf}"')
                buf = ""
            m = {"n": "10", "t": "9", "r": "13", "0": "0", "\\": "92", '"': "34", "'": "39"}
            parts.append(m.get(esc, f'"{esc}"'))
            i += 2
        elif c == '"':
            if buf:
                parts.append(f'"{buf}"')
                buf = ""
            parts.append("34")
            i += 1
        else:
            buf += c
            i += 1
    if buf:
        parts.append(f'"{buf}"')
    return ", ".join(parts) if parts else '""'


_RUNTIME = r"""
_print_int:
    push rbp
    mov rbp, rsp
    push rbx
    mov rax, rdi
    lea rdi, [rel _iobuf + 31]
    mov byte [rdi], 10
    mov rbx, 0
    test rax, rax
    jns .pi_pos
    neg rax
    mov rbx, 1
.pi_pos:
    mov rcx, 10
.pi_loop:
    dec rdi
    xor rdx, rdx
    div rcx
    add dl, '0'
    mov [rdi], dl
    test rax, rax
    jnz .pi_loop
    test rbx, rbx
    jz .pi_nosign
    dec rdi
    mov byte [rdi], '-'
.pi_nosign:
    lea rax, [rel _iobuf + 32]
    mov rdx, rax
    sub rdx, rdi
    mov rsi, rdi
    mov rdi, 1
    mov rax, 1
    syscall
    pop rbx
    pop rbp
    ret

_print_str:
    push rbp
    mov rbp, rsp
    push rbx
    mov rbx, rdi
    xor rcx, rcx
.ps_len:
    cmp byte [rbx + rcx], 0
    je  .ps_write
    inc rcx
    jmp .ps_len
.ps_write:
    mov rdx, rcx
    mov rsi, rbx
    mov rdi, 1
    mov rax, 1
    syscall
    mov byte [rel _iobuf], 10
    mov rdx, 1
    lea rsi, [rel _iobuf]
    mov rdi, 1
    mov rax, 1
    syscall
    pop rbx
    pop rbp
    ret

_print_char:
    push rbp
    mov rbp, rsp
    mov [rel _iobuf], dil
    mov byte [rel _iobuf + 1], 10
    mov rdx, 2
    lea rsi, [rel _iobuf]
    mov rdi, 1
    mov rax, 1
    syscall
    pop rbp
    ret

_read_int:
    push rbp
    mov rbp, rsp
    mov rax, 0
    mov rdi, 0
    lea rsi, [rel _inbuf]
    mov rdx, 63
    syscall
    mov rcx, rax
    lea rdi, [rel _inbuf]
    xor rax, rax
    xor r8, r8
    test rcx, rcx
    jle .ri_done
.ri_skip:
    cmp rcx, 0
    jle .ri_done
    mov dl, [rdi]
    cmp dl, ' '
    je  .ri_adv
    cmp dl, 9
    je  .ri_adv
    cmp dl, 10
    je  .ri_adv
    cmp dl, 13
    je  .ri_adv
    jmp .ri_sign
.ri_adv:
    inc rdi
    dec rcx
    jmp .ri_skip
.ri_sign:
    cmp byte [rdi], '-'
    jne .ri_digits
    mov r8, 1
    inc rdi
    dec rcx
.ri_digits:
    cmp rcx, 0
    jle .ri_end
    movzx rdx, byte [rdi]
    cmp dl, '0'
    jb  .ri_end
    cmp dl, '9'
    ja  .ri_end
    sub dl, '0'
    imul rax, rax, 10
    add rax, rdx
    inc rdi
    dec rcx
    jmp .ri_digits
.ri_end:
    test r8, r8
    jz  .ri_done
    neg rax
.ri_done:
    pop rbp
    ret
"""


class X86_64Backend:
    def __init__(self, program: IRProgram) -> None:
        self._prog = program
        self._pool: Dict[str, str] = {}
        self._sc = 0
        self._buf = io.StringIO()
        self._used: set[str] = set()  # which runtime helpers are referenced

    def _lbl(self, v: str) -> str:
        for lbl, s in self._pool.items():
            if s == v:
                return lbl
        lbl = f"_str_{self._sc}"
        self._sc += 1
        self._pool[lbl] = v
        return lbl

    def _ln(self, s: str = "") -> None:
        self._buf.write(s + "\n")

    def _i(self, s: str) -> None:
        self._buf.write("    " + s + "\n")

    def _build_frame(self, func: IRFunction) -> Tuple[Dict[str, int], Dict[str, int], int]:
        slot, abase, cur = {}, {}, 0

        def alloc(nm: str, n: int = 1) -> None:
            nonlocal cur
            if nm not in slot:
                cur += n * 8
                slot[nm] = cur

        for p in func.param_names:
            alloc(p)
        for ins in func.instructions:
            op, a = ins.op, ins.args
            if op == "ALLOC_ARRAY":
                abase[a[0]] = cur + 8
                alloc(a[0], int(a[1]))
            elif op in _DEF:
                alloc(a[0])
            elif op == "STORE":
                alloc(a[0])
            elif op == "CALL" and a[0]:
                alloc(a[0])
        return slot, abase, (cur + 15) & ~15

    def _ref(self, slot: Dict[str, int], name: str) -> str:
        return f"qword [rbp - {slot[name]}]"

    def generate(self) -> str:
        for fn in self._prog.functions:
            for ins in fn.instructions:
                if ins.op == "CONST" and isinstance(ins.args[1], tuple) and ins.args[1][0] == "string":
                    self._lbl(ins.args[1][1])

        # Generate function bodies first into a side buffer so we know which
        # runtime helpers were touched and can omit unused ones.
        body_buf = io.StringIO()
        main_buf = self._buf
        self._buf = body_buf
        for fn in self._prog.functions:
            self._gen_fn(fn, *self._build_frame(fn))
        self._buf = main_buf

        # ---- header / data / bss ----
        if self._pool:
            self._ln("section .data")
            for lbl, val in self._pool.items():
                self._ln(f"    {lbl:<14} db {_nasm_string(val)}, 0")
            self._ln()

        if self._used:
            self._ln("section .bss")
            if {"_print_int", "_print_str", "_print_char"} & self._used:
                self._ln("    _iobuf      resb 64")
            if "_read_int" in self._used:
                self._ln("    _inbuf      resb 64")
            self._ln()

        self._ln("section .text")
        has_main = any(f.name == "main" for f in self._prog.functions)
        if has_main:
            self._ln("    global _start")
        self._ln()

        # ---- _start trampoline: call main, then sys_exit with rax ----
        if has_main:
            self._ln("_start:")
            self._i("call main")
            self._i("mov rdi, rax")
            self._i("mov rax, 60")
            self._i("syscall")
            self._ln()

        # ---- emit only the runtime helpers we actually need ----
        for helper, block in _split_runtime(_RUNTIME).items():
            if helper in self._used:
                self._buf.write(block)
                self._ln()

        # ---- user function bodies ----
        self._buf.write(body_buf.getvalue())
        return self._buf.getvalue()

    def _gen_fn(self, func: IRFunction, slot: Dict[str, int], ab: Dict[str, int], fs: int) -> None:
        r: Callable[[str], str] = lambda n: self._ref(slot, n)
        self._ln(f"{func.name}:")
        self._i("push rbp")
        self._i("mov rbp, rsp")
        if fs:
            self._i(f"sub rsp, {fs}")
        self._ln()

        for i, p in enumerate(func.param_names):
            if i < 6:
                self._i(f"mov {r(p)}, {_REGS[i]}")
            else:
                self._i(f"mov rax, [rbp + {16 + (i - 6) * 8}]")
                self._i(f"mov {r(p)}, rax")

        kinds: Dict[str, str] = {p: "int" for p in func.param_names}
        pend: List[str] = []

        for ins in func.instructions:
            self._emit(ins, slot, ab, r, kinds, pend)
        self._ln()

    def _emit(
        self,
        ins: Instruction,
        slot: Dict[str, int],
        ab: Dict[str, int],
        r: Callable[[str], str],
        kinds: Dict[str, str],
        pend: List[str],
    ) -> None:
        op, a = ins.op, ins.args

        if op == "FUNC_ENTRY":
            return
        if op == "LABEL":
            self._ln(f"  .{a[0]}:")
            return
        if op == "JMP":
            self._i(f"jmp .{a[0]}")
            return
        if op == "JMP_IF":
            self._i(f"mov rax, {r(a[0])}")
            self._i("test rax, rax")
            self._i(f"jnz .{a[1]}")
            return
        if op == "JMP_IF_NOT":
            self._i(f"mov rax, {r(a[0])}")
            self._i("test rax, rax")
            self._i(f"jz .{a[1]}")
            return

        if op == "CONST":
            dest, (kind, val) = a[0], a[1]
            kinds[dest] = kind
            if kind in ("int", "uint32", "bool"):
                self._i(f"mov rax, {int(val)}")
                self._i(f"mov {r(dest)}, rax")
            elif kind == "char":
                self._i(f"mov rax, {int(val) if isinstance(val, int) else ord(val)}")
                self._i(f"mov {r(dest)}, rax")
            elif kind == "float":
                self._i("; float -> 0")
                self._i("mov rax, 0")
                self._i(f"mov {r(dest)}, rax")
            elif kind == "string":
                self._i(f"lea rax, [rel {self._lbl(val)}]")
                self._i(f"mov {r(dest)}, rax")
            return

        if op == "LOAD":
            if a[1] in kinds:
                kinds[a[0]] = kinds[a[1]]
            self._i(f"mov rax, {r(a[1])}")
            self._i(f"mov {r(a[0])}, rax")
            return
        if op == "STORE":
            if a[1] in kinds:
                kinds[a[0]] = kinds[a[1]]
            self._i(f"mov rax, {r(a[1])}")
            self._i(f"mov {r(a[0])}, rax")
            return
        if op == "ALLOC_ARRAY":
            return
        if op == "LOAD_ARR":
            dest, arr, idx = a[0], a[1], a[2]
            b = ab[arr]
            self._i(f"mov rcx, {r(idx)}")
            self._i("imul rcx, 8")
            self._i(f"lea rdx, [rbp - {b}]")
            self._i("sub rdx, rcx")
            self._i("mov rax, [rdx]")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "STORE_ARR":
            arr, idx, src = a[0], a[1], a[2]
            b = ab[arr]
            self._i(f"mov rcx, {r(idx)}")
            self._i("imul rcx, 8")
            self._i(f"lea rdx, [rbp - {b}]")
            self._i("sub rdx, rcx")
            self._i(f"mov rax, {r(src)}")
            self._i("mov [rdx], rax")
            return

        if op == "ADD":
            dest, l, rv = a
            kinds[dest] = kinds.get(l, "int")
            self._i(f"mov rax, {r(l)}")
            self._i(f"mov rcx, {r(rv)}")
            self._i("add rax, rcx")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "SUB":
            dest, l, rv = a
            kinds[dest] = kinds.get(l, "int")
            self._i(f"mov rax, {r(l)}")
            self._i(f"mov rcx, {r(rv)}")
            self._i("sub rax, rcx")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "MUL":
            dest, l, rv = a
            kinds[dest] = kinds.get(l, "int")
            self._i(f"mov rax, {r(l)}")
            self._i(f"imul rax, {r(rv)}")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "DIV":
            dest, l, rv = a
            kinds[dest] = kinds.get(l, "int")
            self._i(f"mov rax, {r(l)}")
            self._i("cqo")
            self._i(f"idiv {r(rv)}")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "MOD":
            dest, l, rv = a
            kinds[dest] = "int"
            self._i(f"mov rax, {r(l)}")
            self._i("cqo")
            self._i(f"idiv {r(rv)}")
            self._i(f"mov {r(dest)}, rdx")
            return
        if op == "NEG":
            kinds[a[0]] = kinds.get(a[1], "int")
            self._i(f"mov rax, {r(a[1])}")
            self._i("neg rax")
            self._i(f"mov {r(a[0])}, rax")
            return
        if op == "INC":
            kinds[a[0]] = kinds.get(a[1], "int")
            self._i(f"mov rax, {r(a[1])}")
            self._i("inc rax")
            self._i(f"mov {r(a[0])}, rax")
            return
        if op == "DEC":
            kinds[a[0]] = kinds.get(a[1], "int")
            self._i(f"mov rax, {r(a[1])}")
            self._i("dec rax")
            self._i(f"mov {r(a[0])}, rax")
            return

        if op in _SETCC:
            dest, l, rv = a
            kinds[dest] = "bool"
            self._i(f"mov rax, {r(l)}")
            self._i(f"cmp rax, {r(rv)}")
            self._i(f"{_SETCC[op]} al")
            self._i("movzx rax, al")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "AND":
            dest, l, rv = a
            kinds[dest] = "bool"
            self._i(f"mov rax, {r(l)}")
            self._i("test rax, rax")
            self._i("setnz al")
            self._i("movzx rax, al")
            self._i(f"mov rcx, {r(rv)}")
            self._i("test rcx, rcx")
            self._i("setnz cl")
            self._i("movzx rcx, cl")
            self._i("and rax, rcx")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "OR":
            dest, l, rv = a
            kinds[dest] = "bool"
            self._i(f"mov rax, {r(l)}")
            self._i("test rax, rax")
            self._i("setnz al")
            self._i("movzx rax, al")
            self._i(f"mov rcx, {r(rv)}")
            self._i("test rcx, rcx")
            self._i("setnz cl")
            self._i("movzx rcx, cl")
            self._i("or rax, rcx")
            self._i(f"mov {r(dest)}, rax")
            return
        if op == "NOT":
            kinds[a[0]] = "bool"
            self._i(f"mov rax, {r(a[1])}")
            self._i("test rax, rax")
            self._i("setz al")
            self._i("movzx rax, al")
            self._i(f"mov {r(a[0])}, rax")
            return

        if op == "PRINT":
            for arg in a:
                k = kinds.get(arg, "int")
                if k == "string":
                    self._used.add("_print_str")
                    self._i(f"mov rdi, {r(arg)}")
                    self._i("call _print_str")
                elif k == "char":
                    self._used.add("_print_char")
                    self._i(f"mov rdi, {r(arg)}")
                    self._i("call _print_char")
                else:
                    self._used.add("_print_int")
                    self._i(f"mov rdi, {r(arg)}")
                    self._i("call _print_int")
            return
        if op == "READ_INT":
            kinds[a[0]] = "int"
            self._used.add("_read_int")
            self._i("call _read_int")
            self._i(f"mov {r(a[0])}, rax")
            return
        if op == "EXIT":
            self._i(f"mov rdi, {r(a[0])}")
            self._i("mov rax, 60")
            self._i("syscall")
            return
        if op == "PARAM":
            pend.append(a[0])
            return
        if op == "CALL":
            dest, callee = (a[0] or None), a[1]
            nreg = len(_REGS)
            extra = max(0, len(pend) - nreg)
            pad = extra % 2 == 1
            if pad:
                self._i("sub rsp, 8")
            for p in reversed(pend[nreg:]):
                self._i(f"mov rax, {r(p)}")
                self._i("push rax")
            for i, p in enumerate(pend[:nreg]):
                self._i(f"mov {_REGS[i]}, {r(p)}")
            self._i(f"call {callee}")
            rs = extra * 8 + (8 if pad else 0)
            if rs:
                self._i(f"add rsp, {rs}")
            if dest:
                kinds[dest] = "int"
                self._i(f"mov {r(dest)}, rax")
            pend.clear()
            return
        if op == "RET":
            if a[0]:
                self._i(f"mov rax, {r(a[0])}")
            else:
                self._i("xor eax, eax")
            self._i("mov rsp, rbp")
            self._i("pop rbp")
            self._i("ret")
            return

        self._i(f"; TODO: {op} {a}")


def _split_runtime(src: str) -> Dict[str, str]:
    """Split _RUNTIME blob into a {label: text} map keyed by helper name.

    The leading docstring comment that precedes each helper is attached to
    *that* helper, and trailing blank / comment lines are stripped so a block
    never bleeds into the next helper's documentation.
    """
    out: Dict[str, str] = {}
    cur_name: str | None = None
    cur_lines: List[str] = []
    pending_comments: List[str] = []

    def is_helper_label(line: str) -> bool:
        s = line.lstrip()
        return (
            line.startswith("_")
            and s.endswith(":\n")
            and " " not in s[:-2]
            and "\t" not in s[:-2]
        )

    for line in src.splitlines(keepends=True):
        stripped_no_nl = line.rstrip("\n")
        is_blank = stripped_no_nl.strip() == ""
        is_comment = stripped_no_nl.lstrip().startswith(";")

        if is_helper_label(line):
            if cur_name is not None:
                out[cur_name] = "".join(cur_lines).rstrip() + "\n"
            cur_lines = pending_comments + [line]
            cur_name = line.lstrip()[:-2]
            pending_comments = []
        elif cur_name is None:
            # Header comments / blanks before first helper float forward.
            if is_comment or is_blank:
                pending_comments.append(line)
        else:
            if is_comment or is_blank:
                pending_comments.append(line)
            else:
                if pending_comments:
                    cur_lines.extend(pending_comments)
                    pending_comments = []
                cur_lines.append(line)

    if cur_name is not None:
        out[cur_name] = "".join(cur_lines).rstrip() + "\n"
    return out
