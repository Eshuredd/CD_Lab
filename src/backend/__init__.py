"""IR → assembly (RISC-V / x86-64) or C++ via ``backend.cpp_transpile`` / ``main --emit-cpp``."""

from .riscv import RiscVBackend

__all__ = ["RiscVBackend", "X86_64Backend"]


def __getattr__(name: str):
    if name == "X86_64Backend":
        from .x86_64 import X86_64Backend

        return X86_64Backend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
