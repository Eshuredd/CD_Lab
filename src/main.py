from lexer.lexer import Lexer
from parser.parser import Parser
from symbol_table import SemanticError
from type_checker import TypeChecker
from ir import ast_to_ir, validate, IRValidationError


def main():
    with open("./samples/break_continue_exit.prog") as f:
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
        print(f"IR validation error in {e.function_name or 'program'}" + (
            f" at instruction {e.instruction_index}" if e.instruction_index >= 0 else ""
        ) + f": {e}")
        return
    print("IR validation OK")
    print("IR:")
    print(ir_program)


if __name__ == "__main__":
    main()
