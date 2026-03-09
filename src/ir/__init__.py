"""IR (Intermediate Representation) module: linear IR format, AST-to-IR translation, and validation."""

from .ir import (
    Instruction,
    IRProgram,
    IRFunction,
    Operand,
)
from .ast_to_ir import ast_to_ir, IRBuilder
from .ir_validator import validate, IRValidationError

__all__ = [
    "Instruction",
    "IRProgram",
    "IRFunction",
    "Operand",
    "ast_to_ir",
    "IRBuilder",
    "validate",
    "IRValidationError",
]
