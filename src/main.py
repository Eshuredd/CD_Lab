import argparse
from pathlib import Path
from typing import Optional

from lexer.lexer import Lexer
from parser.parser import Parser
from symbol_table import SemanticError
from type_checker import TypeChecker
from unused_warnings import unused_variable_warnings
from ir import ast_to_ir, validate, IRValidationError
from optimizer import (
    constant_folding, constant_propagation, dead_code_elimination,
    strength_reduction, cse, copy_propagation, peephole, basic_block_opt,
)
from viz import ast_to_dot, ir_linear_to_dot, cfg_to_dot
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
    all_optim_passes = ["cf", "cprop", "sr", "dce", "cse", "cp", "peephole", "bb", "dce2"]
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
        "--dump-ir-after-cprop",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after constant propagation pass (Graphviz DOT)",
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
        "--dump-ir-after-peephole",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after peephole pass (Graphviz DOT)",
    )
    cli.add_argument(
        "--dump-ir-after-bb",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit IR after basic-block optimization pass (Graphviz DOT)",
    )
    cli.add_argument(
        "--dump-ir-after",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit fully optimized IR (CF + CProp + SR + DCE + CSE + CP + peephole + BB) as Graphviz DOT",
    )
    cli.add_argument(
        "--dump-cfg-dot",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Emit control-flow graph (basic blocks) as Graphviz DOT for final IR",
    )
    cli.add_argument(
        "--no-optimize",
        action="store_true",
        help="Disable optimization passes (constant folding, strength reduction, dead-code elimination, etc.)",
    )
    cli.add_argument(
        "--optim",
        metavar="LIST",
        default="all",
        help=(
            "Comma-separated optimization pass list (default: all). "
            "Use 'none' to disable. "
            "Available: cf,cprop,sr,dce,cse,cp,peephole,bb,dce2"
        ),
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
        help=(
            "Target for --emit-asm (default: riscv).\n"
            "  riscv  = RV32IM + ecall I/O for Ripes (ripes.me).\n"
            "  x86_64 = NASM + Linux syscalls only (nasm+ld / online compilers; no libc)."
        ),
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

    raw_optim = args.optim.strip().lower()
    if raw_optim == "all":
        selected_optim_passes = set(all_optim_passes)
    elif raw_optim in {"none", ""}:
        selected_optim_passes = set()
    else:
        selected_optim_passes = {
            p.strip() for p in raw_optim.split(",") if p.strip()
        }
        unknown = sorted(selected_optim_passes - set(all_optim_passes))
        if unknown:
            cli.error(
                "Unknown pass name(s) in --optim: "
                + ", ".join(unknown)
                + ". Available: "
                + ",".join(all_optim_passes)
            )

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
            for wmsg in unused_variable_warnings(ast, source_path=str(Path(args.source))):
                print(wmsg)

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
    if not args.no_optimize and selected_optim_passes:
        current_program = ir_program

        if "cf" in selected_optim_passes:
            cf_result = constant_folding(current_program)
            current_program = cf_result.program
            log(cf_result.summary())
            log("-" * 80)
            log("\nIR (after constant folding):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_cf is not None:
            _write_output(args.dump_ir_after_cf, ir_linear_to_dot(current_program))

        if "cprop" in selected_optim_passes:
            # Iterate constant propagation (+ optional re-folding) to a fixed point.
            cprop_total = 0
            post_fold_total = 0
            while True:
                cprop_result = constant_propagation(current_program)
                current_program = cprop_result.program
                cprop_total += cprop_result.total_propagated
                if cprop_result.total_propagated == 0:
                    break
                if "cf" in selected_optim_passes:
                    cf_iter = constant_folding(current_program)
                    current_program = cf_iter.program
                    post_fold_total += cf_iter.total_folds
                    if cf_iter.total_folds == 0:
                        break
                else:
                    break

            log(
                "Constant Propagation Pass:\n"
                f"  Total: {cprop_total} propagation(s); "
                f"{post_fold_total} additional fold(s) from re-folding propagated CONSTs"
            )
            log("-" * 80)
            log("\nIR (after constant propagation):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_cprop is not None:
            _write_output(
                args.dump_ir_after_cprop, ir_linear_to_dot(current_program)
            )

        if "sr" in selected_optim_passes:
            sr_result = strength_reduction(current_program)
            current_program = sr_result.program
            log(sr_result.summary())
            log("-" * 80)
            log("\nIR (after strength reduction):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_sr is not None:
            _write_output(args.dump_ir_after_sr, ir_linear_to_dot(current_program))

        if "dce" in selected_optim_passes:
            dce_result = dead_code_elimination(current_program)
            current_program = dce_result.program
            log(dce_result.summary())
            log("-" * 80)
            log("\nIR (after dead code elimination):")
            log(current_program)
            log("-" * 80)

        if "cse" in selected_optim_passes:
            cse_result = cse(current_program)
            current_program = cse_result.program
            log(cse_result.summary())
            log("-" * 80)
            log("\nIR (after CSE):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_cse is not None:
            _write_output(args.dump_ir_after_cse, ir_linear_to_dot(current_program))

        if "cp" in selected_optim_passes:
            cp_result = copy_propagation(current_program)
            current_program = cp_result.program
            log(cp_result.summary())
            log("-" * 80)
            log("\nIR (after copy propagation):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_cp is not None:
            _write_output(args.dump_ir_after_cp, ir_linear_to_dot(current_program))

        if "peephole" in selected_optim_passes:
            ph_result = peephole(current_program)
            current_program = ph_result.program
            log(ph_result.summary())
            log("-" * 80)
            log("\nIR (after peephole):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_peephole is not None:
            _write_output(
                args.dump_ir_after_peephole, ir_linear_to_dot(current_program)
            )

        if "bb" in selected_optim_passes:
            bb_result = basic_block_opt(current_program)
            current_program = bb_result.program
            log(bb_result.summary())
            log("-" * 80)
            log("\nIR (after basic-block optimization):")
            log(current_program)
            log("-" * 80)

        if args.dump_ir_after_bb is not None:
            _write_output(args.dump_ir_after_bb, ir_linear_to_dot(current_program))

        # Optional final DCE sweep after late structural optimizations.
        if "dce2" in selected_optim_passes:
            dce2 = dead_code_elimination(current_program)
            current_program = dce2.program
            if dce2.total_removed:
                log(f"Post-CP DCE: removed {dce2.total_removed} more instruction(s)")
                log(current_program)
                log("-" * 80)

        optimized_program = current_program

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
        log("Optimizations skipped (--no-optimize or --optim=none).")

    if args.dump_ir_after is not None:
        after_dot = ir_linear_to_dot(optimized_program)
        _write_output(args.dump_ir_after, after_dot)

    if args.dump_cfg_dot is not None:
        _write_output(args.dump_cfg_dot, cfg_to_dot(optimized_program))

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
