from parser.ast import *
from symbol_table import *


class TypeChecker:

    def __init__(self):
        self.supported_types = ["int", "uint32", "float", "bool", "char", "void"]
        self.global_symbols = SymbolTable()
        self.current_function_def = None

        # Built-in functions
        self.global_symbols.define(FunctionSymbol("readInt", "int", []))
        self.global_symbols.define(FunctionSymbol("print", "void", []))

    def analyze(self, program):

        for function in program.functions:
            if function.return_type not in self.supported_types:
                raise SemanticError("Invalid return type")

            parameter_types = []
            for param in function.params:
                if param.param_type not in self.supported_types:
                    raise SemanticError("Invalid parameter type")
                parameter_types.append(param.param_type)

            self.global_symbols.define(
                FunctionSymbol(function.name, function.return_type, parameter_types)
            )

        if self.global_symbols.lookup("main") is None:
            raise SemanticError("main function missing")

        # Second pass
        for function in program.functions:
            self.check_function(function)

    def check_function(self, function_def):
        self.current_function_def = function_def
        function_scope = SymbolTable(self.global_symbols)

        # add parameters
        for param in function_def.params:
            function_scope.define(VarSymbol(param.name, param.param_type))

        self.check_block(function_def.body, function_scope)
        self.current_function_def = None

    def check_block(self, block, parent_scope):
        local_scope = SymbolTable(parent_scope)

        for declaration in block.declarations:
            if declaration.var_type not in self.supported_types:
                raise SemanticError("Invalid variable type")

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
                    raise SemanticError("Type mismatch in initialization")

        for statement in block.statements:
            self.check_statement(statement, local_scope)

    def check_statement(self, statement, scope):

        if isinstance(statement, IfStmt):
            condition_type = self.check_expression(statement.condition, scope)
            if condition_type != "bool":
                raise SemanticError("If condition must be bool")

            self.check_statement(statement.then_branch, scope)
            if statement.else_branch:
                self.check_statement(statement.else_branch, scope)

        elif isinstance(statement, WhileStmt):
            condition_type = self.check_expression(statement.condition, scope)
            if condition_type != "bool":
                raise SemanticError("While condition must be bool")

            self.check_statement(statement.body, scope)

        elif isinstance(statement, ForStmt):
            if statement.init:
                self.check_expression(statement.init, scope)

            if statement.condition:
                condition_type = self.check_expression(statement.condition, scope)
                if condition_type != "bool":
                    raise SemanticError("For condition must be bool")

            if statement.increment:
                self.check_expression(statement.increment, scope)

            self.check_statement(statement.body, scope)

        elif isinstance(statement, ReturnStmt):
            expected_type = self.current_function_def.return_type

            if statement.value is None:
                if expected_type != "void":
                    raise SemanticError("Return value required")
            else:
                value_type = self.check_expression(statement.value, scope)
                if value_type != expected_type:
                    raise SemanticError("Return type mismatch")

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
                raise SemanticError("Variable not declared")
            if isinstance(symbol, FunctionSymbol):
                raise SemanticError("Function used as variable")
            return symbol.type_name

        if isinstance(expression, Assign):
            if not isinstance(expression.target, Variable):
                raise SemanticError("Invalid assignment")

            symbol = scope.lookup(expression.target.name)
            if symbol is None:
                raise SemanticError("Variable not declared")

            value_type = self.check_expression(expression.value, scope)
            if value_type != symbol.type_name:
                raise SemanticError("Assignment type mismatch")

            return symbol.type_name

        if isinstance(expression, BinaryOp):
            left_type = self.check_expression(expression.left, scope)
            right_type = self.check_expression(expression.right, scope)

            if left_type != right_type:
                raise SemanticError("Type mismatch in binary op")

            if expression.op in ["+", "-", "*", "/", "%"]:
                return left_type

            if expression.op in ["<", ">", "<=", ">=", "==", "!="]:
                return "bool"

            if expression.op in ["&&", "||"]:
                if left_type != "bool":
                    raise SemanticError("Logical op needs bool")
                return "bool"

        if isinstance(expression, UnaryOp):
            operand_type = self.check_expression(expression.operand, scope)

            if expression.op == "!":
                if operand_type != "bool":
                    raise SemanticError("! needs bool")
                return "bool"

            if expression.op in ["-", "++", "--"]:
                return operand_type

        if isinstance(expression, Call):
            symbol = self.global_symbols.lookup(expression.callee.name)
            if symbol is None:
                raise SemanticError("Function not declared")

            if expression.callee.name == "print":
                for arg in expression.args:
                    self.check_expression(arg, scope)
                return "void"

            if len(expression.args) != len(symbol.param_types):
                raise SemanticError("Wrong number of arguments")

            for index in range(len(expression.args)):
                argument_type = self.check_expression(expression.args[index], scope)
                if argument_type != symbol.param_types[index]:
                    raise SemanticError("Argument type mismatch")

            return symbol.type_name

        if isinstance(expression, ArrayAccess):
            symbol = scope.lookup(expression.array.name)
            if symbol is None:
                raise SemanticError("Array not declared")

            index_type = self.check_expression(expression.index, scope)
            if index_type not in ["int", "uint32"]:
                raise SemanticError("Invalid index type")

            return symbol.type_name

        raise SemanticError("Invalid expression")