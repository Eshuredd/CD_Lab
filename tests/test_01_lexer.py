"""Lexer unit tests.

Each test feeds a small source snippet to the Lexer and checks the resulting
token stream — type, value, and (where relevant) line numbers.
"""

import pytest
from lexer.lexer import Lexer, Token


def tokenize(src: str):
    return Lexer(src).tokenize()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def types(src: str):
    return [t.type for t in tokenize(src)]


def values(src: str):
    return [t.value for t in tokenize(src)]


# ---------------------------------------------------------------------------
# 1. Keywords
# ---------------------------------------------------------------------------

class TestKeywords:
    def test_int_keyword(self):
        toks = tokenize("int")
        assert len(toks) == 1
        assert toks[0].type == "KEYWORD"
        assert toks[0].value == "int"

    def test_all_type_keywords(self):
        src = "int uint32 float bool char void"
        ts = [t for t in tokenize(src) if t.type == "KEYWORD"]
        assert [t.value for t in ts] == ["int", "uint32", "float", "bool", "char", "void"]

    def test_control_keywords(self):
        src = "if else while for break continue return const"
        kw_vals = [t.value for t in tokenize(src) if t.type == "KEYWORD"]
        assert set(kw_vals) == {"if", "else", "while", "for", "break", "continue", "return", "const"}


# ---------------------------------------------------------------------------
# 2. Identifiers
# ---------------------------------------------------------------------------

class TestIdentifiers:
    def test_simple_identifier(self):
        toks = tokenize("myVar")
        assert toks[0].type == "IDENTIFIER"
        assert toks[0].value == "myVar"

    def test_underscore_identifier(self):
        toks = tokenize("_foo_bar")
        assert toks[0].type == "IDENTIFIER"
        assert toks[0].value == "_foo_bar"

    def test_identifier_with_digits(self):
        toks = tokenize("x1y2z3")
        assert toks[0].type == "IDENTIFIER"

    def test_keyword_not_identifier(self):
        # "int" must come back as KEYWORD, not IDENTIFIER
        toks = tokenize("int")
        assert toks[0].type != "IDENTIFIER"


# ---------------------------------------------------------------------------
# 3. Integer & float literals
# ---------------------------------------------------------------------------

class TestLiterals:
    def test_integer_literal(self):
        toks = tokenize("42")
        assert toks[0].type == "NUMBER"
        assert toks[0].value == "42"

    def test_zero(self):
        toks = tokenize("0")
        assert toks[0].type == "NUMBER"
        assert toks[0].value == "0"

    def test_float_literal(self):
        toks = tokenize("3.14")
        assert toks[0].type == "FLOAT_LIT"
        assert toks[0].value == "3.14"

    def test_bool_true(self):
        toks = tokenize("true")
        assert toks[0].type == "BOOL_LIT"
        assert toks[0].value == "true"

    def test_bool_false(self):
        toks = tokenize("false")
        assert toks[0].type == "BOOL_LIT"
        assert toks[0].value == "false"

    def test_string_literal(self):
        toks = tokenize('"hello"')
        assert toks[0].type == "STRING_LIT"
        assert toks[0].value == "hello"


# ---------------------------------------------------------------------------
# 4. Operators and symbols
# ---------------------------------------------------------------------------

class TestOperators:
    def test_arithmetic_operators(self):
        ts = types("+ - * / %")
        assert ts == ["SYMBOL"] * 5

    def test_two_char_operators(self):
        src = "<= >= == != && ||"
        toks = tokenize(src)
        syms = [t for t in toks if t.type == "SYMBOL"]
        assert [t.value for t in syms] == ["<=", ">=", "==", "!=", "&&", "||"]

    def test_increment_decrement(self):
        src = "++ --"
        toks = tokenize(src)
        syms = [t.value for t in toks if t.type == "SYMBOL"]
        assert syms == ["++", "--"]

    def test_single_lt_gt(self):
        toks = tokenize("< >")
        syms = [t.value for t in toks if t.type == "SYMBOL"]
        assert "<" in syms and ">" in syms


# ---------------------------------------------------------------------------
# 5. Comments
# ---------------------------------------------------------------------------

class TestComments:
    def test_line_comment_ignored(self):
        toks = tokenize("// this is a comment\nint")
        assert len(toks) == 1
        assert toks[0].value == "int"

    def test_comment_at_end_of_line_with_code(self):
        toks = tokenize("int x; // declare x")
        vals = [t.value for t in toks]
        assert "int" in vals
        assert "x" in vals
        assert ";" in vals

    def test_inline_comment_does_not_consume_next_line(self):
        src = "int // comment\nbool"
        vals = [t.value for t in tokenize(src)]
        assert vals == ["int", "bool"]


# ---------------------------------------------------------------------------
# 6. Line tracking
# ---------------------------------------------------------------------------

class TestLineNumbers:
    def test_token_line_numbers(self):
        src = "int\nbool\nvoid"
        toks = tokenize(src)
        assert toks[0].line == 1
        assert toks[1].line == 2
        assert toks[2].line == 3

    def test_column_starts_at_one(self):
        toks = tokenize("int")
        assert toks[0].column == 1


# ---------------------------------------------------------------------------
# 7. Multi-token expression
# ---------------------------------------------------------------------------

class TestExpression:
    def test_assignment_expression(self):
        toks = tokenize("x = 10 + y;")
        types_list = [t.type for t in toks]
        # IDENTIFIER SYMBOL NUMBER SYMBOL IDENTIFIER SYMBOL
        assert types_list == [
            "IDENTIFIER", "SYMBOL", "NUMBER", "SYMBOL", "IDENTIFIER", "SYMBOL"
        ]

    def test_function_call_tokens(self):
        toks = tokenize("foo(a, b)")
        types_list = [t.type for t in toks]
        assert types_list == [
            "IDENTIFIER", "SYMBOL", "IDENTIFIER", "SYMBOL", "IDENTIFIER", "SYMBOL"
        ]
