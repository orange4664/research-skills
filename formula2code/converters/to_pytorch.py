"""
SymPy → PyTorch code converter.
Uses sympytorch for nn.Module generation, and sympy.lambdify for function generation.
"""
import sympy
from typing import Optional, List, Dict, Any

# Try importing optional deps
try:
    import sympytorch
    HAS_SYMPYTORCH = True
except ImportError:
    HAS_SYMPYTORCH = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ── Custom SymPy functions for ML ops ───────────────────────────────────────
# These bridge the gap between what SymPy supports and what PyTorch needs.

class Softmax(sympy.Function):
    """Symbolic softmax for use in SymPy expressions."""
    pass

class ReLU(sympy.Function):
    """Symbolic ReLU."""
    pass

class MatMul(sympy.Function):
    """Symbolic batch matrix multiply."""
    pass

class LayerNorm(sympy.Function):
    """Symbolic layer normalization."""
    pass


def _get_extra_funcs() -> dict:
    """Get mapping from custom SymPy functions to PyTorch implementations."""
    if not HAS_TORCH:
        return {}
    import torch
    import torch.nn.functional as F
    return {
        Softmax: lambda x: F.softmax(x, dim=-1),
        ReLU: torch.relu,
        MatMul: lambda a, b: torch.matmul(a, b),
        LayerNorm: lambda x: F.layer_norm(x, x.shape[-1:]),
    }


def sympy_to_pytorch_module(
    expr: sympy.Expr,
    name: str = "FormulaModule",
    trainable_floats: bool = False,
) -> Optional[Any]:
    """
    Convert a SymPy expression into a PyTorch nn.Module via sympytorch.

    Args:
        expr: SymPy expression
        name: Name for the generated module class
        trainable_floats: If True, float constants become nn.Parameter (trainable).
                         If False, floats are fixed buffers.

    Returns:
        sympytorch.SymPyModule instance, or None if sympytorch not available
    """
    if not HAS_SYMPYTORCH:
        return None

    # Optionally freeze float constants
    if not trainable_floats:
        expr = sympytorch.hide_floats(expr)

    module = sympytorch.SymPyModule(
        expressions=[expr],
        extra_funcs=_get_extra_funcs(),
    )
    return module


def sympy_to_pytorch_function(expr: sympy.Expr, symbols: Optional[List[sympy.Symbol]] = None):
    """
    Convert a SymPy expression into a callable PyTorch function via lambdify.

    Args:
        expr: SymPy expression
        symbols: Ordered list of input symbols. If None, auto-detected and sorted.

    Returns:
        Callable that accepts torch tensors
    """
    if symbols is None:
        symbols = sorted(expr.free_symbols, key=lambda s: str(s))

    func = sympy.lambdify(symbols, expr, modules="torch")
    return func, symbols


def sympy_to_pytorch(
    expr: sympy.Expr,
    as_module: bool = True,
    trainable_floats: bool = False,
) -> Dict[str, Any]:
    """
    Convert SymPy expression to PyTorch in both module and function form.

    Returns dict with:
        - module: sympytorch.SymPyModule (if sympytorch available)
        - function: lambdify'd callable
        - symbols: list of input symbol names
        - code: human-readable PyTorch code string
    """
    symbols = sorted(expr.free_symbols, key=lambda s: str(s))
    symbol_names = [str(s) for s in symbols]

    result = {
        'module': None,
        'function': None,
        'symbols': symbol_names,
        'code': generate_pytorch_code(expr, symbol_names),
    }

    # Module via sympytorch
    if as_module and HAS_SYMPYTORCH:
        try:
            result['module'] = sympy_to_pytorch_module(expr, trainable_floats=trainable_floats)
        except Exception as e:
            result['module_error'] = str(e)

    # Function via lambdify
    try:
        func, _ = sympy_to_pytorch_function(expr, symbols)
        result['function'] = func
    except Exception as e:
        result['function_error'] = str(e)

    return result


def generate_pytorch_code(expr: sympy.Expr, symbol_names: Optional[List[str]] = None) -> str:
    """
    Generate human-readable PyTorch code string from a SymPy expression.

    This produces a standalone function definition that can be copy-pasted.
    """
    if symbol_names is None:
        symbol_names = [str(s) for s in sorted(expr.free_symbols, key=lambda s: str(s))]

    args_str = ', '.join(symbol_names)

    # Convert SymPy expr to Python code string
    code_body = _sympy_to_torch_str(expr)

    code = f'''import torch
import torch.nn.functional as F

def formula({args_str}):
    """
    Auto-generated from LaTeX formula.
    SymPy expression: {expr}
    """
    return {code_body}
'''
    return code


def _sympy_to_torch_str(expr: sympy.Expr) -> str:
    """
    Convert a SymPy expression to a PyTorch-compatible Python string.
    Handles common operations that need torch.* instead of math.*.
    """
    s = str(expr)

    # SymPy → PyTorch replacements
    replacements = [
        ('exp(', 'torch.exp('),
        ('log(', 'torch.log('),
        ('sqrt(', 'torch.sqrt('),
        ('sin(', 'torch.sin('),
        ('cos(', 'torch.cos('),
        ('tan(', 'torch.tan('),
        ('asin(', 'torch.asin('),
        ('acos(', 'torch.acos('),
        ('atan(', 'torch.atan('),
        ('Abs(', 'torch.abs('),
        ('sign(', 'torch.sign('),
        ('floor(', 'torch.floor('),
        ('ceiling(', 'torch.ceil('),
        ('Max(', 'torch.maximum('),
        ('Min(', 'torch.minimum('),
        ('pi', 'torch.pi'),
    ]

    for old, new in replacements:
        # Avoid double-replacing (e.g., torch.torch.exp)
        if new not in s:
            s = s.replace(old, new)

    # SymPy uses ** for power, which is fine in Python/PyTorch
    # SymPy Sum → torch.sum (simplified)
    s = s.replace('Sum(', 'torch.sum(')

    return s
