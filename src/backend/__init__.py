"""IR → assembly: RV32+ecall (Ripes) or NASM+syscalls (bare ld), or C++ via ``cpp_transpile`` / ``--emit-cpp``."""

from .riscv import RiscVBackend

__all__ = ["RiscVBackend", "X86_64Backend"]


def __getattr__(name: str):
    if name == "X86_64Backend":
        from .x86_64 import X86_64Backend

        return X86_64Backend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
