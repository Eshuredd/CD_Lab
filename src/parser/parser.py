from .ast import (
    Program,
    FunctionDecl,
    Param,
    Block,
    VarDecl,
    IfStmt,
    WhileStmt,
    ForStmt,
    BreakStmt,
    ContinueStmt,
    ReturnStmt,
    ExprStmt,
    Assign,
    BinaryOp,
    UnaryOp,
    Literal,
    Variable,
    ArrayAccess,
    Call,
)


class ParseError(Exception):
    pass


def _describe_token(tok):
    """Short description of a token for error messages (compiler-style)."""
    if tok is None:
        return "end of input"
    t = tok.type
    v = tok.value
    if t == "KEYWORD":
        return f"keyword '{v}'"
    if t == "IDENTIFIER":
        return f"identifier '{v}'"
    if t == "NUMBER":
        return f"integer literal {v!r}"
    if t == "FLOAT_LIT":
        return f"float literal {v!r}"
    if t == "BOOL_LIT":
        return f"boolean literal {v!r}"
    if t == "CHAR_LIT":
        return "character literal"
    if t == "STRING_LIT":
        return "string literal"
    if t == "SYMBOL":
        return repr(v)
    return f"{t} {v!r}"


def _describe_expected(ttype, value=None):
    """What the parser was expecting, for error messages."""
    if ttype == "IDENTIFIER" and value is None:
        return "an identifier"
    if ttype == "NUMBER" and value is None:
        return "an integer literal"
    if ttype == "KEYWORD" and value is not None:
        return f"keyword '{value}'"
    if ttype == "SYMBOL" and value is not None:
        return repr(value)
    if ttype == "SYMBOL":
        return "a symbol"
    if ttype == "KEYWORD":
        return "a keyword"
    return ttype.lower().replace("_", " ")


class Parser:
    def __init__(self, tokens, source_path=None):
        self.tokens = tokens
        self.index = 0
        self.errors = []
        self.source_path = source_path

        self.type_keywords = ["uint32", "int", "float", "bool", "char", "void"]

    def _location_token(self, tok):
        """Use last token for end-of-file situations."""
        if tok is not None:
            return tok
        if self.tokens:
            return self.tokens[-1]
        return None

    def _format_syntax_error(self, tok, message: str) -> str:
        """
        Classic-style diagnostic: with source path, 'file:line: syntax error: ...';
        otherwise 'line L: syntax error: ...'.
        """
        t = self._location_token(tok)
        line = getattr(t, "line", None) if t is not None else None
        col = getattr(t, "column", None) if t is not None else None

        if self.source_path and line is not None:
            return f"{self.source_path}:{line}: syntax error: {message}"
        if line is not None:
            return f"line {line}: syntax error: {message}"
        return f"syntax error: {message}"

    def _raise_syntax_error(self, tok, message: str):
        raise ParseError(self._format_syntax_error(tok, message))

    def _sync_to_next_statement(self):
        while self.current() is not None:
            tok = self.current()
            if tok.type == "SYMBOL" and tok.value == "}":
                return
            if tok.type == "SYMBOL" and tok.value == ";":
                self.advance()
                return
            if tok.type == "KEYWORD" and tok.value in ("if", "while", "for", "return", "break", "continue"):
                return
            self.advance()

    def _sync_to_next_function(self):
        while self.current() is not None:
            tok = self.current()
            if tok.type == "KEYWORD" and tok.value in self.type_keywords:
                return
            self.advance()

    def current(self):
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def advance(self):
        self.index += 1

    def match(self, ttype, value=None):
        tok = self.current()
        if tok is None:
            return False

        if tok.type != ttype:
            return False

        if value is not None and tok.value != value:
            return False

        self.advance()
        return True

    def expect(self, ttype, value=None):
        tok = self.current()
        expected = _describe_expected(ttype, value)
        if tok is None:
            self._raise_syntax_error(
                None,
                f"unexpected end of input while expecting {expected}",
            )

        if tok.type != ttype or (value is not None and tok.value != value):
            found = _describe_token(tok)
            self._raise_syntax_error(
                tok,
                f"expected {expected}, found {found}",
            )

        self.advance()
        return tok

    def parse(self):
        functions = []
        while self.current() is not None:
            try:
                functions.append(self.parse_function())
            except ParseError as e:
                self.errors.append(str(e))
                self._sync_to_next_function()
        return Program(functions)

    def parse_function(self):
        return_type = self.parse_type()
        name = self.expect("IDENTIFIER").value

        self.expect("SYMBOL", "(")
        params = []

        if not self.match("SYMBOL", ")"):
            while True:
                ptype = self.parse_type()
                pname = self.expect("IDENTIFIER").value
                params.append(Param(ptype, pname))

                if self.match("SYMBOL", ")"):
                    break
                self.expect("SYMBOL", ",")

        body = self.parse_block()
        return FunctionDecl(return_type, name, params, body)

    def parse_type(self):
        tok = self.current()
        if tok and tok.type == "KEYWORD" and tok.value in self.type_keywords:
            self.advance()
            return tok.value
        found = _describe_token(tok)
        self._raise_syntax_error(tok, f"expected a type name (int, void, ...), found {found}")

    def parse_block(self):
        self.expect("SYMBOL", "{")
        decls = []
        stmts = []

        while True:
            if self.match("SYMBOL", "}"):
                break

            tok = self.current()
            if tok is None:
                break

            if tok.type == "KEYWORD" and tok.value == "const":
                try:
                    decls.append(self.parse_var_decl())
                except ParseError as e:
                    self.errors.append(str(e))
                    self._sync_to_next_statement()
            elif tok.type == "KEYWORD" and tok.value in self.type_keywords:
                try:
                    decls.append(self.parse_var_decl())
                except ParseError as e:
                    self.errors.append(str(e))
                    self._sync_to_next_statement()
            else:
                try:
                    stmts.append(self.parse_statement())
                except ParseError as e:
                    self.errors.append(str(e))
                    self._sync_to_next_statement()

        return Block(decls, stmts)

    def parse_var_decl(self):
        is_const = False
        if self.match("KEYWORD", "const"):
            is_const = True

        vtype = self.parse_type()
        name = self.expect("IDENTIFIER").value

        size = None
        if self.match("SYMBOL", "["):
            size_tok = self.expect("NUMBER")
            size = int(size_tok.value)
            self.expect("SYMBOL", "]")

        init = None
        if self.match("SYMBOL", "="):
            init = self.parse_expression()

        self.expect("SYMBOL", ";")
        return VarDecl(vtype, name, is_const, size, init)

    def parse_statement(self):
        tok = self.current()
        if tok is None:
            self._raise_syntax_error(None, "unexpected end of input while parsing a statement")

        # block
        if tok.type == "SYMBOL" and tok.value == "{":
            return self.parse_block()

        # empty statement
        if self.match("SYMBOL", ";"):
            return ExprStmt(None)

        if tok.type == "KEYWORD":
            if tok.value == "if":
                return self.parse_if()
            if tok.value == "while":
                return self.parse_while()
            if tok.value == "for":
                return self.parse_for()
            if tok.value == "break":
                self.advance()
                self.expect("SYMBOL", ";")
                return BreakStmt()
            if tok.value == "continue":
                self.advance()
                self.expect("SYMBOL", ";")
                return ContinueStmt()
            if tok.value == "return":
                self.advance()
                expr = None
                if not self.match("SYMBOL", ";"):
                    expr = self.parse_expression()
                    self.expect("SYMBOL", ";")
                return ReturnStmt(expr)

        expr = self.parse_expression()
        self.expect("SYMBOL", ";")
        return ExprStmt(expr)

    def parse_if(self):
        self.expect("KEYWORD", "if")
        self.expect("SYMBOL", "(")
        cond = self.parse_expression()
        self.expect("SYMBOL", ")")
        then_branch = self.parse_statement()

        else_branch = None
        if self.match("KEYWORD", "else"):
            else_branch = self.parse_statement()

        return IfStmt(cond, then_branch, else_branch)

    def parse_while(self):
        self.expect("KEYWORD", "while")
        self.expect("SYMBOL", "(")
        cond = self.parse_expression()
        self.expect("SYMBOL", ")")
        body = self.parse_statement()
        return WhileStmt(cond, body)

    def parse_for(self):
        self.expect("KEYWORD", "for")
        self.expect("SYMBOL", "(")

        init = None
        if not (self.current() and self.current().type == "SYMBOL" and self.current().value == ";"):
            init = self.parse_expression()
        self.expect("SYMBOL", ";")

        cond = None
        if not (self.current() and self.current().type == "SYMBOL" and self.current().value == ";"):
            cond = self.parse_expression()
        self.expect("SYMBOL", ";")

        step = None
        if not (self.current() and self.current().type == "SYMBOL" and self.current().value == ")"):
            step = self.parse_expression()
        self.expect("SYMBOL", ")")

        body = self.parse_statement()
        return ForStmt(init, cond, step, body)


    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        left = self.parse_or()

        if self.match("SYMBOL", "="):
            eq_tok = self.tokens[self.index - 1]
            right = self.parse_assignment()
            if not isinstance(left, Variable) and not isinstance(left, ArrayAccess):
                self._raise_syntax_error(
                    eq_tok,
                    "invalid left-hand side of assignment (expected variable or array element)",
                )
            return Assign(left, right)

        return left

    def parse_or(self):
        left = self.parse_and()
        while self.match("SYMBOL", "||"):
            right = self.parse_and()
            left = BinaryOp("||", left, right)
        return left

    def parse_and(self):
        left = self.parse_equality()
        while self.match("SYMBOL", "&&"):
            right = self.parse_equality()
            left = BinaryOp("&&", left, right)
        return left

    def parse_equality(self):
        left = self.parse_comparison()

        while True:
            if self.match("SYMBOL", "==") or self.match("SYMBOL", "!="):
                op = self.tokens[self.index - 1].value
                right = self.parse_comparison()
                left = BinaryOp(op, left, right)
            else:
                break

        return left

    def parse_comparison(self):
        left = self.parse_additive()

        while True:
            if (
                self.match("SYMBOL", "<")
                or self.match("SYMBOL", ">")
                or self.match("SYMBOL", "<=")
                or self.match("SYMBOL", ">=")
            ):
                op = self.tokens[self.index - 1].value
                right = self.parse_additive()
                left = BinaryOp(op, left, right)
            else:
                break

        return left

    def parse_additive(self):
        left = self.parse_term()

        while self.match("SYMBOL", "+") or self.match("SYMBOL", "-"):
            op = self.tokens[self.index - 1].value
            right = self.parse_term()
            left = BinaryOp(op, left, right)

        return left

    def parse_term(self):
        left = self.parse_unary()

        while self.match("SYMBOL", "*") or self.match("SYMBOL", "/") or self.match("SYMBOL", "%"):
            op = self.tokens[self.index - 1].value
            right = self.parse_unary()
            left = BinaryOp(op, left, right)

        return left

    def parse_unary(self):
        if (
            self.match("SYMBOL", "!")
            or self.match("SYMBOL", "-")
            or self.match("SYMBOL", "++")
            or self.match("SYMBOL", "--")
        ):
            op = self.tokens[self.index - 1].value
            right = self.parse_unary()
            return UnaryOp(op, right, postfix=False)

        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()

        while True:
            if self.match("SYMBOL", "("):
                args = []
                if not self.match("SYMBOL", ")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.match("SYMBOL", ")"):
                            break
                        self.expect("SYMBOL", ",")
                expr = Call(expr, args)
            elif self.match("SYMBOL", "["):
                idx = self.parse_expression()
                self.expect("SYMBOL", "]")
                expr = ArrayAccess(expr, idx)
            elif self.match("SYMBOL", "++") or self.match("SYMBOL", "--"):
                op = self.tokens[self.index - 1].value
                expr = UnaryOp(op, expr, postfix=True)
            else:
                break

        return expr

    def parse_primary(self):
        tok = self.current()
        if tok is None:
            self._raise_syntax_error(None, "unexpected end of input in expression")

        if tok.type == "NUMBER":
            self.advance()
            return Literal("int", int(tok.value))

        if tok.type == "FLOAT_LIT":
            self.advance()
            return Literal("float", float(tok.value))

        if tok.type == "BOOL_LIT":
            self.advance()
            return Literal("bool", tok.value == "true")

        if tok.type == "CHAR_LIT":
            self.advance()
            return Literal("char", tok.value)

        if tok.type == "STRING_LIT":
            self.advance()
            return Literal("string", tok.value)

        if tok.type == "IDENTIFIER":
            self.advance()
            return Variable(tok.value)

        if self.match("SYMBOL", "("):
            expr = self.parse_expression()
            self.expect("SYMBOL", ")")
            return expr

        self._raise_syntax_error(
            tok,
            f"expected primary expression (literal, identifier, or '(' ... ')'), found {_describe_token(tok)}",
        )
