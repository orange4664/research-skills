"""
SymPy → readable Python source code converter.
Generates human-readable code strings that can be copy-pasted.
"""
import sympy
from typing import Optional, List


def sympy_to_python_code(
    expr: sympy.Expr,
    symbol_names: Optional[List[str]] = None,
    func_name: str = "formula",
    docstring: Optional[str] = None,
) -> str:
    """
    Convert a SymPy expression into a pure Python function string.
    No external dependencies — just plain Python math.

    Args:
        expr: SymPy expression
        symbol_names: Input symbol names. Auto-detected if None.
        func_name: Name for the generated function
        docstring: Optional docstring

    Returns:
        Python source code string
    """
    if symbol_names is None:
        symbol_names = [str(s) for s in sorted(expr.free_symbols, key=lambda s: str(s))]

    args_str = ', '.join(symbol_names)

    # Use SymPy's pycode for clean Python output
    try:
        body = sympy.pycode(expr)
    except Exception:
        body = str(expr)

    # Build function
    doc = docstring or f"Auto-generated from SymPy: {expr}"
    lines = [
        f'import math',
        f'',
        f'def {func_name}({args_str}):',
        f'    """{doc}"""',
        f'    return {body}',
    ]

    return '\n'.join(lines)


def sympy_to_latex_roundtrip(expr: sympy.Expr) -> str:
    """Convert SymPy expression back to LaTeX for verification."""
    return sympy.latex(expr)


def format_expression_info(expr: sympy.Expr) -> str:
    """Generate a human-readable summary of a SymPy expression."""
    symbols = sorted(expr.free_symbols, key=lambda s: str(s))

    lines = [
        f"Expression: {expr}",
        f"LaTeX:      {sympy.latex(expr)}",
        f"Symbols:    {', '.join(str(s) for s in symbols)}",
        f"Type:       {type(expr).__name__}",
    ]

    # Try to simplify
    try:
        simplified = sympy.simplify(expr)
        if simplified != expr:
            lines.append(f"Simplified: {simplified}")
    except Exception:
        pass

    # Try to expand
    try:
        expanded = sympy.expand(expr)
        if expanded != expr:
            lines.append(f"Expanded:   {expanded}")
    except Exception:
        pass

    return '\n'.join(lines)
