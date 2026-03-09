"""
AST to Linear IR translation.

Walks the semantically-validated AST and emits three-address IR instructions.
Assumes semantic analysis has already run (main ensures this before calling IR).
"""

from __future__ import annotations
from typing import List, Optional, Any

from parser.ast import (
    Program,
    FunctionDecl,
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
from .ir import (
    Instruction,
    IRProgram,
    IRFunction,
    CONST,
    LOAD,
    STORE,
    LOAD_ARR,
    STORE_ARR,
    ALLOC_ARRAY,
    ADD,
    SUB,
    MUL,
    DIV,
    MOD,
    NEG,
    INC,
    DEC,
    LT,
    LE,
    GT,
    GE,
    EQ,
    NE,
    AND,
    OR,
    NOT,
    LABEL,
    JMP,
    JMP_IF,
    JMP_IF_NOT,
    PARAM,
    CALL as IR_CALL,
    RET,
    PRINT,
    READ_INT,
    EXIT,
    FUNC_ENTRY,
)


class IRBuilder:
    def __init__(self) -> None:
        self._temp_counter = 0
        self._label_counter = 0
        self._instructions: List[Instruction] = []
        self._loop_stack: List[tuple] = []  # (exit_label, head_label) per nested loop

    def _fresh_temp(self) -> str:
        t = f"%{self._temp_counter}"
        self._temp_counter += 1
        return t

    def _fresh_label(self) -> str:
        L = f"L{self._label_counter}"
        self._label_counter += 1
        return L

    def _emit(self, insn: Instruction) -> None:
        self._instructions.append(insn)

    def build(self, program: Program) -> IRProgram:
        self._return_types = {f.name: f.return_type for f in program.functions}
        ir_functions: List[IRFunction] = []
        for func in program.functions:
            ir_func = self._build_function(func)
            ir_functions.append(ir_func)
        return IRProgram(ir_functions)

    def _build_function(self, func: FunctionDecl) -> IRFunction:
        self._temp_counter = 0
        self._label_counter = 0
        self._instructions = []
        self._loop_stack = []

        param_names = [p.name for p in func.params]
        param_types = [p.param_type for p in func.params]
        self._emit(FUNC_ENTRY(func.name, func.return_type, param_names))

        self._build_block(func.body)
        return IRFunction(
            name=func.name,
            return_type=func.return_type,
            param_names=param_names,
            param_types=param_types,
            instructions=list(self._instructions),
        )

    def _build_block(self, block: Block) -> None:
        for decl in block.declarations:
            self._build_decl(decl)
        for stmt in block.statements:
            self._build_statement(stmt)

    def _build_decl(self, decl: VarDecl) -> None:
        if decl.size is not None:
            self._emit(ALLOC_ARRAY(decl.name, decl.size))
        if decl.initializer is not None:
            src = self._expr(decl.initializer)
            self._emit(STORE(decl.name, src))
        # Uninitialized vars: backend can zero or leave undefined per spec

    def _build_statement(self, stmt: Any) -> None:
        if isinstance(stmt, IfStmt):
            self._build_if(stmt)
        elif isinstance(stmt, WhileStmt):
            self._build_while(stmt)
        elif isinstance(stmt, ForStmt):
            self._build_for(stmt)
        elif isinstance(stmt, BreakStmt):
            exit_label = self._loop_stack[-1][0]
            self._emit(JMP(exit_label))
        elif isinstance(stmt, ContinueStmt):
            head_label = self._loop_stack[-1][1]
            self._emit(JMP(head_label))
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is None:
                self._emit(RET(None))
            else:
                t = self._expr(stmt.value)
                self._emit(RET(t))
        elif isinstance(stmt, ExprStmt):
            if stmt.expr is not None:
                self._expr(stmt.expr)
        elif isinstance(stmt, Block):
            self._build_block(stmt)
        else:
            raise TypeError(f"Unknown statement: {type(stmt)}")

    def _build_if(self, stmt: IfStmt) -> None:
        cond = self._expr(stmt.condition)
        else_label = self._fresh_label()
        end_label = self._fresh_label()
        self._emit(JMP_IF_NOT(cond, else_label))
        self._build_statement(stmt.then_branch)
        self._emit(JMP(end_label))
        self._emit(LABEL(else_label))
        if stmt.else_branch is not None:
            self._build_statement(stmt.else_branch)
        self._emit(LABEL(end_label))

    def _build_while(self, stmt: WhileStmt) -> None:
        head_label = self._fresh_label()
        exit_label = self._fresh_label()
        self._loop_stack.append((exit_label, head_label))
        self._emit(LABEL(head_label))
        cond = self._expr(stmt.condition)
        self._emit(JMP_IF_NOT(cond, exit_label))
        self._build_statement(stmt.body)
        self._emit(JMP(head_label))
        self._emit(LABEL(exit_label))
        self._loop_stack.pop()

    def _build_for(self, stmt: ForStmt) -> None:
        if stmt.init is not None:
            self._expr(stmt.init)
        head_label = self._fresh_label()
        exit_label = self._fresh_label()
        self._loop_stack.append((exit_label, head_label))
        self._emit(LABEL(head_label))
        if stmt.condition is not None:
            cond = self._expr(stmt.condition)
            self._emit(JMP_IF_NOT(cond, exit_label))
        self._build_statement(stmt.body)
        if stmt.increment is not None:
            self._expr(stmt.increment)
        self._emit(JMP(head_label))
        self._emit(LABEL(exit_label))
        self._loop_stack.pop()

    def _expr(self, expr: Any) -> str:
        """Evaluate expression and return the name of a temp (or variable) holding the result."""
        if isinstance(expr, Literal):
            dest = self._fresh_temp()
            kind = expr.kind
            val = expr.value
            if kind == "bool" and isinstance(val, bool):
                val = 1 if val else 0
            if kind == "char" and isinstance(val, str):
                val = ord(val) if len(val) == 1 else 0
            self._emit(CONST(dest, kind, val))
            return dest

        if isinstance(expr, Variable):
            dest = self._fresh_temp()
            self._emit(LOAD(dest, expr.name))
            return dest

        if isinstance(expr, Assign):
            value_temp = self._expr(expr.value)
            target = expr.target
            if isinstance(target, Variable):
                self._emit(STORE(target.name, value_temp))
                return value_temp
            if isinstance(target, ArrayAccess):
                arr = target.array.name
                idx = self._expr(target.index)
                self._emit(STORE_ARR(arr, idx, value_temp))
                return value_temp
            raise TypeError("Invalid assignment target")

        if isinstance(expr, BinaryOp):
            left = self._expr(expr.left)
            right = self._expr(expr.right)
            dest = self._fresh_temp()
            op = expr.op
            if op == "+":
                self._emit(ADD(dest, left, right))
            elif op == "-":
                self._emit(SUB(dest, left, right))
            elif op == "*":
                self._emit(MUL(dest, left, right))
            elif op == "/":
                self._emit(DIV(dest, left, right))
            elif op == "%":
                self._emit(MOD(dest, left, right))
            elif op == "<":
                self._emit(LT(dest, left, right))
            elif op == "<=":
                self._emit(LE(dest, left, right))
            elif op == ">":
                self._emit(GT(dest, left, right))
            elif op == ">=":
                self._emit(GE(dest, left, right))
            elif op == "==":
                self._emit(EQ(dest, left, right))
            elif op == "!=":
                self._emit(NE(dest, left, right))
            elif op == "&&":
                self._emit(AND(dest, left, right))
            elif op == "||":
                self._emit(OR(dest, left, right))
            else:
                raise ValueError(f"Unknown binary op: {op}")
            return dest

        if isinstance(expr, UnaryOp):
            src = self._expr(expr.operand)
            dest = self._fresh_temp()
            op = expr.op
            if op == "!":
                self._emit(NOT(dest, src))
            elif op == "-":
                self._emit(NEG(dest, src))
            elif op == "++":
                self._emit(INC(dest, src))
                if isinstance(expr.operand, Variable):
                    self._emit(STORE(expr.operand.name, dest))
                elif isinstance(expr.operand, ArrayAccess):
                    self._emit(STORE_ARR(expr.operand.array.name, self._expr(expr.operand.index), dest))
                if expr.postfix:
                    dest = src  # postfix returns value before increment
            elif op == "--":
                self._emit(DEC(dest, src))
                if isinstance(expr.operand, Variable):
                    self._emit(STORE(expr.operand.name, dest))
                elif isinstance(expr.operand, ArrayAccess):
                    self._emit(STORE_ARR(expr.operand.array.name, self._expr(expr.operand.index), dest))
                if expr.postfix:
                    dest = src  # postfix returns value before decrement
            else:
                raise ValueError(f"Unknown unary op: {op}")
            return dest

        if isinstance(expr, ArrayAccess):
            dest = self._fresh_temp()
            arr = expr.array.name
            idx = self._expr(expr.index)
            self._emit(LOAD_ARR(dest, arr, idx))
            return dest

        if isinstance(expr, Call):
            callee_name = expr.callee.name
            if callee_name == "print":
                args = [self._expr(a) for a in expr.args]
                self._emit(PRINT(args))
                return self._fresh_temp()  # print returns void; caller should ignore
            if callee_name == "readInt":
                dest = self._fresh_temp()
                self._emit(READ_INT(dest))
                return dest
            if callee_name == "exit":
                code = self._expr(expr.args[0])
                self._emit(EXIT(code))
                return self._fresh_temp()
            # User function
            arg_temps = [self._expr(a) for a in expr.args]
            for a in arg_temps:
                self._emit(PARAM(a))
            return_type = self._return_types.get(callee_name, "int")
            dest = None if return_type == "void" else self._fresh_temp()
            self._emit(IR_CALL(dest, callee_name, len(arg_temps)))
            return dest if dest is not None else self._fresh_temp()

        raise TypeError(f"Unknown expression: {type(expr)}")


def ast_to_ir(program: Program) -> IRProgram:
    """Convert AST program to linear IR."""
    builder = IRBuilder()
    return builder.build(program)
