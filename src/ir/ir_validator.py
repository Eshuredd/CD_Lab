"""
IR Validation: control-flow correctness and execution semantics.

Validates that:
- All branch targets (JMP, JMP_IF, JMP_IF_NOT) reference defined labels.
- No duplicate labels per function.
- Every used temporary or variable is defined before use.
- PARAM count matches CALL arity.
- RET has a value for non-void functions and no value for void.
- CALL targets are known functions (builtins or defined in program).
"""

from __future__ import annotations
from typing import Set, List

from .ir import (
    IRProgram,
    IRFunction,
    Instruction,
)

# Built-in functions
BUILTINS = {"print", "readInt", "exit"}


class IRValidationError(Exception):
    """Raised when IR validation fails."""

    def __init__(self, message: str, function_name: str = "", instruction_index: int = -1):
        self.function_name = function_name
        self.instruction_index = instruction_index
        super().__init__(message)


def _get_operands_used(insn: Instruction) -> List[str]:
    """Return list of temp/variable operands that must be defined before this instruction."""
    op, args = insn.op, insn.args
    used: List[str] = []
    if op == "CONST":
        pass
    elif op in ("LOAD", "READ_INT"):
        # dest, [src for LOAD]
        if op == "LOAD":
            used.append(args[1])
    elif op == "STORE":
        used.append(args[1])
    elif op == "LOAD_ARR":
        # [dest, array, index]
        used.append(args[1])
        used.append(args[2])
    elif op == "STORE_ARR":
        # [array, index, src]
        used.append(args[0])
        used.append(args[1])
        used.append(args[2])
    elif op in ("ADD", "SUB", "MUL", "DIV", "MOD", "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR"):
        used.extend([args[1], args[2]])
    elif op in ("NEG", "NOT", "INC", "DEC"):
        used.append(args[1])
    elif op in ("JMP_IF", "JMP_IF_NOT"):
        used.append(args[0])  # cond
    elif op == "PARAM":
        used.append(args[0])
    elif op == "CALL":
        pass
    elif op == "RET":
        if args[0]:
            used.append(args[0])
    elif op == "PRINT":
        used.extend(args)
    elif op == "EXIT":
        used.append(args[0])
    elif op in ("LABEL", "JMP", "FUNC_ENTRY", "ALLOC_ARRAY"):
        pass
    return used


def _get_operands_defined(insn: Instruction) -> List[str]:
    """Return list of temp/variable names defined by this instruction."""
    op, args = insn.op, insn.args or []
    defined: List[str] = []
    if op == "CONST":
        defined.append(args[0])
    elif op in ("LOAD", "LOAD_ARR", "READ_INT"):
        defined.append(args[0])
    elif op == "STORE":
        defined.append(args[0])  # variable is written
    elif op == "ALLOC_ARRAY":
        defined.append(args[0])  # array name
    elif op in ("ADD", "SUB", "MUL", "DIV", "MOD", "NEG", "INC", "DEC",
                "LT", "LE", "GT", "GE", "EQ", "NE", "AND", "OR", "NOT"):
        defined.append(args[0])
    elif op == "CALL":
        if args[0]:  # non-void return
            defined.append(args[0])
    return defined


def _validate_function(func: IRFunction, known_functions: Set[str]) -> None:
    """Validate one IR function. Raises IRValidationError on first error."""
    insns = func.instructions

    # First pass: collect all labels and check for duplicates
    labels: Set[str] = set()
    for i, insn in enumerate(insns):
        if insn.op == "LABEL":
            label_name = insn.args[0]
            if label_name in labels:
                raise IRValidationError(
                    f"Duplicate label: {label_name}",
                    func.name,
                    i,
                )
            labels.add(label_name)

    # Second pass: use-def and control flow
    defined: Set[str] = set(func.param_names)
    param_count = 0

    for i, insn in enumerate(insns):
        op, args = insn.op, insn.args

        if op == "LABEL":
            continue

        if op == "JMP":
            target = args[0]
            if target not in labels:
                raise IRValidationError(
                    f"Jump to undefined label: {target}",
                    func.name,
                    i,
                )
        elif op in ("JMP_IF", "JMP_IF_NOT"):
            cond, target = args[0], args[1]
            if target not in labels:
                raise IRValidationError(
                    f"Branch to undefined label: {target}",
                    func.name,
                    i,
                )
            if cond not in defined:
                raise IRValidationError(
                    f"Branch condition '{cond}' used before definition",
                    func.name,
                    i,
                )

        if op == "PARAM":
            param_count += 1
            src = args[0]
            if src not in defined:
                raise IRValidationError(
                    f"PARAM source '{src}' used before definition",
                    func.name,
                    i,
                )
            continue
        if op == "CALL":
            dest, callee, num_args = args[0], args[1], args[2]
            if param_count != num_args:
                raise IRValidationError(
                    f"CALL {callee} expects {num_args} arguments but {param_count} PARAM(s) given",
                    func.name,
                    i,
                )
            param_count = 0
            if callee not in known_functions and callee not in BUILTINS:
                raise IRValidationError(
                    f"CALL to unknown function: {callee}",
                    func.name,
                    i,
                )
            if dest and dest not in defined:
                # dest is being defined by this CALL, not used
                pass
            for u in _get_operands_used(insn):
                if u not in defined:
                    raise IRValidationError(
                        f"Operand '{u}' used before definition",
                        func.name,
                        i,
                    )
            for d in _get_operands_defined(insn):
                defined.add(d)
            continue

        # --- RET ---
        if op == "RET":
            ret_val = args[0]
            if func.return_type == "void":
                if ret_val:
                    raise IRValidationError(
                        "void function must not return a value",
                        func.name,
                        i,
                    )
            else:
                if not ret_val:
                    raise IRValidationError(
                        f"Non-void function must return a value (type {func.return_type})",
                        func.name,
                        i,
                    )
                if ret_val not in defined:
                    raise IRValidationError(
                        f"Return value '{ret_val}' used before definition",
                        func.name,
                        i,
                    )
            continue

        for u in _get_operands_used(insn):
            if u not in defined:
                raise IRValidationError(
                    f"Operand '{u}' used before definition",
                    func.name,
                    i,
                )

        for d in _get_operands_defined(insn):
            defined.add(d)


def validate(program: IRProgram) -> None:
    """
    Validate entire IR program.
    Raises IRValidationError on first validation failure.
    """
    known = {f.name for f in program.functions} | BUILTINS

    for func in program.functions:
        _validate_function(func, known)
