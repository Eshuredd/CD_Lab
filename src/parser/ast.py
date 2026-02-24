from __future__ import annotations

from typing import Any


class ASTNode:
    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return self._pretty()

    def _pretty(self, level: int = 0) -> str:
        indent = _INDENT_UNIT * level
        fields = getattr(self, "__dict__", {})

        if not fields:
            return f"{self.__class__.__name__}()"

        lines: list[str] = [f"{self.__class__.__name__}("]
        for key, value in fields.items():
            rendered = _pretty_value(value, level + 1)
            if "\n" in rendered:
                rendered = "\n" + _indent_multiline(
                    rendered, _INDENT_UNIT * (level + 2)
                )
            lines.append(f"{indent}{_INDENT_UNIT}{key}={rendered},")
        lines.append(f"{indent})")
        return "\n".join(lines)


_INDENT_UNIT = " "


def _indent_multiline(s: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in s.splitlines())


def _pretty_value(value: Any, level: int) -> str:
    if isinstance(value, ASTNode):
        return value._pretty(level)

    if isinstance(value, list):
        if not value:
            return "[]"
        indent = _INDENT_UNIT * level
        items = [_pretty_value(v, level + 1) for v in value]
        lines = ["["]
        for item in items:
            if "\n" in item:
                lines.append(_indent_multiline(item, f"{indent}{_INDENT_UNIT}"))
            else:
                lines.append(f"{indent}{_INDENT_UNIT}{item}")
        lines.append(f"{_INDENT_UNIT * (level - 1)}]")
        return "\n".join(lines)

    if isinstance(value, tuple):
        if not value:
            return "()"
        inner = ", ".join(_pretty_value(v, level) for v in value)
        return f"({inner})"

    return repr(value)


class Program(ASTNode):
    def __init__(self, functions):
        self.functions = functions


class FunctionDecl(ASTNode):
    def __init__(self, return_type, name, params, body):
        self.return_type = return_type
        self.name = name
        self.params = params
        self.body = body


class Param(ASTNode):
    def __init__(self, param_type, name):
        self.param_type = param_type
        self.name = name


class Block(ASTNode):
    def __init__(self, declarations, statements):
        self.declarations = declarations
        self.statements = statements


class VarDecl(ASTNode):
    def __init__(self, var_type, name, is_const=False, size=None, initializer=None):
        self.var_type = var_type
        self.name = name
        self.is_const = is_const
        self.size = size
        self.initializer = initializer


class IfStmt(ASTNode):
    def __init__(self, condition, then_branch, else_branch=None):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch


class WhileStmt(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body


class ForStmt(ASTNode):
    def __init__(self, init, condition, increment, body):
        self.init = init
        self.condition = condition
        self.increment = increment
        self.body = body


class BreakStmt(ASTNode):
    def __init__(self):
        # intentionally empty
        return


class ContinueStmt(ASTNode):
    def __init__(self):
        # intentionally empty
        return


class ReturnStmt(ASTNode):
    def __init__(self, value):
        self.value = value


class ExprStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr


class Assign(ASTNode):
    def __init__(self, target, value):
        self.target = target
        self.value = value


class BinaryOp(ASTNode):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class UnaryOp(ASTNode):
    def __init__(self, op, operand, postfix=False):
        self.op = op
        self.operand = operand
        self.postfix = postfix


class Literal(ASTNode):
    def __init__(self, kind, value):
        self.kind = kind
        self.value = value


class Variable(ASTNode):
    def __init__(self, name):
        self.name = name


class ArrayAccess(ASTNode):
    def __init__(self, array, index):
        self.array = array
        self.index = index


class Call(ASTNode):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args

