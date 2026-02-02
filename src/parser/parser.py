class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def end(self):
        return self.pos >= len(self.tokens)

    def statement(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self):
        statements = []
        while not self.end():
            statements.append(self.statement())
        return statements
