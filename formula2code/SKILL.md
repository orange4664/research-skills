---
name: formula2code
description: Convert LaTeX math formulas from papers into executable PyTorch/NumPy code.
---

# Formula2Code Skill

## Purpose
Convert mathematical equations from research papers into runnable code. This skill bridges the gap between **paper reading** (LaTeX formulas) and **implementation** (PyTorch/NumPy).

## When to Use
- Paper has mathematical formulas that need to be implemented
- User asks to "convert this equation to code" or "implement this loss function"
- During `code-writer` workflow: auto-convert extracted formulas into `loss.py` / `model.py`
- Verifying that a manual implementation matches the paper's formula

## Architecture (3-Layer Pipeline)

```
LaTeX input
    │
    ▼
Layer 1: ML Pattern Matcher ─── Known formula? ──→ Direct PyTorch API mapping
    │ (no match)                                    (softmax, cross_entropy, etc.)
    ▼
Layer 2: latex2sympy2 ────────── Parse to SymPy symbolic expression
    │
    ▼
Layer 3: Code Generator ─────── sympytorch (nn.Module) / lambdify / pycode
    │
    ▼
Layer 4: Validator ──────────── Cross-check SymPy vs NumPy vs PyTorch
```

## Quick Start

### Single Formula
```bash
python formula2code/convert.py "\frac{1}{N}\sum_{i=1}^{N}(y_i - \hat{y}_i)^2" --to pytorch -v
```

### From Paper JSON (paper-parser output)
```bash
python formula2code/convert.py --from-paper workspace/<paper>/paper_content.json --to pytorch -o formulas.json
```

### List Known Patterns
```bash
python formula2code/convert.py --list-patterns
```

## Built-in ML Pattern Library (16 patterns)

| Category | Patterns |
|----------|----------|
| **Loss** | MSE, Cross Entropy, Binary CE, KL Divergence, L1, Huber |
| **Activation** | Softmax, Sigmoid, ReLU, GELU, Tanh |
| **Attention** | Scaled Dot-Product Attention |
| **Normalization** | Layer Norm, Batch Norm |
| **Distribution** | Gaussian/Normal |

When a LaTeX formula matches a known pattern, the skill returns the exact PyTorch API call instead of generating code from scratch. This is more reliable for standard operations.

## Output Format

For each formula, the converter outputs:

```json
{
  "input_latex": "\\frac{1}{N}\\sum...",
  "method": "pattern_match | sympy_pipeline | failed",
  "outputs": {
    "pytorch_functional": "F.mse_loss(predictions, targets)",
    "pytorch_class": "nn.MSELoss()",
    "pytorch_code": "import torch\ndef formula(N, y, y_hat): ...",
    "numpy_code": "import numpy as np\ndef formula(N, y, y_hat): ...",
    "python_code": "import math\ndef formula(N, y, y_hat): ..."
  },
  "validation": {"passed": true, "summary": "5/5 tests passed"}
}
```

## Integration with Other Skills

### With paper-parser
```
paper-parser outputs JSON with LaTeX formulas
    → formula2code reads them and generates code
```

### With code-writer
```
code-writer extracts equations from paper
    → calls formula2code to generate loss.py / model.py components
    → inserts generated code into project scaffolding
```

## Examples

See `formula2code/examples/` for runnable demos:

| Example | What it Shows |
|---------|---------------|
| `01_basic_usage.py` | 3-layer pipeline: pattern match → SymPy → code generation |
| `02_official_library_usage.py` | Direct usage of latex2sympy2, sympytorch, lambdify |
| `03_trainable_formula.py` | Learn formula coefficients via gradient descent |

### Quick Example: Pattern Match
```python
from converters.ml_patterns import match_ml_pattern

result = match_ml_pattern(r"\text{softmax}(z)")
# → {'name': 'softmax', 'pytorch_functional': 'F.softmax(x, dim=-1)', ...}
```

### Quick Example: SymPy Pipeline
```python
from converters.latex_parser import parse_latex
from converters.to_python import sympy_to_python_code

expr, meta = parse_latex(r"x^2 + 2x + 1")
code = sympy_to_python_code(expr)
# → "def formula(x):\n    return x**2 + 2*x + 1"
```

### Quick Example: sympytorch (from official README)
```python
import sympy, torch, sympytorch

x = sympy.symbols('x_name')
cosx = 1.0 * sympy.cos(x)
sinx = 2.0 * sympy.sin(x)
mod = sympytorch.SymPyModule(expressions=[cosx, sinx])

x_ = torch.rand(3)
out = mod(x_name=x_)  # shape (3, 2)
# Floats (1.0, 2.0) become trainable nn.Parameters!
```

### Quick Example: latex2sympy2 (from official README)
```python
from latex2sympy2_extended import latex2sympy

latex2sympy(r"\frac{d}{dx}(x^{2}+x)")   # → Derivative(x**2 + x, x)
latex2sympy(r"\sum_{i = 1}^{n} i")        # → Sum(i, (i, 1, n))
latex2sympy(r"\int_{a}^{b} \frac{dt}{t}") # → Integral(1/t, (t, a, b))
```

## Dependencies
```bash
pip install -r formula2code/requirements.txt
# Core: sympy
# LaTeX parsing: latex2sympy2_extended[antlr4_13_2]
# PyTorch modules: sympytorch
```

## Troubleshooting & Where to Get Help

When encountering issues, the agent should **fetch** the relevant docs:

### LaTeX Parsing Errors
**Problem**: `latex2sympy` fails to parse a formula.
**Solution**:
1. Check supported syntax at the official repo
2. Preprocess the LaTeX (our `latex_parser.py` handles common ML notation like `\text{}`, `\hat{}`)
3. For very complex notation, manually simplify to standard LaTeX

```
# Fetch latest docs/issues:
fetch_url("https://github.com/huggingface/latex2sympy2_extended")
fetch_url("https://github.com/huggingface/latex2sympy2_extended/issues")
```

### sympytorch Unsupported Operation
**Problem**: `sympytorch` throws `NotImplementedError` for a SymPy function.
**Solution**: Use `extra_funcs` to provide a custom PyTorch implementation.

```python
import sympy, sympytorch

# Check supported operations:
# https://github.com/patrick-kidger/sympytorch/blob/master/sympytorch/sympy_module.py#L12

mod = sympytorch.SymPyModule(
    expressions=[expr],
    extra_funcs={
        sympy.Function('my_custom_op'): lambda x: x.clamp(min=0),
    }
)
```

```
# Fetch supported ops list:
fetch_url("https://github.com/patrick-kidger/sympytorch/blob/master/sympytorch/sympy_module.py")
```

### lambdify Module Selection
**Problem**: Need to generate code for a specific backend (torch/numpy/scipy).
**Solution**: Use the `modules` parameter.

```python
import sympy
f = sympy.lambdify([x], expr, modules='torch')    # → torch functions
f = sympy.lambdify([x], expr, modules='numpy')    # → numpy functions
f = sympy.lambdify([x], expr, modules='scipy')    # → scipy special
```

```
# Fetch lambdify docs:
fetch_url("https://docs.sympy.org/latest/modules/utilities/lambdify.html")
```

## 📚 Reference URLs (for agent self-help)

When stuck on any issue, the agent should fetch these URLs:

| Topic | URL |
|-------|-----|
| **latex2sympy2 README + examples** | `https://github.com/huggingface/latex2sympy2_extended` |
| **latex2sympy2 issues** | `https://github.com/huggingface/latex2sympy2_extended/issues` |
| **latex2sympy2 grammar (PS.g4)** | `https://github.com/huggingface/latex2sympy2_extended/blob/master/src/latex2sympy2_extended/PS.g4` |
| **sympytorch README** | `https://github.com/patrick-kidger/sympytorch` |
| **sympytorch supported ops** | `https://github.com/patrick-kidger/sympytorch/blob/master/sympytorch/sympy_module.py` |
| **sympytorch issues** | `https://github.com/patrick-kidger/sympytorch/issues` |
| **SymPy lambdify docs** | `https://docs.sympy.org/latest/modules/utilities/lambdify.html` |
| **SymPy pycode docs** | `https://docs.sympy.org/latest/modules/printing.html` |
| **SymPy basic operations** | `https://docs.sympy.org/latest/tutorials/intro-tutorial/basic_operations.html` |

## Limitations
- `latex2sympy2` cannot parse all LaTeX notations (very complex nested expressions may fail)
- `sympytorch` only supports a subset of SymPy operations (extend via `extra_funcs`)
- Pattern matching is regex-based — unusual formatting of standard formulas may not match
- For complex multi-line algorithm definitions, use `code-writer` instead

