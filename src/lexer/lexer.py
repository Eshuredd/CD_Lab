from .tokens import KEYWORDS, SYMBOLS_1, SYMBOLS_2, CHARS_STARTING_2, BOOL_LITERALS


class Token:
    def __init__(self, type, value, line=None, column=None):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        loc = ""
        if self.line is not None:
            loc = f" (line {self.line})"
        return f"{self.type}: {self.value}{loc}"


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1

    def _consume_char(self):
        """Consume one character and update (line, column) counters."""
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    def peek(self, offset=0):
        i = self.pos + offset
        return self.text[i] if i < len(self.text) else None

    def tokenize(self):
        tokens = []

        while self.pos < len(self.text):
            ch = self.text[self.pos]

            if ch.isspace():
                self._consume_char()
                continue

            # Second slash must be peek(1): peek() is same as ch (offset 0).
            if ch == "/" and self.peek(1) == "/":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self._consume_char()
                continue

            # Identifiers: letter or underscore start; body is alphanumeric or underscore
            if ch.isalpha() or ch == "_":
                start = self.pos
                tok_line = self.line
                tok_col = self.column
                while self.pos < len(self.text):
                    c = self.text[self.pos]
                    if c.isalnum() or c == "_":
                        self._consume_char()
                    else:
                        break
                word = self.text[start : self.pos]
                if word in BOOL_LITERALS:
                    tokens.append(Token("BOOL_LIT", word, tok_line, tok_col))
                elif word in KEYWORDS:
                    tokens.append(Token("KEYWORD", word, tok_line, tok_col))
                else:
                    tokens.append(Token("IDENTIFIER", word, tok_line, tok_col))
                continue

            # Number or float literal
            if ch.isdigit():
                start = self.pos
                tok_line = self.line
                tok_col = self.column
                while self.pos < len(self.text) and self.text[self.pos].isdigit():
                    self._consume_char()
                if self.peek() == "." and self.peek(1) is not None and self.peek(1).isdigit():
                    self._consume_char()  # consume '.'
                    while self.pos < len(self.text) and self.text[self.pos].isdigit():
                        self._consume_char()
                    tokens.append(Token("FLOAT_LIT", self.text[start : self.pos], tok_line, tok_col))
                else:
                    tokens.append(Token("NUMBER", self.text[start : self.pos], tok_line, tok_col))
                continue

            # String literal (double-quoted)
            if ch == '"':
                tok_line = self.line
                tok_col = self.column
                self._consume_char()  # opening "
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos] != '"':
                    if self.text[self.pos] == "\\":
                        self._consume_char()  # backslash
                        if self.pos < len(self.text):
                            self._consume_char()  # escaped char
                    else:
                        self._consume_char()
                if self.pos >= len(self.text):
                    raise Exception("Unterminated string literal")
                tokens.append(Token("STRING_LIT", self.text[start : self.pos], tok_line, tok_col))
                self._consume_char()  # consume closing "
                continue

            # Character literal (single-quoted)
            if ch == "'":
                tok_line = self.line
                tok_col = self.column
                self._consume_char()  # opening '
                if self.pos >= len(self.text):
                    raise Exception("Unterminated char literal")
                if self.text[self.pos] == "\\":
                    self._consume_char()
                    if self.pos >= len(self.text):
                        raise Exception("Unterminated escape in char literal")
                    char_val = self.text[self.pos]
                    self._consume_char()
                else:
                    char_val = self.text[self.pos]
                    self._consume_char()
                if self.pos >= len(self.text) or self.text[self.pos] != "'":
                    raise Exception("Char literal must be single character")
                self._consume_char()  # closing '
                tokens.append(Token("CHAR_LIT", char_val, tok_line, tok_col))
                continue

            # Two-character symbols (must be checked before single-char)
            if ch in CHARS_STARTING_2:
                two = self.text[self.pos : self.pos + 2]
                if two in SYMBOLS_2:
                    tok_line = self.line
                    tok_col = self.column
                    self._consume_char()
                    self._consume_char()
                    tokens.append(Token("SYMBOL", two, tok_line, tok_col))
                    continue

            # Single-character symbols
            if ch in SYMBOLS_1:
                tok_line = self.line
                tok_col = self.column
                self._consume_char()
                tokens.append(Token("SYMBOL", ch, tok_line, tok_col))
                continue

            raise Exception(f"Unknown character: {ch!r} at position {self.pos} (line {self.line})")

        return tokens


if __name__ == "__main__":
    code = "int x; void main(){ print(42); }"
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    for t in tokens:
        print(t)
