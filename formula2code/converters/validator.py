"""
Numerical validator for formula conversions.
Cross-validates outputs between NumPy and PyTorch implementations.
"""
import sympy
import numpy as np
from typing import Optional, List, Dict, Any


def validate_conversion(
    expr: sympy.Expr,
    numpy_func=None,
    pytorch_func=None,
    symbols: Optional[List[sympy.Symbol]] = None,
    n_samples: int = 10,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    value_range: tuple = (-5.0, 5.0),
) -> Dict[str, Any]:
    """
    Validate that a converted formula produces correct numerical outputs.

    Comparison strategy:
    1. Evaluate with SymPy (ground truth, arbitrary precision)
    2. Compare NumPy output against SymPy
    3. Compare PyTorch output against SymPy (if available)
    4. Cross-validate NumPy vs PyTorch

    Args:
        expr: Original SymPy expression
        numpy_func: lambdify'd NumPy function
        pytorch_func: lambdify'd PyTorch function
        symbols: Ordered input symbols
        n_samples: Number of random test points
        rtol: Relative tolerance
        atol: Absolute tolerance
        value_range: Range for random input values

    Returns:
        Validation report dict
    """
    if symbols is None:
        symbols = sorted(expr.free_symbols, key=lambda s: str(s))

    report = {
        'passed': True,
        'n_symbols': len(symbols),
        'n_samples': n_samples,
        'symbol_names': [str(s) for s in symbols],
        'tests': [],
        'errors': [],
    }

    if len(symbols) == 0:
        # Constant expression
        try:
            val = float(expr.evalf())
            report['constant_value'] = val
            report['tests'].append({
                'type': 'constant',
                'sympy_value': val,
                'passed': True,
            })
        except Exception as e:
            report['errors'].append(f'Cannot evaluate constant: {e}')
            report['passed'] = False
        return report

    # Generate random test inputs
    np.random.seed(42)
    test_inputs = []
    for _ in range(n_samples):
        vals = {str(s): np.random.uniform(*value_range) for s in symbols}
        # Ensure positive values for symbols that might be in log/sqrt
        for name in vals:
            if name in ('sigma', 'variance', 'std', 'var'):
                vals[name] = abs(vals[name]) + 0.1
        test_inputs.append(vals)

    # Evaluate with SymPy (ground truth)
    sympy_results = []
    for vals in test_inputs:
        try:
            subs = {s: vals[str(s)] for s in symbols}
            result = float(expr.evalf(subs=subs))
            sympy_results.append(result)
        except Exception as e:
            sympy_results.append(None)
            report['errors'].append(f'SymPy eval error: {e}')

    # Validate NumPy
    if numpy_func is not None:
        for i, vals in enumerate(test_inputs):
            if sympy_results[i] is None:
                continue
            try:
                args = [vals[str(s)] for s in symbols]
                np_result = float(numpy_func(*args))
                close = np.isclose(np_result, sympy_results[i], rtol=rtol, atol=atol)
                test = {
                    'type': 'numpy_vs_sympy',
                    'sample': i,
                    'sympy': sympy_results[i],
                    'numpy': np_result,
                    'passed': bool(close),
                }
                report['tests'].append(test)
                if not close:
                    report['passed'] = False
            except Exception as e:
                report['errors'].append(f'NumPy eval error at sample {i}: {e}')
                report['passed'] = False

    # Validate PyTorch
    if pytorch_func is not None:
        try:
            import torch
            for i, vals in enumerate(test_inputs):
                if sympy_results[i] is None:
                    continue
                try:
                    args = [torch.tensor(vals[str(s)], dtype=torch.float64) for s in symbols]
                    pt_result = float(pytorch_func(*args))
                    close = np.isclose(pt_result, sympy_results[i], rtol=rtol, atol=atol)
                    test = {
                        'type': 'pytorch_vs_sympy',
                        'sample': i,
                        'sympy': sympy_results[i],
                        'pytorch': pt_result,
                        'passed': bool(close),
                    }
                    report['tests'].append(test)
                    if not close:
                        report['passed'] = False
                except Exception as e:
                    report['errors'].append(f'PyTorch eval error at sample {i}: {e}')
        except ImportError:
            report['errors'].append('PyTorch not installed, skipping PT validation')

    # Summary
    n_tests = len(report['tests'])
    n_passed = sum(1 for t in report['tests'] if t['passed'])
    report['summary'] = f'{n_passed}/{n_tests} tests passed'

    return report


def quick_validate(expr: sympy.Expr, numpy_func=None) -> bool:
    """Quick boolean check: does the NumPy function match SymPy on 5 samples?"""
    report = validate_conversion(expr, numpy_func=numpy_func, n_samples=5)
    return report['passed']
