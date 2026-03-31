"""
SymPy → NumPy function converter.
Uses sympy.lambdify with numpy module.
"""
import sympy
from typing import Optional, List, Callable, Tuple


def sympy_to_numpy(
    expr: sympy.Expr,
    symbols: Optional[List[sympy.Symbol]] = None,
) -> Tuple[Optional[Callable], List[str], str]:
    """
    Convert a SymPy expression into a NumPy callable function.

    Args:
        expr: SymPy expression
        symbols: Ordered list of input symbols. Auto-detected if None.

    Returns:
        Tuple of (numpy_function, symbol_names, code_string)
    """
    if symbols is None:
        symbols = sorted(expr.free_symbols, key=lambda s: str(s))

    symbol_names = [str(s) for s in symbols]

    try:
        func = sympy.lambdify(symbols, expr, modules="numpy")
    except Exception as e:
        return None, symbol_names, f"# Error: {e}"

    code = generate_numpy_code(expr, symbol_names)
    return func, symbol_names, code


def generate_numpy_code(expr: sympy.Expr, symbol_names: Optional[List[str]] = None) -> str:
    """Generate human-readable NumPy code from a SymPy expression."""
    if symbol_names is None:
        symbol_names = [str(s) for s in sorted(expr.free_symbols, key=lambda s: str(s))]

    args_str = ', '.join(symbol_names)
    code_body = _sympy_to_numpy_str(expr)

    code = f'''import numpy as np

def formula({args_str}):
    """
    Auto-generated from LaTeX formula.
    SymPy expression: {expr}
    """
    return {code_body}
'''
    return code


def _sympy_to_numpy_str(expr: sympy.Expr) -> str:
    """Convert SymPy expression to NumPy-compatible Python string."""
    s = str(expr)

    replacements = [
        ('exp(', 'np.exp('),
        ('log(', 'np.log('),
        ('sqrt(', 'np.sqrt('),
        ('sin(', 'np.sin('),
        ('cos(', 'np.cos('),
        ('tan(', 'np.tan('),
        ('asin(', 'np.arcsin('),
        ('acos(', 'np.arccos('),
        ('atan(', 'np.arctan('),
        ('Abs(', 'np.abs('),
        ('sign(', 'np.sign('),
        ('floor(', 'np.floor('),
        ('ceiling(', 'np.ceil('),
        ('Max(', 'np.maximum('),
        ('Min(', 'np.minimum('),
        ('pi', 'np.pi'),
        ('Sum(', 'np.sum('),
    ]

    for old, new in replacements:
        if new not in s:
            s = s.replace(old, new)

    return s
