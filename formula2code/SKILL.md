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

## Dependencies
```bash
pip install -r formula2code/requirements.txt
# Core: sympy
# LaTeX parsing: latex2sympy2_extended[antlr4_13_2]
# PyTorch modules: sympytorch
```

## Limitations
- `latex2sympy2` cannot parse all LaTeX notations (very complex nested expressions may fail)
- `sympytorch` only supports a subset of SymPy operations (extend via `extra_funcs`)
- Pattern matching is regex-based — unusual formatting of standard formulas may not match
- For complex multi-line algorithm definitions, use `code-writer` instead
