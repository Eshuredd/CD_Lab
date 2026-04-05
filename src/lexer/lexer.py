from .tokens import KEYWORDS, SYMBOLS_1, SYMBOLS_2, CHARS_STARTING_2, BOOL_LITERALS


class Token:
    def __init__(self, type, value, line=None, column=None):
        self.type, self.value, self.line, self.column = type, value, line, column

    def __repr__(self):
        loc = f" (line {self.line})" if self.line is not None else ""
        return f"{self.type}: {self.value}{loc}"


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1

    def _adv(self):
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def peek(self, offset=0):
        i = self.pos + offset
        return self.text[i] if i < len(self.text) else None

    def tokenize(self):
        toks, t = [], self.text
        while self.pos < len(t):
            ch = t[self.pos]
            if ch.isspace():
                self._adv()
                continue

            if ch == "/" and self.peek(1) == "/":
                while self.pos < len(t) and t[self.pos] != "\n":
                    self._adv()
                continue

            L, C = self.line, self.column

            if ch.isalpha() or ch == "_":
                start = self.pos
                while self.pos < len(t) and (t[self.pos].isalnum() or t[self.pos] == "_"):
                    self._adv()
                w = t[start : self.pos]
                kind = "BOOL_LIT" if w in BOOL_LITERALS else ("KEYWORD" if w in KEYWORDS else "IDENTIFIER")
                toks.append(Token(kind, w, L, C))
                continue

            if ch.isdigit():
                start = self.pos
                while self.pos < len(t) and t[self.pos].isdigit():
                    self._adv()
                if self.peek() == "." and self.peek(1) and self.peek(1).isdigit():
                    self._adv()
                    while self.pos < len(t) and t[self.pos].isdigit():
                        self._adv()
                    toks.append(Token("FLOAT_LIT", t[start : self.pos], L, C))
                else:
                    toks.append(Token("NUMBER", t[start : self.pos], L, C))
                continue

            if ch == '"':
                self._adv()
                start = self.pos
                while self.pos < len(t) and t[self.pos] != '"':
                    if t[self.pos] == "\\":
                        self._adv()
                        if self.pos < len(t):
                            self._adv()
                    else:
                        self._adv()
                if self.pos >= len(t):
                    raise Exception("Unterminated string literal")
                toks.append(Token("STRING_LIT", t[start : self.pos], L, C))
                self._adv()
                continue

            if ch == "'":
                self._adv()
                if self.pos >= len(t):
                    raise Exception("Unterminated char literal")
                if t[self.pos] == "\\":
                    self._adv()
                    if self.pos >= len(t):
                        raise Exception("Unterminated escape in char literal")
                cv = t[self.pos]
                self._adv()
                if self.pos >= len(t) or t[self.pos] != "'":
                    raise Exception("Char literal must be single character")
                self._adv()
                toks.append(Token("CHAR_LIT", cv, L, C))
                continue

            if ch in CHARS_STARTING_2:
                two = t[self.pos : self.pos + 2]
                if two in SYMBOLS_2:
                    self._adv()
                    self._adv()
                    toks.append(Token("SYMBOL", two, L, C))
                    continue

            if ch in SYMBOLS_1:
                self._adv()
                toks.append(Token("SYMBOL", ch, L, C))
                continue

            raise Exception(f"Unknown character: {ch!r} at position {self.pos} (line {self.line})")

        return toks


if __name__ == "__main__":
    lx = Lexer("int x; void main(){ print(42); }")
    for x in lx.tokenize():
        print(x)
