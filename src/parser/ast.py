class Program:
    def __init__(self, functions):
        self.functions = functions

class VarDecl:
    def __init__(self, var_type, name):
        self.var_type = var_type
        self.name = name

class Assign:
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr
