"""Reserved words and punctuation for the lexer (see docs/language_spec.md)."""

KEYWORDS = {
    "uint32", "int", "float", "bool", "char", "void", "const",
    "if", "else", "while", "for", "break", "continue", "return",
}
SYMBOLS_1 = {
    "+", "-", "*", "/", "%", "=", ";", ",", "(", ")", "{", "}",
    "[", "]", "<", ">", "!",
}
SYMBOLS_2 = {"<=", ">=", "==", "!=", "&&", "||", "++", "--"}
CHARS_STARTING_2 = {s[0] for s in SYMBOLS_2}
BOOL_LITERALS = {"true", "false"}
