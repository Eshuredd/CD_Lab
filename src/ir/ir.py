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
        parts = [self.op] + [self._arg_str(a) for a in self.args]
        return " ".join(parts)

    @staticmethod
    def _arg_str(a: Any) -> str:
        if isinstance(a, tuple):
            kind, val = a
            if kind == "string":
                return f'"{val}"'
            return f"({kind}:{val})"
        return str(a)


def CONST(dest: str, kind: str, value: Any) -> Instruction: # Constants
    return Instruction("CONST", [dest, (kind, value)])


def LOAD(dest: str, src: str) -> Instruction:
    return Instruction("LOAD", [dest, src])


def STORE(var: str, src: str) -> Instruction:
    return Instruction("STORE", [var, src])


def LOAD_ARR(dest: str, array: str, index: str) -> Instruction:
    return Instruction("LOAD_ARR", [dest, array, index])


def STORE_ARR(array: str, index: str, src: str) -> Instruction:
    return Instruction("STORE_ARR", [array, index, src])


def ALLOC_ARRAY(name: str, size: int) -> Instruction: # Allocate array with constant size
    return Instruction("ALLOC_ARRAY", [name, size])


def ADD(dest: str, left: str, right: str) -> Instruction:
    return Instruction("ADD", [dest, left, right])


def SUB(dest: str, left: str, right: str) -> Instruction:
    return Instruction("SUB", [dest, left, right])


def MUL(dest: str, left: str, right: str) -> Instruction:
    return Instruction("MUL", [dest, left, right])


def DIV(dest: str, left: str, right: str) -> Instruction:
    return Instruction("DIV", [dest, left, right])


def MOD(dest: str, left: str, right: str) -> Instruction:   
    return Instruction("MOD", [dest, left, right])


def NEG(dest: str, src: str) -> Instruction:
    return Instruction("NEG", [dest, src])


def INC(dest: str, src: str) -> Instruction: # Increment by 1
    return Instruction("INC", [dest, src])


def DEC(dest: str, src: str) -> Instruction: # Decrement by 1
    return Instruction("DEC", [dest, src])


def LT(dest: str, left: str, right: str) -> Instruction: # Less than
    return Instruction("LT", [dest, left, right])


def LE(dest: str, left: str, right: str) -> Instruction: # Less than or equal to
    return Instruction("LE", [dest, left, right])


def GT(dest: str, left: str, right: str) -> Instruction: # Greater than
    return Instruction("GT", [dest, left, right])


def GE(dest: str, left: str, right: str) -> Instruction: # Greater than or equal to
    return Instruction("GE", [dest, left, right])


def EQ(dest: str, left: str, right: str) -> Instruction: # Equal to
    return Instruction("EQ", [dest, left, right])


def NE(dest: str, left: str, right: str) -> Instruction: # Not equal to
    return Instruction("NE", [dest, left, right])


def AND(dest: str, left: str, right: str) -> Instruction: 
    return Instruction("AND", [dest, left, right])


def OR(dest: str, left: str, right: str) -> Instruction:
    return Instruction("OR", [dest, left, right])


def NOT(dest: str, src: str) -> Instruction:
    return Instruction("NOT", [dest, src])


def LABEL(name: str) -> Instruction:
    return Instruction("LABEL", [name])


def JMP(label: str) -> Instruction:
    return Instruction("JMP", [label])


def JMP_IF(cond: str, label: str) -> Instruction:
    return Instruction("JMP_IF", [cond, label])


def JMP_IF_NOT(cond: str, label: str) -> Instruction:
    return Instruction("JMP_IF_NOT", [cond, label])


def PARAM(src: str) -> Instruction:
    return Instruction("PARAM", [src])


def CALL(dest: Optional[str], name: str, num_args: int = 0) -> Instruction:
    return Instruction("CALL", [dest if dest is not None else "", name, num_args])


def RET(value: Optional[str]) -> Instruction:
    return Instruction("RET", [value if value is not None else ""])


def PRINT(args: List[str]) -> Instruction:
    return Instruction("PRINT", list(args))


def READ_INT(dest: str) -> Instruction:
    return Instruction("READ_INT", [dest])


def EXIT(code: str) -> Instruction:
    return Instruction("EXIT", [code])


def FUNC_ENTRY(name: str, return_type: str, param_names: List[str]) -> Instruction:
    return Instruction("FUNC_ENTRY", [name, return_type] + param_names)


@dataclass
class IRFunction:
    name: str
    return_type: str
    param_names: List[str]
    param_types: List[str]
    instructions: List[Instruction] = field(default_factory=list)

    def __repr__(self) -> str:
        lines = [f"FUNC {self.name}({', '.join(self.param_names)}) -> {self.return_type}"]
        for insn in self.instructions:
            lines.append("  " + repr(insn))
        return "\n".join(lines)


@dataclass
class IRProgram:
    functions: List[IRFunction] = field(default_factory=list)

    def __repr__(self) -> str:
        return "\n\n".join(repr(f) for f in self.functions)
