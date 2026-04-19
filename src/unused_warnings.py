"""Warn on locals and parameters that are never read (after type checking)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from parser.ast import (
    Program,
    FunctionDecl,
    Block,
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
    SwitchStmt,
)


@dataclass
class _Binding:
    name: str
    line: Optional[int]
    is_param: bool
    used: bool = False


class _UnusedInFunction:
    def __init__(self, func_name: str, source_path: Optional[str]) -> None:
        self.func_name = func_name
        self.source_path = source_path
        self.scopes: List[dict[str, _Binding]] = []
        self.warnings: List[str] = []

    def _prefix(self) -> str:
        if self.source_path:
            return f"{self.source_path}: "
        return ""

    def _warn(self, b: _Binding, kind: str) -> None:
        loc = f" (line {b.line})" if b.line is not None else ""
        self.warnings.append(
            f"{self._prefix()}warning: unused {kind} '{b.name}' in function "
            f"'{self.func_name}'{loc}"
        )

    def _declare(self, name: str, line: Optional[int], is_param: bool) -> None:
        self.scopes[-1][name] = _Binding(name, line, is_param, False)

    def _mark_read(self, name: str) -> None:
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name].used = True
                return

    def _pop_scope(self) -> None:
        scope = self.scopes.pop()
        for b in scope.values():
            if not b.used:
                self._warn(b, "parameter" if b.is_param else "variable")

    def run(self, func: FunctionDecl) -> None:
        self.scopes.append({})
        for p in func.params:
            line = getattr(p, "line", None)
            self._declare(p.name, line, is_param=True)
        self._visit_block(func.body)
        self._pop_scope()

    def _visit_block(self, block: Block) -> None:
        self.scopes.append({})
        for d in block.declarations:
            line = getattr(d, "line", None)
            self._declare(d.name, line, is_param=False)
            if d.initializer is not None:
                self._visit_expr_reads(d.initializer)
        for st in block.statements:
            self._visit_statement(st)
        self._pop_scope()

    def _visit_statement(self, st) -> None:
        if isinstance(st, Block):
            self._visit_block(st)
        elif isinstance(st, IfStmt):
            self._visit_expr_reads(st.condition)
            self._visit_statement(st.then_branch)
            if st.else_branch is not None:
                self._visit_statement(st.else_branch)
        elif isinstance(st, WhileStmt):
            self._visit_expr_reads(st.condition)
            self._visit_statement(st.body)
        elif isinstance(st, ForStmt):
            if st.init is not None:
                self._visit_expr_reads(st.init)
            if st.condition is not None:
                self._visit_expr_reads(st.condition)
            if st.increment is not None:
                self._visit_expr_reads(st.increment)
            self._visit_statement(st.body)
        elif isinstance(st, SwitchStmt):
            self._visit_expr_reads(st.expr)
            for clause in st.cases:
                if clause.value is not None:
                    self._visit_expr_reads(clause.value)
                for s in clause.body:
                    self._visit_statement(s)
        elif isinstance(st, (BreakStmt, ContinueStmt)):
            pass
        elif isinstance(st, ReturnStmt):
            if st.value is not None:
                self._visit_expr_reads(st.value)
        elif isinstance(st, ExprStmt):
            if st.expr is not None:
                self._visit_expr_reads(st.expr)
        else:
            pass

    def _visit_expr_reads(self, expr) -> None:
        if isinstance(expr, Literal):
            return
        if isinstance(expr, Variable):
            self._mark_read(expr.name)
            return
        if isinstance(expr, ArrayAccess):
            self._mark_read(expr.array.name)
            self._visit_expr_reads(expr.index)
            return
        if isinstance(expr, BinaryOp):
            self._visit_expr_reads(expr.left)
            self._visit_expr_reads(expr.right)
            return
        if isinstance(expr, UnaryOp):
            self._visit_expr_reads(expr.operand)
            return
        if isinstance(expr, Assign):
            if isinstance(expr.target, Variable):
                self._visit_expr_reads(expr.value)
            elif isinstance(expr.target, ArrayAccess):
                self._mark_read(expr.target.array.name)
                self._visit_expr_reads(expr.target.index)
                self._visit_expr_reads(expr.value)
            return
        if isinstance(expr, Call):
            if isinstance(expr.callee, Variable):
                self._mark_read(expr.callee.name)
            for a in expr.args:
                self._visit_expr_reads(a)
            return


def unused_variable_warnings(program: Program, source_path: Optional[str] = None) -> List[str]:
    """
    Return warning strings for parameters and block locals that are never read.
    Call only after semantic analysis succeeds.
    """
    out: List[str] = []
    for fn in program.functions:
        w = _UnusedInFunction(fn.name, source_path)
        w.run(fn)
        out.extend(w.warnings)
    return out
