class SemanticError(Exception):
    """Represents an error found during semantic analysis."""
    pass


class Symbol:
    """Base class for all symbols stored in the symbol table."""
    def __init__(self, name, type_name):
        self.name = name
        self.type_name = type_name


class VarSymbol(Symbol):
    """Represents a variable (or parameter) in the symbol table."""
    def __init__(self, name, type_name, is_const=False, is_array=False):
        Symbol.__init__(self, name, type_name)
        self.is_const = is_const
        self.is_array = is_array


class FunctionSymbol(Symbol):
    """Represents a function in the symbol table."""
    def __init__(self, name, return_type, param_types):
        Symbol.__init__(self, name, return_type)
        self.param_types = param_types


class SymbolTable:
    """Simple symbol table with support for nested scopes."""
    def __init__(self, parent=None):
        # parent is another SymbolTable or None (for the global scope)
        self.parent = parent
        self.symbols = {}

    def define(self, symbol):
        """Add a new symbol to the current scope.

        Raises SemanticError if the name is already used in this scope.
        """
        if symbol.name in self.symbols:
            raise SemanticError("Redefinition of " + symbol.name)
        self.symbols[symbol.name] = symbol

    def lookup(self, name):
        """Find a symbol by name, searching this scope and all parents."""
        if name in self.symbols:
            return self.symbols[name]

        if self.parent is not None:
            return self.parent.lookup(name)

        return None

