import argparse
from pathlib import Path
from typing import Optional

from lexer.lexer import Lexer
from parser.parser import Parser
from symbol_table import SemanticError
from type_checker import TypeChecker
from ir import ast_to_ir, validate, IRValidationError
from optimizer import constant_folding, dead_code_elimination, strength_reduction
from viz import ast_to_dot, ir_linear_to_dot
from backend import X86_64Backend, RiscVBackend


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
    # Forward-looking flags for pre/post optimization IR snapshots.
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
        "--dump-ir-after",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit fully optimized IR (CF + strength reduction + DCE) as Graphviz DOT",
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
        help="Target architecture for --emit-asm (default: riscv).",
    )

    args = cli.parse_args(argv)

    with open(args.source, encoding="utf-8") as f:
        code = f.read()

    lexer = Lexer(code)
    tokens = lexer.tokenize()

    print("TOKENS:")
    for t in tokens:
        print(t)

    print("-" * 80)

    errors = []
    parser = Parser(tokens, source_path=str(Path(args.source)))
    ast = parser.parse()
    for msg in parser.errors:
        errors.append(("syntax", msg))

    if ast is not None:
        print("\nAST:")
        print(ast)
        print("-" * 80)

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
            print("Semantic analysis OK")
            print("-" * 80)

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
    print("IR validation OK")
    print("\nIR (before optimization):")
    print(ir_program)
    print("-" * 80)

    # IR visualization (unoptimized snapshot).
    if args.dump_ir_dot is not None:
        ir_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_dot, ir_dot)

    if args.dump_ir_before is not None:
        before_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_before, before_dot)

    # ------------------------------------------------------------------
    # Optimization passes
    # ------------------------------------------------------------------
    optimized_program = ir_program
    if not args.no_optimize:
        cf_result = constant_folding(ir_program)
        after_cf_program = cf_result.program
        print(cf_result.summary())
        print("-" * 80)
        print("\nIR (after constant folding):")
        print(after_cf_program)
        print("-" * 80)

        if args.dump_ir_after_cf is not None:
            _write_output(args.dump_ir_after_cf, ir_linear_to_dot(after_cf_program))

        sr_result = strength_reduction(after_cf_program)
        after_sr_program = sr_result.program
        print(sr_result.summary())
        print("-" * 80)
        print("\nIR (after strength reduction):")
        print(after_sr_program)
        print("-" * 80)

        if args.dump_ir_after_sr is not None:
            _write_output(args.dump_ir_after_sr, ir_linear_to_dot(after_sr_program))

        dce_result = dead_code_elimination(after_sr_program)
        optimized_program = dce_result.program
        print(dce_result.summary())
        print("-" * 80)
        try:
            validate(optimized_program)
            print("IR validation OK (after optimizations)")
        except IRValidationError as e:
            print(
                f"IR validation error after optimization in {e.function_name or 'program'}"
                + (f" at instruction {e.instruction_index}" if e.instruction_index >= 0 else "")
                + f": {e}"
            )
            return
        print("-" * 80)
        print("\nIR (after dead code elimination):")
        print(optimized_program)
        print("-" * 80)
    else:
        print("Optimizations skipped (--no-optimize).")

    if args.dump_ir_after is not None:
        after_dot = ir_linear_to_dot(optimized_program)
        _write_output(args.dump_ir_after, after_dot)

    if args.emit_asm is not None:
        if args.arch == "x86_64":
            asm_text = X86_64Backend(optimized_program).generate()
        else:
            asm_text = RiscVBackend(optimized_program).generate()
        _write_output(args.emit_asm, asm_text)
        if args.emit_asm and args.emit_asm != "-":
            print(f"Assembly written to: {args.emit_asm}  (arch={args.arch})")


if __name__ == "__main__":
    main()
