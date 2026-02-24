# Token definitions — see docs/language_spec.md for full language specification.

# All reserved keywords (Section 1.1)
KEYWORDS = {
    "uint32", "int", "float", "bool", "char", "void",
    "const",
    "if", "else", "while", "for", "break", "continue", "return",
}

# Single-character symbols (Section 1.2)
SYMBOLS_1 = {
    "+", "-", "*", "/", "%", "=", ";", ",", "(", ")", "{", "}",
    "[", "]", "<", ">", "!",
}

# Two-character symbols — must be checked before single-char (e.g. <= before <)
# Each entry: (first_char, full_two_char)
SYMBOLS_2 = {
    "<=", ">=", "==", "!=", "&&", "||", "++", "--",
}

# Set of all single chars that can start a two-char symbol (for lexer lookahead)
CHARS_STARTING_2 = {s[0] for s in SYMBOLS_2}

# Legacy: flat set of single symbols for backward compatibility
SYMBOLS = SYMBOLS_1

# Literal tokens
BOOL_LITERALS = {"true", "false"}
