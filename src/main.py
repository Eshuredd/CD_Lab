from lexer.lexer import Lexer
from parser.parser import Parser, ParseError
from semantic import SemanticAnalyzer, SemanticError


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
    analyzer = SemanticAnalyzer()
    try:
        analyzer.analyze(ast)
    except SemanticError as e:
        print("Semantic error:", e)
        return

    print("Semantic analysis OK")


if __name__ == "__main__":
    main()
