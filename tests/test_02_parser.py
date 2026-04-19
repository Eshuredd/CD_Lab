"""Parser unit tests.

Parse small source programs and assert the AST structure matches expectations.
Also checks that ill-formed programs surface ParseError.
"""

import pytest
from lexer.lexer import Lexer
from parser.parser import Parser, ParseError
from parser.ast import (
    Program, FunctionDecl, Block, VarDecl, IfStmt, WhileStmt, ForStmt,
    ReturnStmt, Assign, BinaryOp, Literal, Variable, Call, ArrayAccess,
)


def parse(src: str) -> Program:
    tokens = Lexer(src).tokenize()
    p = Parser(tokens)
    ast = p.parse()
    if ast is None or p.errors:
        raise ParseError("; ".join(p.errors) if p.errors else "parse returned None")
    return ast


def parse_ok(src: str) -> Program:
    """Parse and assert no errors."""
    return parse(src)


def assert_parse_error(src: str):
    """Assert that parsing raises ParseError or leaves errors."""
    tokens = Lexer(src).tokenize()
    p = Parser(tokens)
    ast = p.parse()
    assert ast is None or p.errors, "Expected a parse error but none occurred"


# ---------------------------------------------------------------------------
# 1. Function declarations
# ---------------------------------------------------------------------------

class TestFunctionDecl:
    def test_void_main_no_params(self):
        prog = parse_ok("int main() { return 0; }")
        assert len(prog.functions) == 1
        fn = prog.functions[0]
        assert isinstance(fn, FunctionDecl)
        assert fn.name == "main"
        assert fn.return_type == "int"
        assert fn.params == []

    def test_function_with_params(self):
        prog = parse_ok("int add(int a, int b) { return a; }")
        fn = prog.functions[0]
        assert len(fn.params) == 2
        assert fn.params[0].name == "a"
        assert fn.params[1].param_type == "int"

    def test_multiple_functions(self):
        src = "int foo() { return 1; } int bar() { return 2; }"
        prog = parse_ok(src)
        assert len(prog.functions) == 2
        names = [f.name for f in prog.functions]
        assert "foo" in names and "bar" in names

    def test_void_return_type(self):
        prog = parse_ok("void say() { return; }")
        assert prog.functions[0].return_type == "void"


# ---------------------------------------------------------------------------
# 2. Variable declarations
# ---------------------------------------------------------------------------

class TestVarDecl:
    def test_int_decl_with_init(self):
        prog = parse_ok("int main() { int x = 5; return 0; }")
        body = prog.functions[0].body
        decl = body.declarations[0]
        assert isinstance(decl, VarDecl)
        assert decl.name == "x"
        assert decl.var_type == "int"

    def test_uninitialized_decl(self):
        prog = parse_ok("int main() { int y; return 0; }")
        decl = prog.functions[0].body.declarations[0]
        assert decl.initializer is None

    def test_const_decl(self):
        prog = parse_ok("int main() { const int MAX = 100; return 0; }")
        decl = prog.functions[0].body.declarations[0]
        assert decl.is_const is True

    def test_bool_decl(self):
        prog = parse_ok("int main() { bool flag = true; return 0; }")
        decl = prog.functions[0].body.declarations[0]
        assert decl.var_type == "bool"

    def test_array_decl(self):
        prog = parse_ok("int main() { int arr[5]; return 0; }")
        decl = prog.functions[0].body.declarations[0]
        assert decl.size == 5


# ---------------------------------------------------------------------------
# 3. Assignment and expressions
# ---------------------------------------------------------------------------

class TestAssignment:
    def _unwrap_assign(self, stmt):
        """Assignments are wrapped in ExprStmt by the parser."""
        from parser.ast import ExprStmt
        if isinstance(stmt, ExprStmt):
            return stmt.expr
        return stmt

    def test_simple_assignment(self):
        prog = parse_ok("int main() { int x; x = 42; return 0; }")
        raw_stmt = prog.functions[0].body.statements[0]
        stmt = self._unwrap_assign(raw_stmt)
        assert isinstance(stmt, Assign)
        # target is a Variable node
        assert isinstance(stmt.target, Variable)
        assert stmt.target.name == "x"

    def test_binary_op_rhs(self):
        prog = parse_ok("int main() { int x; x = 3 + 4; return 0; }")
        assign = self._unwrap_assign(prog.functions[0].body.statements[0])
        assert isinstance(assign.value, BinaryOp)
        assert assign.value.op == "+"

    def test_nested_binary_op(self):
        prog = parse_ok("int main() { int x; x = (2 + 3) * 4; return 0; }")
        assign = self._unwrap_assign(prog.functions[0].body.statements[0])
        # outer op should be *
        assert assign.value.op == "*"


# ---------------------------------------------------------------------------
# 4. Control flow statements
# ---------------------------------------------------------------------------

class TestControlFlow:
    def test_if_statement(self):
        src = "int main() { if (1 == 1) { return 1; } return 0; }"
        prog = parse_ok(src)
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, IfStmt)
        assert stmt.else_branch is None

    def test_if_else_statement(self):
        src = "int main() { if (1 < 2) { return 1; } else { return 0; } }"
        prog = parse_ok(src)
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, IfStmt)
        assert stmt.else_branch is not None

    def test_while_loop(self):
        src = "int main() { int i; i = 0; while (i < 5) { i = i + 1; } return 0; }"
        prog = parse_ok(src)
        while_stmt = prog.functions[0].body.statements[1]
        assert isinstance(while_stmt, WhileStmt)

    def test_for_loop(self):
        src = "int main() { int i; for (i = 0; i < 3; i = i + 1) { } return 0; }"
        prog = parse_ok(src)
        for_stmt = prog.functions[0].body.statements[0]
        assert isinstance(for_stmt, ForStmt)


# ---------------------------------------------------------------------------
# 5. Return statements
# ---------------------------------------------------------------------------

class TestReturn:
    def test_return_literal(self):
        prog = parse_ok("int main() { return 0; }")
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, ReturnStmt)
        assert isinstance(ret.value, Literal)
        assert ret.value.value == 0

    def test_return_variable(self):
        prog = parse_ok("int main() { int x; x = 1; return x; }")
        ret = prog.functions[0].body.statements[1]
        assert isinstance(ret, ReturnStmt)
        assert isinstance(ret.value, Variable)


# ---------------------------------------------------------------------------
# 6. Parse errors
# ---------------------------------------------------------------------------

class TestParseErrors:
    def test_missing_semicolon(self):
        assert_parse_error("int main() { int x = 5 return 0; }")

    def test_empty_function_body_parse_error(self):
        # A function with a missing opening brace is a parse error
        assert_parse_error("int main) { return 0; }")

    def test_missing_open_paren_in_if(self):
        assert_parse_error("int main() { if 1 == 1 { return 0; } }")
