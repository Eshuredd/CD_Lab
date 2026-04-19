from parser.ast import *
from symbol_table import *


class TypeChecker:

    def __init__(self):
        self.supported_types = ["int", "uint32", "float", "bool", "char", "void"]
        self.global_symbols = SymbolTable()
        self.current_function_def = None
        self._loop_depth = 0    # for continue: must be inside a loop
        self._switch_depth = 0  # for break: also valid inside switch

        # Built-in functions
        self.global_symbols.define(FunctionSymbol("readInt", "int", []))
        self.global_symbols.define(FunctionSymbol("print", "void", []))
        self.global_symbols.define(FunctionSymbol("exit", "void", ["int"]))

    def _err(self, msg: str, node) -> None:
        line = getattr(node, "line", None)
        col = getattr(node, "column", None)
        raise SemanticError(msg, line=line, column=col)

    def analyze(self, program):

        for function in program.functions:
            if function.return_type not in self.supported_types:
                self._err("Invalid return type", function)

            parameter_types = []
            for param in function.params:
                if param.param_type not in self.supported_types:
                    self._err("Invalid parameter type", param)
                parameter_types.append(param.param_type)

            self.global_symbols.define(
                FunctionSymbol(function.name, function.return_type, parameter_types)
            )

        if self.global_symbols.lookup("main") is None:
            self._err("main function missing", program)

        for function in program.functions:
            self.check_function(function)

    def check_function(self, function_def):
        self.current_function_def = function_def
        function_scope = SymbolTable(self.global_symbols)

        for param in function_def.params:
            function_scope.define(VarSymbol(param.name, param.param_type))

        self.check_block(function_def.body, function_scope)
        self.current_function_def = None

    def check_block(self, block, parent_scope):
        local_scope = SymbolTable(parent_scope)

        for declaration in block.declarations:
            if declaration.var_type not in self.supported_types:
                self._err("Invalid variable type", declaration)

            local_scope.define(
                VarSymbol(
                    declaration.name,
                    declaration.var_type,
                    declaration.is_const,
                    declaration.size is not None,
                )
            )

            if declaration.initializer:
                initializer_type = self.check_expression(
                    declaration.initializer, local_scope
                )
                if initializer_type != declaration.var_type:
                    self._err("Type mismatch in initialization", declaration)

        for statement in block.statements:
            self.check_statement(statement, local_scope)

    def check_statement(self, statement, scope):

        if isinstance(statement, IfStmt):
            condition_type = self.check_expression(statement.condition, scope)
            if condition_type != "bool":
                self._err("If condition must be bool", statement.condition)

            self.check_statement(statement.then_branch, scope)
            if statement.else_branch:
                self.check_statement(statement.else_branch, scope)

        elif isinstance(statement, WhileStmt):
            condition_type = self.check_expression(statement.condition, scope)
            if condition_type != "bool":
                self._err("While condition must be bool", statement.condition)

            self._loop_depth += 1
            try:
                self.check_statement(statement.body, scope)
            finally:
                self._loop_depth -= 1

        elif isinstance(statement, ForStmt):
            if statement.init:
                self.check_expression(statement.init, scope)

            if statement.condition:
                condition_type = self.check_expression(statement.condition, scope)
                if condition_type != "bool":
                    self._err("For condition must be bool", statement.condition)

            if statement.increment:
                self.check_expression(statement.increment, scope)

            self._loop_depth += 1
            try:
                self.check_statement(statement.body, scope)
            finally:
                self._loop_depth -= 1

        elif isinstance(statement, BreakStmt):
            if self._loop_depth <= 0 and self._switch_depth <= 0:
                self._err("break outside loop or switch", statement)

        elif isinstance(statement, ContinueStmt):
            if self._loop_depth <= 0:
                self._err("continue outside loop", statement)

        elif isinstance(statement, SwitchStmt):
            subj_type = self.check_expression(statement.expr, scope)
            if subj_type not in ("int", "uint32", "char"):
                self._err("switch expression must be int, uint32, or char", statement)
            seen_default = False
            self._switch_depth += 1
            try:
                for clause in statement.cases:
                    if clause.value is None:
                        if seen_default:
                            self._err("duplicate default in switch", clause)
                        seen_default = True
                    else:
                        val_type = self.check_expression(clause.value, scope)
                        if val_type != subj_type:
                            self._err("case value type does not match switch expression", clause.value)
                    for stmt in clause.body:
                        self.check_statement(stmt, scope)
            finally:
                self._switch_depth -= 1

        elif isinstance(statement, ReturnStmt):
            expected_type = self.current_function_def.return_type

            if statement.value is None:
                if expected_type != "void":
                    self._err("Return value required", statement)
            else:
                value_type = self.check_expression(statement.value, scope)
                if value_type != expected_type:
                    self._err("Return type mismatch", statement)

        elif isinstance(statement, ExprStmt):
            if statement.expr:
                self.check_expression(statement.expr, scope)

        elif isinstance(statement, Block):
            self.check_block(statement, scope)

    def check_expression(self, expression, scope):

        if isinstance(expression, Literal):
            return expression.kind

        if isinstance(expression, Variable):
            symbol = scope.lookup(expression.name)
            if symbol is None:
                self._err("Variable not declared", expression)
            if isinstance(symbol, FunctionSymbol):
                self._err("Function used as variable", expression)
            return symbol.type_name

        if isinstance(expression, Assign):
            # Assignment targets may be either:
            #   - a variable:    x = expr;
            #   - an array elem: arr[i] = expr;
            if isinstance(expression.target, Variable):
                symbol = scope.lookup(expression.target.name)
                if symbol is None:
                    self._err("Variable not declared", expression.target)
                value_type = self.check_expression(expression.value, scope)
                if value_type != symbol.type_name:
                    self._err("Assignment type mismatch", expression)
                return symbol.type_name

            if isinstance(expression.target, ArrayAccess):
                symbol = scope.lookup(expression.target.array.name)
                if symbol is None:
                    self._err("Array not declared", expression.target.array)
                if not getattr(symbol, "is_array", False):
                    self._err("Array not declared", expression.target.array)

                index_type = self.check_expression(expression.target.index, scope)
                if index_type not in ["int", "uint32"]:
                    self._err("Invalid index type", expression.target.index)

                value_type = self.check_expression(expression.value, scope)
                if value_type != symbol.type_name:
                    self._err("Assignment type mismatch", expression)
                return symbol.type_name

            self._err("Invalid assignment", expression)

        if isinstance(expression, BinaryOp):
            left_type = self.check_expression(expression.left, scope)
            right_type = self.check_expression(expression.right, scope)

            if left_type != right_type:
                self._err("Type mismatch in binary op", expression)

            if expression.op in ["+", "-", "*", "/", "%"]:
                return left_type

            if expression.op in ["<", ">", "<=", ">=", "==", "!="]:
                return "bool"

            if expression.op in ["&&", "||"]:
                if left_type != "bool":
                    self._err("Logical op needs bool", expression)
                return "bool"

        if isinstance(expression, UnaryOp):
            operand_type = self.check_expression(expression.operand, scope)

            if expression.op == "!":
                if operand_type != "bool":
                    self._err("! needs bool", expression)
                return "bool"

            if expression.op in ["-", "++", "--"]:
                return operand_type

        if isinstance(expression, Call):
            symbol = self.global_symbols.lookup(expression.callee.name)
            if symbol is None:
                self._err("Function not declared", expression)

            if expression.callee.name == "print":
                for arg in expression.args:
                    self.check_expression(arg, scope)
                return "void"

            if expression.callee.name == "exit":
                if len(expression.args) != 1:
                    self._err("exit requires exactly one argument (exit code)", expression)
                code_type = self.check_expression(expression.args[0], scope)
                if code_type not in ["int", "uint32"]:
                    self._err("exit code must be int or uint32", expression.args[0])
                return "void"

            if len(expression.args) != len(symbol.param_types):
                self._err("Wrong number of arguments", expression)

            for index in range(len(expression.args)):
                argument_type = self.check_expression(expression.args[index], scope)
                if argument_type != symbol.param_types[index]:
                    self._err("Argument type mismatch", expression.args[index])

            return symbol.type_name

        if isinstance(expression, ArrayAccess):
            symbol = scope.lookup(expression.array.name)
            if symbol is None:
                self._err("Array not declared", expression.array)

            index_type = self.check_expression(expression.index, scope)
            if index_type not in ["int", "uint32"]:
                self._err("Invalid index type", expression.index)

            return symbol.type_name

        self._err("Invalid expression", expression)