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

# Convenience re-export so callers can do: from ir import constant_folding
from optimizer.constant_folding import constant_folding, ConstantFoldingResult  # noqa: E402
from optimizer.dead_code_elimination import dead_code_elimination, DeadCodeEliminationResult  # noqa: E402
from optimizer.strength_reduction import strength_reduction, StrengthReductionResult  # noqa: E402

__all__ += [
    "constant_folding",
    "ConstantFoldingResult",
    "dead_code_elimination",
    "DeadCodeEliminationResult",
    "strength_reduction",
    "StrengthReductionResult",
]
