from .tokens import KEYWORDS, SYMBOLS

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

    def tokenize(self):
        tokens = []

        while self.pos < len(self.text):
            ch = self.text[self.pos]

            # Skip whitespace
            if ch.isspace():
                self.pos += 1
                continue

            # Identifier or keyword
            if ch.isalpha():
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos].isalnum():
                    self.pos += 1
                word = self.text[start:self.pos]

                if word in KEYWORDS:
                    tokens.append(Token("KEYWORD", word))
                else:
                    tokens.append(Token("IDENTIFIER", word))
                continue

            # Number
            if ch.isdigit():
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos].isdigit():
                    self.pos += 1
                number = self.text[start:self.pos]
                tokens.append(Token("NUMBER", number))
                continue

            # Symbols
            if ch in SYMBOLS:
                tokens.append(Token("SYMBOL", ch))
                self.pos += 1
                continue

            # Unknown character
            raise Exception(f"Unknown character: {ch}")

        return tokens


if __name__ == "__main__":
    code = "int x; void main(){print(a);}"
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    print(tokens)
