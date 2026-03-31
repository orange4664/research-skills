"""
LaTeX → SymPy expression parser.
Wraps latex2sympy2_extended with preprocessing for ML-specific notation.
"""
import re
import sympy
from typing import Optional, Tuple, List

# Try importing latex2sympy2_extended; fall back gracefully
try:
    from latex2sympy2_extended import latex2sympy as _latex2sympy
    HAS_LATEX2SYMPY = True
except ImportError:
    HAS_LATEX2SYMPY = False


# ── Pre-processing rules ────────────────────────────────────────────────────
# latex2sympy2 does NOT understand ML-specific macros like \text{softmax}.
# We clean these up before parsing so the ANTLR grammar can handle them.

_PREPROCESS_RULES = [
    # \text{...} → remove wrapper (keep content as plain identifier)
    (r'\\text\{([^}]+)\}', r'\1'),
    # \operatorname{...} → same
    (r'\\operatorname\{([^}]+)\}', r'\1'),
    # \mathcal{L} → L  (common for loss)
    (r'\\mathcal\{([^}]+)\}', r'\1'),
    # \mathbb{E} → E  (expectation)
    (r'\\mathbb\{([^}]+)\}', r'\1'),
    # \hat{x} → x_hat  (make it a valid symbol)
    (r'\\hat\{([^}]+)\}', r'\1_hat'),
    # \bar{x} → x_bar
    (r'\\bar\{([^}]+)\}', r'\1_bar'),
    # \tilde{x} → x_tilde
    (r'\\tilde\{([^}]+)\}', r'\1_tilde'),
    # \boldsymbol{x} → x
    (r'\\boldsymbol\{([^}]+)\}', r'\1'),
    # \mathbf{x} → x
    (r'\\mathbf\{([^}]+)\}', r'\1'),
    # \left and \right → remove (sizing)
    (r'\\left', ''),
    (r'\\right', ''),
    # \, \; \! \quad → remove spacing
    (r'\\[,;!]', ''),
    (r'\\quad', ''),
    # Double backslash newline in align → space
    (r'\\\\', ' '),
]


def preprocess_latex(tex: str) -> str:
    """Clean ML-specific LaTeX notation so it can be parsed by latex2sympy2."""
    result = tex.strip()
    for pattern, replacement in _PREPROCESS_RULES:
        result = re.sub(pattern, replacement, result)
    return result.strip()


def extract_symbols(expr: sympy.Expr) -> List[sympy.Symbol]:
    """Extract all free symbols from a SymPy expression, sorted by name."""
    return sorted(expr.free_symbols, key=lambda s: str(s))


def classify_symbols(expr: sympy.Expr) -> dict:
    """
    Classify symbols into likely inputs vs parameters based on naming conventions.
    Returns {'inputs': [...], 'parameters': [...], 'indices': [...]}.
    """
    inputs = []
    parameters = []
    indices = []

    # Common index names
    index_names = {'i', 'j', 'k', 'l', 'm', 'n', 't'}
    # Common parameter names
    param_names = {'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'lambda',
                   'mu', 'sigma', 'tau', 'eta', 'theta', 'phi', 'psi',
                   'omega', 'rho', 'nu', 'kappa', 'lr', 'eps'}

    for sym in extract_symbols(expr):
        name = str(sym).lower()
        if name in index_names or len(name) == 1 and name in 'ijklmn':
            indices.append(sym)
        elif name in param_names or name.startswith(('w_', 'b_')):
            parameters.append(sym)
        else:
            inputs.append(sym)

    return {
        'inputs': inputs,
        'parameters': parameters,
        'indices': indices,
    }


def parse_latex(tex: str, preprocess: bool = True) -> Tuple[Optional[sympy.Expr], dict]:
    """
    Parse a LaTeX math string into a SymPy expression.

    Args:
        tex: LaTeX math string (e.g. r"\\frac{1}{N}\\sum_{i=1}^{N}(y_i - \\hat{y}_i)^2")
        preprocess: Whether to apply ML-specific preprocessing

    Returns:
        Tuple of (sympy_expression, metadata_dict)
        metadata_dict contains: original_latex, cleaned_latex, symbols, classification, errors
    """
    meta = {
        'original_latex': tex,
        'cleaned_latex': tex,
        'symbols': [],
        'classification': {},
        'errors': [],
        'parse_method': 'none',
    }

    if not HAS_LATEX2SYMPY:
        meta['errors'].append(
            'latex2sympy2_extended not installed. '
            'Install with: pip install "latex2sympy2_extended[antlr4_13_2]"'
        )
        # Fallback: try sympy's built-in parser (limited)
        return _fallback_parse(tex, meta)

    # Pre-process
    cleaned = preprocess_latex(tex) if preprocess else tex
    meta['cleaned_latex'] = cleaned

    # Parse with latex2sympy2
    try:
        result = _latex2sympy(cleaned)
        if result is None:
            meta['errors'].append(f'latex2sympy2 returned None for: {cleaned}')
            return _fallback_parse(tex, meta)

        # If it returns a list/tuple, take the first meaningful one
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None

        if result is not None and isinstance(result, sympy.Basic):
            meta['parse_method'] = 'latex2sympy2'
            meta['symbols'] = [str(s) for s in extract_symbols(result)]
            meta['classification'] = {
                k: [str(s) for s in v]
                for k, v in classify_symbols(result).items()
            }
            return result, meta
        else:
            meta['errors'].append(f'Unexpected result type: {type(result)}')
            return _fallback_parse(tex, meta)

    except Exception as e:
        meta['errors'].append(f'latex2sympy2 parse error: {str(e)}')
        return _fallback_parse(tex, meta)


def _fallback_parse(tex: str, meta: dict) -> Tuple[Optional[sympy.Expr], dict]:
    """Fallback: try SymPy's sympify with basic LaTeX-to-Python translation."""
    try:
        # Very basic LaTeX → Python translation
        py_str = tex
        py_str = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'((\1)/(\2))', py_str)
        py_str = re.sub(r'\\sqrt\{([^}]+)\}', r'sqrt(\1)', py_str)
        py_str = py_str.replace('^', '**')
        py_str = py_str.replace(r'\cdot', '*')
        py_str = re.sub(r'\\(sin|cos|tan|exp|log|ln)\b', r'\1', py_str)

        result = sympy.sympify(py_str)
        meta['parse_method'] = 'sympy_fallback'
        meta['symbols'] = [str(s) for s in extract_symbols(result)]
        meta['classification'] = {
            k: [str(s) for s in v]
            for k, v in classify_symbols(result).items()
        }
        return result, meta
    except Exception as e2:
        meta['errors'].append(f'Fallback parse also failed: {str(e2)}')
        meta['parse_method'] = 'failed'
        return None, meta


def parse_latex_batch(equations: List[str]) -> List[Tuple[Optional[sympy.Expr], dict]]:
    """Parse multiple LaTeX equations."""
    return [parse_latex(eq) for eq in equations]
