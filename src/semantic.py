from parser.ast import (
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


class SemanticError(Exception):
    pass


class Symbol:
    def __init__(self, name, type_name):
        self.name = name
        self.type_name = type_name


class VarSymbol(Symbol):
    def __init__(self, name, type_name, is_const=False, is_array=False):
        Symbol.__init__(self, name, type_name)
        self.is_const = is_const
        self.is_array = is_array


class FunctionSymbol(Symbol):
    def __init__(self, name, return_type, param_types):
        Symbol.__init__(self, name, return_type)
        self.param_types = param_types


class SymbolTable:
    def __init__(self, parent=None):
        self.parent = parent
        self.symbols = {}

    def define(self, symbol):
        if symbol.name in self.symbols:
            raise SemanticError("Redefinition of " + symbol.name)
        self.symbols[symbol.name] = symbol

    def lookup(self, name):
        if name in self.symbols:
            return self.symbols[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None


class SemanticAnalyzer:
    def __init__(self):
        self.types = ["uint32", "int", "float", "bool", "char", "void"]
        self.global_table = SymbolTable()
        self.current_function = None

        # built-in functions
        # readInt() -> int
        self.global_table.define(FunctionSymbol("readInt", "int", []))
        # print(...) -> void, any arguments (checked specially)
        self.global_table.define(FunctionSymbol("print", "void", []))

    def analyze(self, program):
        if not isinstance(program, Program):
            raise SemanticError("Expected Program node")

        # first pass: collect functions
        for func in program.functions:
            self._register_function(func)

        # check main exists
        if self.global_table.lookup("main") is None:
            raise SemanticError("No 'main' function defined")

        # second pass: check each function body
        for func in program.functions:
            self._check_function(func)

    def _register_function(self, func):
        if not isinstance(func, FunctionDecl):
            return

        if func.return_type not in self.types:
            raise SemanticError("Unknown return type: " + str(func.return_type))

        param_types = []
        for p in func.params:
            if p.param_type not in self.types:
                raise SemanticError("Unknown parameter type: " + str(p.param_type))
            param_types.append(p.param_type)

        sym = FunctionSymbol(func.name, func.return_type, param_types)
        self.global_table.define(sym)

    def _check_function(self, func):
        self.current_function = func
        table = SymbolTable(self.global_table)

        # parameters
        for p in func.params:
            var_sym = VarSymbol(p.name, p.param_type, is_const=False, is_array=False)
            table.define(var_sym)

        self._check_block(func.body, table)
        self.current_function = None

    def _check_block(self, block, table):
        if not isinstance(block, Block):
            return

        local = SymbolTable(table)

        for decl in block.declarations:
            self._check_vardecl(decl, local)

        for stmt in block.statements:
            self._check_statement(stmt, local)

    def _check_vardecl(self, decl, table):
        if decl.var_type not in self.types:
            raise SemanticError("Unknown type: " + str(decl.var_type))

        is_array = decl.size is not None
        sym = VarSymbol(decl.name, decl.var_type, decl.is_const, is_array)
        table.define(sym)

        if decl.initializer is not None:
            init_type = self._check_expression(decl.initializer, table)
            if init_type != decl.var_type:
                raise SemanticError("Type mismatch in initializer of " + decl.name)

    def _check_statement(self, stmt, table):
        if isinstance(stmt, IfStmt):
            cond_type = self._check_expression(stmt.condition, table)
            if cond_type != "bool":
                raise SemanticError("Condition in if must be bool")
            self._check_statement(stmt.then_branch, table)
            if stmt.else_branch is not None:
                self._check_statement(stmt.else_branch, table)

        elif isinstance(stmt, WhileStmt):
            cond_type = self._check_expression(stmt.condition, table)
            if cond_type != "bool":
                raise SemanticError("Condition in while must be bool")
            self._check_statement(stmt.body, table)

        elif isinstance(stmt, ForStmt):
            if stmt.init is not None:
                self._check_expression(stmt.init, table)
            if stmt.condition is not None:
                cond_type = self._check_expression(stmt.condition, table)
                if cond_type != "bool":
                    raise SemanticError("Condition in for must be bool")
            if stmt.increment is not None:
                self._check_expression(stmt.increment, table)
            self._check_statement(stmt.body, table)

        elif isinstance(stmt, BreakStmt):
            # not checking loop nesting for simplicity
            return

        elif isinstance(stmt, ContinueStmt):
            # not checking loop nesting for simplicity
            return

        elif isinstance(stmt, ReturnStmt):
            func_ret = self.current_function.return_type
            if stmt.value is None:
                if func_ret != "void":
                    raise SemanticError("Return with no value in non-void function")
            else:
                value_type = self._check_expression(stmt.value, table)
                if func_ret == "void":
                    raise SemanticError("Return with value in void function")
                if value_type != func_ret:
                    raise SemanticError("Return type mismatch in function " + self.current_function.name)

        elif isinstance(stmt, ExprStmt):
            if stmt.expr is not None:
                self._check_expression(stmt.expr, table)

        elif isinstance(stmt, Block):
            self._check_block(stmt, table)

        else:
            raise SemanticError("Unknown statement type: " + str(type(stmt)))

    def _check_expression(self, expr, table):
        if isinstance(expr, Literal):
            if expr.kind == "int":
                return "int"
            if expr.kind == "float":
                return "float"
            if expr.kind == "bool":
                return "bool"
            if expr.kind == "char":
                return "char"
            if expr.kind == "string":
                return "string"
            raise SemanticError("Unknown literal kind: " + str(expr.kind))

        if isinstance(expr, Variable):
            sym = table.lookup(expr.name)
            if sym is None:
                raise SemanticError("Undeclared variable: " + expr.name)
            if isinstance(sym, FunctionSymbol):
                raise SemanticError("Function used as value: " + expr.name)
            return sym.type_name

        if isinstance(expr, ArrayAccess):
            if not isinstance(expr.array, Variable):
                raise SemanticError("Array access must use array variable")
            sym = table.lookup(expr.array.name)
            if sym is None or not isinstance(sym, VarSymbol):
                raise SemanticError("Undeclared array: " + expr.array.name)
            if not sym.is_array:
                raise SemanticError("Variable is not an array: " + expr.array.name)
            index_type = self._check_expression(expr.index, table)
            if index_type not in ["int", "uint32"]:
                raise SemanticError("Array index must be int or uint32")
            return sym.type_name

        if isinstance(expr, Assign):
            if isinstance(expr.target, Variable):
                target_sym = table.lookup(expr.target.name)
                if target_sym is None or not isinstance(target_sym, VarSymbol):
                    raise SemanticError("Assignment to undeclared variable: " + expr.target.name)
                value_type = self._check_expression(expr.value, table)
                if value_type != target_sym.type_name:
                    raise SemanticError("Type mismatch in assignment to " + expr.target.name)
                return target_sym.type_name
            elif isinstance(expr.target, ArrayAccess):
                # reuse the array element type rules
                array_type = self._check_expression(expr.target, table)
                value_type = self._check_expression(expr.value, table)
                if value_type != array_type:
                    raise SemanticError("Type mismatch in array assignment")
                return array_type
            else:
                raise SemanticError("Invalid assignment target")

        if isinstance(expr, UnaryOp):
            t = self._check_expression(expr.operand, table)
            if expr.op == "!":
                if t != "bool":
                    raise SemanticError("Operator ! expects bool")
                return "bool"
            if expr.op == "-":
                if t not in ["int", "uint32", "float"]:
                    raise SemanticError("Unary - expects number")
                return t
            if expr.op in ["++", "--"]:
                if not isinstance(expr.operand, Variable) and not isinstance(expr.operand, ArrayAccess):
                    raise SemanticError("++/-- must be used on variable or array element")
                if t not in ["int", "uint32", "float"]:
                    raise SemanticError("++/-- expects number")
                return t
            raise SemanticError("Unknown unary operator: " + str(expr.op))

        if isinstance(expr, BinaryOp):
            left_type = self._check_expression(expr.left, table)
            right_type = self._check_expression(expr.right, table)

            if expr.op in ["+", "-", "*", "/", "%"]:
                if left_type != right_type:
                    raise SemanticError("Operands of " + expr.op + " must have same type")
                if left_type not in ["int", "uint32", "float"]:
                    raise SemanticError("Operator " + expr.op + " expects numeric types")
                if expr.op == "%" and left_type not in ["int", "uint32"]:
                    raise SemanticError("Operator % expects integer type")
                return left_type

            if expr.op in ["<", ">", "<=", ">="]:
                if left_type != right_type:
                    raise SemanticError("Operands of " + expr.op + " must have same type")
                if left_type not in ["int", "uint32", "float"]:
                    raise SemanticError("Operator " + expr.op + " expects numeric types")
                return "bool"

            if expr.op in ["==", "!="]:
                if left_type != right_type:
                    raise SemanticError("Operands of " + expr.op + " must have same type")
                return "bool"

            if expr.op in ["&&", "||"]:
                if left_type != "bool" or right_type != "bool":
                    raise SemanticError("Logical operators expect bool operands")
                return "bool"

            raise SemanticError("Unknown binary operator: " + str(expr.op))

        if isinstance(expr, Call):
            if not isinstance(expr.callee, Variable):
                raise SemanticError("Can only call functions by name")

            name = expr.callee.name
            sym = self.global_table.lookup(name)
            if sym is None or not isinstance(sym, FunctionSymbol):
                raise SemanticError("Undeclared function: " + name)

            # print: allow any number of arguments
            if name == "print":
                for a in expr.args:
                    self._check_expression(a, table)
                return "void"

            # readInt: no arguments
            if name == "readInt":
                if len(expr.args) != 0:
                    raise SemanticError("readInt takes no arguments")
                return "int"

            if len(expr.args) != len(sym.param_types):
                raise SemanticError("Wrong number of arguments in call to " + name)

            for i in range(len(expr.args)):
                arg_type = self._check_expression(expr.args[i], table)
                expected = sym.param_types[i]
                if arg_type != expected:
                    raise SemanticError("Type mismatch in argument " + str(i + 1) + " of " + name)

            return sym.type_name

        if isinstance(expr, ExprStmt):
            if expr.expr is None:
                return "void"
            return self._check_expression(expr.expr, table)

        raise SemanticError("Unknown expression type: " + str(type(expr)))

