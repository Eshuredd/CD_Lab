import argparse
from pathlib import Path
from typing import Optional

from lexer.lexer import Lexer
from parser.parser import Parser
from symbol_table import SemanticError
from type_checker import TypeChecker
from ir import ast_to_ir, validate, IRValidationError
from viz import ast_to_dot, ir_linear_to_dot


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
        help="Emit IR (before optimizations) as Graphviz DOT (alias of --dump-ir-dot for now)",
    )
    cli.add_argument(
        "--dump-ir-after",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR (after optimizations) as Graphviz DOT (currently same as before; no passes yet)",
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
    parser = Parser(tokens)
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
    print("IR:")
    print(ir_program)

    # IR visualization.
    if args.dump_ir_dot is not None:
        ir_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_dot, ir_dot)

    # For now, before/after are identical because there are no optimization passes yet.
    if args.dump_ir_before is not None:
        before_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_before, before_dot)

    if args.dump_ir_after is not None:
        after_dot = ir_linear_to_dot(ir_program)
        _write_output(args.dump_ir_after, after_dot)


if __name__ == "__main__":
    main()
