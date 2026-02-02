from lexer.lexer import Lexer
from parser.parser import Parser


code = open("test.prog").read()
lexer = Lexer(code)
tokens = lexer.tokenize()

print("TOKENS:")
for t in tokens:
    print(t)

print("---------------------------------------------------------------------------------")
parser = Parser(tokens)
ast = parser.parse()

print("\nAST:")
for node in ast:
    print(node)
