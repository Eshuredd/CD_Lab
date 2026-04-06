"""Optimizer module: IR optimization passes."""

from .constant_folding import constant_folding, ConstantFoldingResult
from .dead_code_elimination import dead_code_elimination, DeadCodeEliminationResult
from .strength_reduction import strength_reduction, StrengthReductionResult
from .cse import cse, CSEResult
from .copy_propagation import copy_propagation, CopyPropagationResult

__all__ = [
    "constant_folding",
    "ConstantFoldingResult",
    "dead_code_elimination",
    "DeadCodeEliminationResult",
    "strength_reduction",
    "StrengthReductionResult",
    "cse",
    "CSEResult",
    "copy_propagation",
    "CopyPropagationResult",
]
