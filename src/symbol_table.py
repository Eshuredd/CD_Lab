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

