from lexer.lexer import Lexer
from parser.parser import Parser, ParseError
from symbol_table import SemanticError
from type_checker import TypeChecker


def main():
    with open("./samples/simple.prog") as f:
        code = f.read()

    lexer = Lexer(code)
    tokens = lexer.tokenize()

    print("TOKENS:")
    for t in tokens:
        print(t)

    print("-" * 80)

    parser = Parser(tokens)
    try:
        ast = parser.parse()
    except ParseError as e:
        print("Syntax error:", e)
        return

    print("\nAST:")
    print(ast)

    print("-" * 80)
    type_checker = TypeChecker()
    try:
        type_checker.analyze(ast)
    except SemanticError as e:
        print("Semantic error:", e)
        return

    print("Semantic analysis OK")


if __name__ == "__main__":
    main()
