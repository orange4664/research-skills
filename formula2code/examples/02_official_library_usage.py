#!/usr/bin/env python3
"""
formula2code Example 2: Official Library Usage
================================================
Shows how to use the underlying libraries directly,
for when you need more control than the formula2code wrapper.

Based on official docs:
  - sympytorch README: https://github.com/patrick-kidger/sympytorch
  - latex2sympy2_extended README: https://github.com/huggingface/latex2sympy2_extended
  - SymPy lambdify docs: https://docs.sympy.org/latest/modules/utilities/lambdify.html
"""

# ═══════════════════════════════════════════════════════════════
# 1. latex2sympy2_extended — LaTeX → SymPy
# Source: https://github.com/huggingface/latex2sympy2_extended
# Install: pip install latex2sympy2_extended[antlr4_13_2]
# ═══════════════════════════════════════════════════════════════

print("=" * 60)
print("  1. latex2sympy2_extended (LaTeX → SymPy)")
print("=" * 60)

try:
    from latex2sympy2_extended import latex2sympy

    # Basic examples from official README
    examples = [
        (r"x^{3}",                              "Power"),
        (r"\frac{d}{dx}(x^{2}+x)",             "Derivative"),
        (r"\sum_{i = 1}^{n} i",                 "Summation"),
        (r"\int_{a}^{b} \frac{dt}{t}",          "Integral"),
        (r"\sqrt{x^2 + y^2}",                   "Square root"),
        (r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}", "Matrix"),
    ]

    for tex, desc in examples:
        try:
            result = latex2sympy(tex)
            print(f"\n  [{desc}]")
            print(f"    LaTeX:  {tex}")
            print(f"    SymPy:  {result}")
        except Exception as e:
            print(f"\n  [{desc}] ❌ Error: {e}")

except ImportError:
    print("\n  ⚠️  latex2sympy2_extended not installed.")
    print("     Install: pip install latex2sympy2_extended[antlr4_13_2]")

# ═══════════════════════════════════════════════════════════════
# 2. sympytorch — SymPy → PyTorch nn.Module
# Source: https://github.com/patrick-kidger/sympytorch
# Install: pip install sympytorch
#
# Official example from README:
#   import sympy, torch, sympytorch
#   x = sympy.symbols('x_name')
#   cosx = 1.0 * sympy.cos(x)
#   sinx = 2.0 * sympy.sin(x)
#   mod = sympytorch.SymPyModule(expressions=[cosx, sinx])
#   x_ = torch.rand(3)
#   out = mod(x_name=x_)  # out has shape (3, 2)
# ═══════════════════════════════════════════════════════════════

print(f"\n\n{'=' * 60}")
print("  2. sympytorch (SymPy → PyTorch Module)")
print("=" * 60)

try:
    import sympy
    import sympytorch

    # Official README example
    x = sympy.symbols('x_name')
    cosx = 1.0 * sympy.cos(x)
    sinx = 2.0 * sympy.sin(x)

    mod = sympytorch.SymPyModule(expressions=[cosx, sinx])

    print(f"\n  Expressions: [1.0*cos(x), 2.0*sin(x)]")
    print(f"  Module: {mod}")
    print(f"  Parameters: {list(mod.parameters())}")

    try:
        import torch
        x_ = torch.rand(3)
        out = mod(x_name=x_)
        print(f"\n  Input:  {x_}")
        print(f"  Output: {out}")
        print(f"  Shape:  {out.shape}  # (3, 2) — one column per expression")
        print(f"  Grad:   {out.requires_grad}  # True — floats become Parameters!")

        # Trainable coefficients!
        print(f"\n  Trainable params: {set(p.item() for p in mod.parameters())}")
        print(f"  (1.0 and 2.0 are learnable via gradient descent)")
    except ImportError:
        print("\n  ⚠️  torch not installed, skipping tensor demo")

    # --- Advanced: extra_funcs for custom operations ---
    print(f"\n  --- Advanced: extra_funcs ---")
    print(f"  sympytorch.SymPyModule(expressions=[expr], extra_funcs={{")
    print(f"      sympy.Function('my_op'): lambda x: x.relu()")
    print(f"  }})")

    # --- Advanced: hide_floats for non-trainable constants ---
    print(f"\n  --- Advanced: hide_floats ---")
    expr = 3.14 * sympy.cos(x) + 2.71
    frozen = sympytorch.hide_floats(expr)
    print(f"  Original:   {expr}  → floats are trainable")
    print(f"  hide_floats: {frozen}  → floats become buffers (frozen)")

except ImportError:
    print("\n  ⚠️  sympytorch not installed.")
    print("     Install: pip install sympytorch")

# ═══════════════════════════════════════════════════════════════
# 3. SymPy lambdify — SymPy → NumPy function
# Source: https://docs.sympy.org/latest/modules/utilities/lambdify.html
# ═══════════════════════════════════════════════════════════════

print(f"\n\n{'=' * 60}")
print("  3. SymPy lambdify (SymPy → NumPy function)")
print("=" * 60)

import sympy
import numpy as np

x, y = sympy.symbols('x y')

# Basic lambdify
expr = sympy.sin(x) + sympy.cos(y)
f = sympy.lambdify([x, y], expr, modules='numpy')

x_vals = np.array([0, np.pi/2, np.pi])
y_vals = np.array([0, 0, 0])
result = f(x_vals, y_vals)

print(f"\n  Expression: sin(x) + cos(y)")
print(f"  x = {x_vals}")
print(f"  y = {y_vals}")
print(f"  f(x, y) = {result}")

# Matrix lambdify
A = sympy.Matrix([[x, y], [y, x]])
f_mat = sympy.lambdify([x, y], A, modules='numpy')
print(f"\n  Matrix expression: [[x, y], [y, x]]")
print(f"  f(1, 2) = {f_mat(1, 2)}")

# Available modules
print(f"\n  Available modules for lambdify:")
print(f"    'numpy'      — np.sin, np.cos, etc.")
print(f"    'math'       — math.sin, math.cos (scalar)")
print(f"    'scipy'      — scipy special functions")
print(f"    'tensorflow' — tf.math.sin, etc.")
print(f"    'torch'      — torch.sin, etc.")

print("\n\nDone! ✨")
