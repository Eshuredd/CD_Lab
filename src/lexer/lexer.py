from .tokens import KEYWORDS, SYMBOLS_1, SYMBOLS_2, CHARS_STARTING_2, BOOL_LITERALS


class Token:
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def __repr__(self):
        return f"{self.type}: {self.value}"


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def peek(self, offset=0):
        i = self.pos + offset
        return self.text[i] if i < len(self.text) else None
    def peek(self, offset=0):
        i = self.pos + offset
        return self.text[i] if i < len(self.text) else None

    def tokenize(self):
        tokens = []

        while self.pos < len(self.text):
            ch = self.text[self.pos]

            if ch.isspace():
                self.pos += 1
                continue

            if ch == "/" and self.peek() == "/":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
                continue

            if ch.isalpha():
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos].isalnum():
                    self.pos += 1
                word = self.text[start : self.pos]
                if word in BOOL_LITERALS:
                    tokens.append(Token("BOOL_LIT", word))
                elif word in KEYWORDS:
                    tokens.append(Token("KEYWORD", word))
                else:
                    tokens.append(Token("IDENTIFIER", word))
                continue

            # Number or float literal
            if ch.isdigit():
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos].isdigit():
                    self.pos += 1
                if self.peek() == "." and self.peek(1) is not None and self.peek(1).isdigit():
                    self.pos += 1  # consume '.'
                    while self.pos < len(self.text) and self.text[self.pos].isdigit():
                        self.pos += 1
                    tokens.append(Token("FLOAT_LIT", self.text[start : self.pos]))
                else:
                    tokens.append(Token("NUMBER", self.text[start : self.pos]))
                continue

            # String literal (double-quoted)
            if ch == '"':
                start = self.pos + 1
                self.pos += 1
                while self.pos < len(self.text) and self.text[self.pos] != '"':
                    if self.text[self.pos] == "\\":
                        self.pos += 2  # skip escape + char
                    else:
                        self.pos += 1
                if self.pos >= len(self.text):
                    raise Exception("Unterminated string literal")
                tokens.append(Token("STRING_LIT", self.text[start : self.pos]))
                self.pos += 1  # consume closing "
                continue

            # Character literal (single-quoted)
            if ch == "'":
                self.pos += 1
                if self.pos >= len(self.text):
                    raise Exception("Unterminated char literal")
                if self.text[self.pos] == "\\":
                    self.pos += 1
                    if self.pos >= len(self.text):
                        raise Exception("Unterminated escape in char literal")
                    char_val = self.text[self.pos]
                    self.pos += 1
                else:
                    char_val = self.text[self.pos]
                    self.pos += 1
                if self.pos >= len(self.text) or self.text[self.pos] != "'":
                    raise Exception("Char literal must be single character")
                self.pos += 1
                tokens.append(Token("CHAR_LIT", char_val))
                continue

            # Two-character symbols (must be checked before single-char)
            if ch in CHARS_STARTING_2:
                two = self.text[self.pos : self.pos + 2]
                if two in SYMBOLS_2:
                    tokens.append(Token("SYMBOL", two))
                    self.pos += 2
                    continue

            # Single-character symbols
            if ch in SYMBOLS_1:
                tokens.append(Token("SYMBOL", ch))
                self.pos += 1
                continue

            raise Exception(f"Unknown character: {ch!r} at position {self.pos}")

        return tokens


if __name__ == "__main__":
    code = "int x; void main(){ print(42); }"
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    for t in tokens:
        print(t)
