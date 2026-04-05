"""AST → linear IR (three-address). Requires semantic analysis to have run first."""

from __future__ import annotations
from typing import Any, List, Optional

from parser.ast import (
    Program, FunctionDecl, Block, VarDecl, IfStmt, WhileStmt, ForStmt,
    BreakStmt, ContinueStmt, ReturnStmt, ExprStmt, Assign, BinaryOp, UnaryOp,
    Literal, Variable, ArrayAccess, Call,
)
from .ir import (
    Instruction, IRProgram, IRFunction,
    CONST, LOAD, STORE, LOAD_ARR, STORE_ARR, ALLOC_ARRAY,
    ADD, SUB, MUL, DIV, MOD, NEG, INC, DEC,
    LT, LE, GT, GE, EQ, NE, AND, OR, NOT,
    LABEL, JMP, JMP_IF, JMP_IF_NOT, PARAM, CALL as IR_CALL, RET, PRINT, READ_INT, EXIT, FUNC_ENTRY,
)

_BIN = {
    "+": ADD, "-": SUB, "*": MUL, "/": DIV, "%": MOD,
    "<": LT, "<=": LE, ">": GT, ">=": GE, "==": EQ, "!=": NE,
    "&&": AND, "||": OR,
}


class IRBuilder:
    def __init__(self) -> None:
        self._t = self._l = 0
        self._ins: List[Instruction] = []
        self._loops: List[tuple] = []
        self._rets: dict[str, str] = {}

    def _tmp(self) -> str:
        t = f"%{self._t}"
        self._t += 1
        return t

    def _lbl(self) -> str:
        L = f"L{self._l}"
        self._l += 1
        return L

    def _e(self, i: Instruction) -> None:
        self._ins.append(i)

    def build(self, program: Program) -> IRProgram:
        self._rets = {f.name: f.return_type for f in program.functions}
        return IRProgram([self._func(f) for f in program.functions])

    def _func(self, func: FunctionDecl) -> IRFunction:
        self._t = self._l = 0
        self._ins = []
        self._loops = []
        pnames = [p.name for p in func.params]
        ptypes = [p.param_type for p in func.params]
        self._e(FUNC_ENTRY(func.name, func.return_type, pnames))
        self._block(func.body)
        return IRFunction(func.name, func.return_type, pnames, ptypes, list(self._ins))

    def _block(self, block: Block) -> None:
        for d in block.declarations:
            if d.size is not None:
                self._e(ALLOC_ARRAY(d.name, d.size))
            if d.initializer is not None:
                self._e(STORE(d.name, self._expr(d.initializer)))
        for s in block.statements:
            self._stmt(s)

    def _stmt(self, stmt: Any) -> None:
        if isinstance(stmt, IfStmt):
            c = self._expr(stmt.condition)
            le, en = self._lbl(), self._lbl()
            self._e(JMP_IF_NOT(c, le))
            self._stmt(stmt.then_branch)
            self._e(JMP(en))
            self._e(LABEL(le))
            if stmt.else_branch:
                self._stmt(stmt.else_branch)
            self._e(LABEL(en))
        elif isinstance(stmt, WhileStmt):
            h, x = self._lbl(), self._lbl()
            self._loops.append((x, h))
            self._e(LABEL(h))
            self._e(JMP_IF_NOT(self._expr(stmt.condition), x))
            self._stmt(stmt.body)
            self._e(JMP(h))
            self._e(LABEL(x))
            self._loops.pop()
        elif isinstance(stmt, ForStmt):
            if stmt.init:
                self._expr(stmt.init)
            h, x = self._lbl(), self._lbl()
            self._loops.append((x, h))
            self._e(LABEL(h))
            if stmt.condition:
                self._e(JMP_IF_NOT(self._expr(stmt.condition), x))
            self._stmt(stmt.body)
            if stmt.increment:
                self._expr(stmt.increment)
            self._e(JMP(h))
            self._e(LABEL(x))
            self._loops.pop()
        elif isinstance(stmt, BreakStmt):
            self._e(JMP(self._loops[-1][0]))
        elif isinstance(stmt, ContinueStmt):
            self._e(JMP(self._loops[-1][1]))
        elif isinstance(stmt, ReturnStmt):
            self._e(RET(None if stmt.value is None else self._expr(stmt.value)))
        elif isinstance(stmt, ExprStmt) and stmt.expr:
            self._expr(stmt.expr)
        elif isinstance(stmt, Block):
            self._block(stmt)
        else:
            raise TypeError(f"Unknown statement: {type(stmt)}")

    def _expr(self, expr: Any) -> str:
        if isinstance(expr, Literal):
            d = self._tmp()
            k, v = expr.kind, expr.value
            if k == "bool" and isinstance(v, bool):
                v = 1 if v else 0
            if k == "char" and isinstance(v, str):
                v = ord(v) if len(v) == 1 else 0
            self._e(CONST(d, k, v))
            return d
        if isinstance(expr, Variable):
            d = self._tmp()
            self._e(LOAD(d, expr.name))
            return d
        if isinstance(expr, Assign):
            vt = self._expr(expr.value)
            tgt = expr.target
            if isinstance(tgt, Variable):
                self._e(STORE(tgt.name, vt))
            elif isinstance(tgt, ArrayAccess):
                self._e(STORE_ARR(tgt.array.name, self._expr(tgt.index), vt))
            else:
                raise TypeError("Invalid assignment target")
            return vt
        if isinstance(expr, BinaryOp):
            L, R = self._expr(expr.left), self._expr(expr.right)
            d = self._tmp()
            fn = _BIN.get(expr.op)
            if fn is None:
                raise ValueError(f"Unknown binary op: {expr.op}")
            self._e(fn(d, L, R))
            return d
        if isinstance(expr, UnaryOp):
            src = self._expr(expr.operand)
            d = self._tmp()
            op = expr.op
            if op == "!":
                self._e(NOT(d, src))
            elif op == "-":
                self._e(NEG(d, src))
            elif op == "++":
                self._e(INC(d, src))
                self._post_store(expr.operand, d)
                if expr.postfix:
                    d = src
            elif op == "--":
                self._e(DEC(d, src))
                self._post_store(expr.operand, d)
                if expr.postfix:
                    d = src
            else:
                raise ValueError(f"Unknown unary op: {op}")
            return d
        if isinstance(expr, ArrayAccess):
            d = self._tmp()
            self._e(LOAD_ARR(d, expr.array.name, self._expr(expr.index)))
            return d
        if isinstance(expr, Call):
            name = expr.callee.name
            if name == "print":
                self._e(PRINT([self._expr(a) for a in expr.args]))
                return self._tmp()
            if name == "readInt":
                d = self._tmp()
                self._e(READ_INT(d))
                return d
            if name == "exit":
                self._e(EXIT(self._expr(expr.args[0])))
                return self._tmp()
            args = [self._expr(a) for a in expr.args]
            for a in args:
                self._e(PARAM(a))
            rt = self._rets.get(name, "int")
            dest: Optional[str] = None if rt == "void" else self._tmp()
            self._e(IR_CALL(dest, name, len(args)))
            return dest if dest else self._tmp()
        raise TypeError(f"Unknown expression: {type(expr)}")

    def _post_store(self, operand: Any, d: str) -> None:
        if isinstance(operand, Variable):
            self._e(STORE(operand.name, d))
        elif isinstance(operand, ArrayAccess):
            self._e(STORE_ARR(operand.array.name, self._expr(operand.index), d))


def ast_to_ir(program: Program) -> IRProgram:
    return IRBuilder().build(program)
