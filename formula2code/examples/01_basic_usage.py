#!/usr/bin/env python3
"""
formula2code Example 1: Basic Usage
====================================
Demonstrates the 3-layer pipeline:
  Layer 1 → ML Pattern Match (known formulas)
  Layer 2 → SymPy symbolic pipeline (unknown formulas)

Official references:
  - latex2sympy2_extended: https://github.com/huggingface/latex2sympy2_extended
  - sympytorch: https://github.com/patrick-kidger/sympytorch
  - SymPy lambdify: https://docs.sympy.org/latest/modules/utilities/lambdify.html
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from converters.ml_patterns import match_ml_pattern
from converters.latex_parser import parse_latex
from converters.to_python import sympy_to_python_code

# ═══════════════════════════════════════════════════════════════
# Example 1: ML Pattern Match (Layer 1)
# Known ML formulas → direct PyTorch API mapping
# ═══════════════════════════════════════════════════════════════

print("=" * 60)
print("  Layer 1: ML Pattern Matching")
print("=" * 60)

formulas = [
    (r"\text{softmax}(z)",             "Softmax"),
    (r"\frac{1}{1+e^{-x}}",           "Sigmoid"),
    (r"\max(0, x)",                    "ReLU"),
    (r"\frac{1}{N}\sum_{i=1}^{N}(y_i - \hat{y}_i)^2", "MSE Loss"),
    (r"-\sum_{i} p_i \log q_i",       "Cross Entropy"),
    (r"\text{Attention}(Q, K, V)",     "Attention"),
    (r"D_{KL}(p||q)",                  "KL Divergence"),
]

for latex, expected_name in formulas:
    result = match_ml_pattern(latex)
    if result:
        print(f"\n  ✅ {expected_name}")
        print(f"     LaTeX:   {latex}")
        print(f"     Pattern: {result['name']}")
        print(f"     PyTorch: {result['pytorch_functional']}")
    else:
        print(f"\n  ❌ {expected_name} — not matched (will fall through to Layer 2)")

# ═══════════════════════════════════════════════════════════════
# Example 2: SymPy Pipeline (Layer 2 → Layer 3)
# Unknown formulas → parse to SymPy → generate code
# ═══════════════════════════════════════════════════════════════

print(f"\n\n{'=' * 60}")
print("  Layer 2+3: SymPy Pipeline")
print("=" * 60)

custom_formulas = [
    r"x^2 + 2x + 1",
    r"\frac{a + b}{c}",
    r"e^{-\frac{x^2}{2\sigma^2}}",
    r"\sqrt{x^2 + y^2}",
]

for latex in custom_formulas:
    expr, meta = parse_latex(latex)
    if expr is not None:
        code = sympy_to_python_code(expr)
        print(f"\n  LaTeX:  {latex}")
        print(f"  SymPy:  {expr}")
        print(f"  Python: {code.split('return ')[-1].strip()}")
    else:
        print(f"\n  ❌ Failed to parse: {latex}")
        print(f"     Errors: {meta.get('errors', [])}")

# ═══════════════════════════════════════════════════════════════
# Example 3: Formulas that DON'T match patterns → full pipeline
# ═══════════════════════════════════════════════════════════════

print(f"\n\n{'=' * 60}")
print("  Full Pipeline: convert_single()")
print("=" * 60)

from convert import convert_single

result = convert_single(r"x^2 + 2x + 1", target="all", validate=True)
print(f"\n  Input:      {result['input_latex']}")
print(f"  Method:     {result['method']}")
print(f"  SymPy:      {result.get('sympy_expr', 'N/A')}")
print(f"  Validation: {result.get('validation', {}).get('summary', 'N/A')}")

for key, val in result.get('outputs', {}).items():
    if val and key.endswith('_code'):
        lines = val.strip().split('\n')
        print(f"\n  --- {key} ---")
        for line in lines[-3:]:  # Show last 3 lines
            print(f"  {line}")

print("\n\nDone! ✨")
