import argparse
from pathlib import Path
from typing import Optional

from lexer.lexer import Lexer
from parser.parser import Parser
from symbol_table import SemanticError
from type_checker import TypeChecker
from ir import ast_to_ir, validate, IRValidationError
from optimizer import (
    constant_folding, dead_code_elimination, strength_reduction,
    cse, copy_propagation,
)
from viz import ast_to_dot, ir_linear_to_dot
from backend import RiscVBackend


def _write_output(target: Optional[str], contents: str) -> None:
    """
    Write DOT/text either to stdout (target is '-' or None) or to a file path.
    """
    if not target or target == "-":
        print(contents)
    else:
        path = Path(target)
        path.write_text(contents, encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> None:
    cli = argparse.ArgumentParser(description="Tiny compiler front-end with IR + visualization")
    cli.add_argument(
        "source",
        nargs="?",
        default="./samples/break_continue_exit.prog",
        help="Source program file (default: samples/break_continue_exit.prog)",
    )
    cli.add_argument(
        "--dump-ast-dot",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit AST as Graphviz DOT (to FILE or stdout if omitted)",
    )
    cli.add_argument(
        "--dump-ir-dot",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit linear IR graph as Graphviz DOT",
    )
    cli.add_argument(
        "--dump-ir-before",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit unoptimized IR as Graphviz DOT (to FILE or stdout if omitted)",
    )
    cli.add_argument(
        "--dump-ir-after-cf",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after constant folding only (Graphviz DOT)",
    )
    cli.add_argument(
        "--dump-ir-after-sr",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after strength reduction (Graphviz DOT)",
    )
    cli.add_argument(
        "--dump-ir-after-cse",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after CSE pass (Graphviz DOT)",
    )
    cli.add_argument(
        "--dump-ir-after-cp",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after copy propagation pass (Graphviz DOT)",
    )
    cli.add_argument(
        "--dump-ir-after",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit fully optimized IR (CF + SR + DCE + CSE + CP) as Graphviz DOT",
    )
    cli.add_argument(
        "--no-optimize",
        action="store_true",
        help="Disable optimization passes (constant folding, strength reduction, dead-code elimination, etc.)",
    )
    cli.add_argument(
        "--emit-asm",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit assembly to FILE (or stdout if omitted). "
             "Use --arch to select the target (default: riscv).",
    )
    cli.add_argument(
        "--arch",
        choices=["riscv", "x86_64"],
        default="riscv",
        help="Target for --emit-asm (default: riscv).",
    )
    cli.add_argument(
        "--emit-cpp",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit portable C++ (from IR); compile manually with g++/clang++.",
    )

    args = cli.parse_args(argv)
    log = print

    with open(args.source, encoding="utf-8") as f:
        code = f.read()

    lexer = Lexer(code)
    tokens = lexer.tokenize()

    log("TOKENS:")
    for t in tokens:
        log(t)

    log("-" * 80)

    errors = []
    parser = Parser(tokens, source_path=str(Path(args.source)))
    ast = parser.parse()
    for msg in parser.errors:
        errors.append(("syntax", msg))

    if ast is not None:
        log("\nAST:")
        log(ast)
        log("-" * 80)

        # Optional AST DOT dump.
        if args.dump_ast_dot is not None:
            dot = ast_to_dot(ast)
            _write_output(args.dump_ast_dot, dot)

        type_checker = TypeChecker()
        semantic_ok = False
        try:
            type_checker.analyze(ast)
            semantic_ok = True
        except SemanticError as e:
            errors.append(("semantic", str(e)))
        if semantic_ok:
            log("Semantic analysis OK")
            log("-" * 80)

    if errors:
        print("\nErrors:")
        for kind, msg in errors:
            print(f"  [{kind}] {msg}")
        return

    if ast is None:
        return

    ir_program = ast_to_ir(ast)
    try:
        validate(ir_program)
    except IRValidationError as e:
        print(
            f"IR validation error in {e.function_name or 'program'}"
            + (f" at instruction {e.instruction_index}" if e.instruction_index >= 0 else "")
            + f": {e}"
        )
        return
    log("IR validation OK")
    log("\nIR (before optimization):")
    log(ir_program)
    log("-" * 80)

    # IR visualization (unoptimized snapshot).
    if args.dump_ir_dot is not None:
        ir_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_dot, ir_dot)

    if args.dump_ir_before is not None:
        before_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_before, before_dot)

    optimized_program = ir_program
    if not args.no_optimize:
        cf_result = constant_folding(ir_program)
        after_cf_program = cf_result.program
        log(cf_result.summary())
        log("-" * 80)
        log("\nIR (after constant folding):")
        log(after_cf_program)
        log("-" * 80)

        if args.dump_ir_after_cf is not None:
            _write_output(args.dump_ir_after_cf, ir_linear_to_dot(after_cf_program))

        sr_result = strength_reduction(after_cf_program)
        after_sr_program = sr_result.program
        log(sr_result.summary())
        log("-" * 80)
        log("\nIR (after strength reduction):")
        log(after_sr_program)
        log("-" * 80)

        if args.dump_ir_after_sr is not None:
            _write_output(args.dump_ir_after_sr, ir_linear_to_dot(after_sr_program))

        dce_result = dead_code_elimination(after_sr_program)
        after_dce_program = dce_result.program
        log(dce_result.summary())
        log("-" * 80)
        log("\nIR (after dead code elimination):")
        log(after_dce_program)
        log("-" * 80)

        cse_result = cse(after_dce_program)
        after_cse_program = cse_result.program
        log(cse_result.summary())
        log("-" * 80)
        log("\nIR (after CSE):")
        log(after_cse_program)
        log("-" * 80)

        if args.dump_ir_after_cse is not None:
            _write_output(args.dump_ir_after_cse, ir_linear_to_dot(after_cse_program))

        cp_result = copy_propagation(after_cse_program)
        optimized_program = cp_result.program
        log(cp_result.summary())
        log("-" * 80)
        log("\nIR (after copy propagation):")
        log(optimized_program)
        log("-" * 80)

        if args.dump_ir_after_cp is not None:
            _write_output(args.dump_ir_after_cp, ir_linear_to_dot(optimized_program))

        # Final DCE sweep to clean up any temps made redundant by CSE / CP
        dce2 = dead_code_elimination(optimized_program)
        optimized_program = dce2.program
        if dce2.total_removed:
            log(f"Post-CP DCE: removed {dce2.total_removed} more instruction(s)")
            log(optimized_program)
            log("-" * 80)

        try:
            validate(optimized_program)
            log("IR validation OK (after all optimizations)")
        except IRValidationError as e:
            print(
                f"IR validation error after optimization in {e.function_name or 'program'}"
                + (f" at instruction {e.instruction_index}" if e.instruction_index >= 0 else "")
                + f": {e}"
            )
            return
    else:
        log("Optimizations skipped (--no-optimize).")

    if args.dump_ir_after is not None:
        after_dot = ir_linear_to_dot(optimized_program)
        _write_output(args.dump_ir_after, after_dot)

    need_asm = args.emit_asm is not None
    asm_text: Optional[str] = None
    if need_asm:
        if args.arch == "x86_64":
            from backend import X86_64Backend

            asm_text = X86_64Backend(optimized_program).generate()
        else:
            asm_text = RiscVBackend(optimized_program).generate()

    need_cpp = args.emit_cpp is not None
    cpp_text: Optional[str] = None
    if need_cpp:
        from backend.cpp_transpile import CppTranspileBackend

        cpp_text = CppTranspileBackend(optimized_program).generate()

    if args.emit_asm is not None:
        assert asm_text is not None
        _write_output(args.emit_asm, asm_text)
        if args.emit_asm != "-":
            print(f"Assembly written to: {args.emit_asm}  (arch={args.arch})")

    if args.emit_cpp is not None:
        assert cpp_text is not None
        _write_output(args.emit_cpp, cpp_text)
        if args.emit_cpp != "-":
            print(f"C++ written to: {args.emit_cpp}")


if __name__ == "__main__":
    main()
