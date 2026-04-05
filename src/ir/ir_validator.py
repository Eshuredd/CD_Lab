"""IR validation: labels, use-before-def, PARAM/CALL match, RET rules."""

from __future__ import annotations
from typing import List, Set

from .ir import IRProgram, IRFunction, Instruction

BUILTINS = {"print", "readInt", "exit"}

_BIN = {
    "ADD", "SUB", "MUL", "DIV", "MOD", "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR",
}
_UNARY = {"NEG", "NOT", "INC", "DEC"}


class IRValidationError(Exception):
    def __init__(self, msg: str, function_name: str = "", instruction_index: int = -1):
        self.function_name = function_name
        self.instruction_index = instruction_index
        super().__init__(msg)


def _used(ins: Instruction) -> List[str]:
    o, a = ins.op, ins.args
    if o == "LOAD":
        return [a[1]]
    if o == "STORE":
        return [a[1]]
    if o == "LOAD_ARR":
        return [a[1], a[2]]
    if o == "STORE_ARR":
        return [a[0], a[1], a[2]]
    if o in _BIN:
        return [a[1], a[2]]
    if o in _UNARY:
        return [a[1]]
    if o in ("JMP_IF", "JMP_IF_NOT"):
        return [a[0]]
    if o == "PARAM":
        return [a[0]]
    if o == "RET" and a[0]:
        return [a[0]]
    if o == "PRINT":
        return list(a)
    if o == "EXIT":
        return [a[0]]
    return []


def _defined(ins: Instruction) -> List[str]:
    o, a = ins.op, ins.args or []
    if o == "CONST":
        return [a[0]]
    if o in ("LOAD", "LOAD_ARR", "READ_INT"):
        return [a[0]]
    if o == "STORE":
        return [a[0]]
    if o == "ALLOC_ARRAY":
        return [a[0]]
    if o in _BIN or o in _UNARY:
        return [a[0]]
    if o == "CALL" and a[0]:
        return [a[0]]
    return []


def _validate_function(func: IRFunction, known: Set[str]) -> None:
    insns = func.instructions
    labels: Set[str] = set()
    for i, ins in enumerate(insns):
        if ins.op == "LABEL":
            n = ins.args[0]
            if n in labels:
                raise IRValidationError(f"Duplicate label: {n}", func.name, i)
            labels.add(n)

    defined: Set[str] = set(func.param_names)
    pc = 0

    for i, ins in enumerate(insns):
        o, a = ins.op, ins.args
        if o == "LABEL":
            continue
        if o == "JMP" and a[0] not in labels:
            raise IRValidationError(f"Jump to undefined label: {a[0]}", func.name, i)
        if o in ("JMP_IF", "JMP_IF_NOT"):
            if a[1] not in labels:
                raise IRValidationError(f"Branch to undefined label: {a[1]}", func.name, i)
            if a[0] not in defined:
                raise IRValidationError(f"Branch condition '{a[0]}' used before definition", func.name, i)

        if o == "PARAM":
            pc += 1
            if a[0] not in defined:
                raise IRValidationError(f"PARAM source '{a[0]}' used before definition", func.name, i)
            continue

        if o == "CALL":
            dest, callee, n = a[0], a[1], a[2]
            if pc != n:
                raise IRValidationError(
                    f"CALL {callee} expects {n} arguments but {pc} PARAM(s) given", func.name, i
                )
            pc = 0
            if callee not in known and callee not in BUILTINS:
                raise IRValidationError(f"CALL to unknown function: {callee}", func.name, i)
            for u in _used(ins):
                if u not in defined:
                    raise IRValidationError(f"Operand '{u}' used before definition", func.name, i)
            for d in _defined(ins):
                defined.add(d)
            continue

        if o == "RET":
            rv = a[0]
            if func.return_type == "void" and rv:
                raise IRValidationError("void function must not return a value", func.name, i)
            if func.return_type != "void":
                if not rv:
                    raise IRValidationError(
                        f"Non-void function must return a value (type {func.return_type})",
                        func.name,
                        i,
                    )
                if rv not in defined:
                    raise IRValidationError(f"Return value '{rv}' used before definition", func.name, i)
            continue

        for u in _used(ins):
            if u not in defined:
                raise IRValidationError(f"Operand '{u}' used before definition", func.name, i)
        for d in _defined(ins):
            defined.add(d)


def validate(program: IRProgram) -> None:
    known = {f.name for f in program.functions} | BUILTINS
    for fn in program.functions:
        _validate_function(fn, known)
