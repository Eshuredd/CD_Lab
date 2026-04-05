"""Linear IR: instructions, helpers, and program containers."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

Operand = Union[str, tuple]


def is_temp(s: str) -> bool:
    return isinstance(s, str) and s.startswith("%")


def is_label(s: str) -> bool:
    return isinstance(s, str) and s.startswith("L") and len(s) > 1 and s[1:].isdigit()


@dataclass
class Instruction:
    op: str
    args: List[Any] = field(default_factory=list)

    def __repr__(self) -> str:
        parts = [self.op] + [self._fmt(a) for a in self.args]
        return " ".join(parts)

    @staticmethod
    def _fmt(a: Any) -> str:
        if isinstance(a, tuple):
            k, v = a
            return f'"{v}"' if k == "string" else f"({k}:{v})"
        return str(a)


def I(op: str, *args: Any) -> Instruction:
    return Instruction(op, list(args))


def CONST(d: str, k: str, v: Any) -> Instruction:
    return I("CONST", d, (k, v))


def LOAD(d: str, s: str) -> Instruction:
    return I("LOAD", d, s)


def STORE(v: str, s: str) -> Instruction:
    return I("STORE", v, s)


def LOAD_ARR(d: str, arr: str, idx: str) -> Instruction:
    return I("LOAD_ARR", d, arr, idx)


def STORE_ARR(arr: str, idx: str, s: str) -> Instruction:
    return I("STORE_ARR", arr, idx, s)


def ALLOC_ARRAY(name: str, size: int) -> Instruction:
    return I("ALLOC_ARRAY", name, size)


def ADD(d: str, l: str, r: str) -> Instruction:
    return I("ADD", d, l, r)


def SUB(d: str, l: str, r: str) -> Instruction:
    return I("SUB", d, l, r)


def MUL(d: str, l: str, r: str) -> Instruction:
    return I("MUL", d, l, r)


def DIV(d: str, l: str, r: str) -> Instruction:
    return I("DIV", d, l, r)


def MOD(d: str, l: str, r: str) -> Instruction:
    return I("MOD", d, l, r)


def NEG(d: str, s: str) -> Instruction:
    return I("NEG", d, s)


def INC(d: str, s: str) -> Instruction:
    return I("INC", d, s)


def DEC(d: str, s: str) -> Instruction:
    return I("DEC", d, s)


def LT(d: str, l: str, r: str) -> Instruction:
    return I("LT", d, l, r)


def LE(d: str, l: str, r: str) -> Instruction:
    return I("LE", d, l, r)


def GT(d: str, l: str, r: str) -> Instruction:
    return I("GT", d, l, r)


def GE(d: str, l: str, r: str) -> Instruction:
    return I("GE", d, l, r)


def EQ(d: str, l: str, r: str) -> Instruction:
    return I("EQ", d, l, r)


def NE(d: str, l: str, r: str) -> Instruction:
    return I("NE", d, l, r)


def AND(d: str, l: str, r: str) -> Instruction:
    return I("AND", d, l, r)


def OR(d: str, l: str, r: str) -> Instruction:
    return I("OR", d, l, r)


def NOT(d: str, s: str) -> Instruction:
    return I("NOT", d, s)


def LABEL(name: str) -> Instruction:
    return I("LABEL", name)


def JMP(lbl: str) -> Instruction:
    return I("JMP", lbl)


def JMP_IF(c: str, lbl: str) -> Instruction:
    return I("JMP_IF", c, lbl)


def JMP_IF_NOT(c: str, lbl: str) -> Instruction:
    return I("JMP_IF_NOT", c, lbl)


def PARAM(s: str) -> Instruction:
    return I("PARAM", s)


def CALL(d: Optional[str], name: str, n: int = 0) -> Instruction:
    return I("CALL", d if d is not None else "", name, n)


def RET(v: Optional[str]) -> Instruction:
    return I("RET", v if v is not None else "")


def PRINT(xs: List[str]) -> Instruction:
    return I("PRINT", *xs)


def READ_INT(d: str) -> Instruction:
    return I("READ_INT", d)


def EXIT(code: str) -> Instruction:
    return I("EXIT", code)


def FUNC_ENTRY(name: str, rt: str, params: List[str]) -> Instruction:
    return I("FUNC_ENTRY", name, rt, *params)


@dataclass
class IRFunction:
    name: str
    return_type: str
    param_names: List[str]
    param_types: List[str]
    instructions: List[Instruction] = field(default_factory=list)

    def __repr__(self) -> str:
        h = f"FUNC {self.name}({', '.join(self.param_names)}) -> {self.return_type}"
        return "\n".join([h] + ["  " + repr(i) for i in self.instructions])


@dataclass
class IRProgram:
    functions: List[IRFunction] = field(default_factory=list)

    def __repr__(self) -> str:
        return "\n\n".join(repr(f) for f in self.functions)
