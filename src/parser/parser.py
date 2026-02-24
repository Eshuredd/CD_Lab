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


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

        self.type_keywords = ["uint32", "int", "float", "bool", "char", "void"]

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
        if tok is None:
            raise ParseError("Unexpected end of input")

        if tok.type != ttype:
            raise ParseError("Unexpected token: " + str(tok.value))

        if value is not None and tok.value != value:
            raise ParseError("Expected " + value)

        self.advance()
        return tok

    def parse(self):
        functions = []
        while self.current() is not None:
            functions.append(self.parse_function())
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
        raise ParseError("Expected type")

    def parse_block(self):
        self.expect("SYMBOL", "{")
        decls = []
        stmts = []

        while True:
            if self.match("SYMBOL", "}"):
                break

            tok = self.current()
            if tok is None:
                raise ParseError("Unexpected end of input in block")

            if tok.type == "KEYWORD" and tok.value == "const":
                decls.append(self.parse_var_decl())
            elif tok.type == "KEYWORD" and tok.value in self.type_keywords:
                decls.append(self.parse_var_decl())
            else:
                stmts.append(self.parse_statement())

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
            raise ParseError("Unexpected end of input")

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
            right = self.parse_assignment()
            if not isinstance(left, Variable) and not isinstance(left, ArrayAccess):
                raise ParseError("Invalid assignment")
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
            raise ParseError("Invalid expression")

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

        raise ParseError("Invalid expression")
