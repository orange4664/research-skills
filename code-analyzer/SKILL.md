---
name: code-analyzer
description: Deep analysis of ML source code repositories — AST call graphs, training loop dissection, reproducibility scoring.
---

# Code Analyzer Skill

## Purpose

Perform comprehensive analysis of a cloned ML research repository to understand:
- What framework it uses (PyTorch, TensorFlow, JAX, HuggingFace)
- How its code is structured (classes, functions, call graphs)
- How training works (optimizer, loss, scheduler, loop structure)
- What configuration system it uses (argparse, Hydra, YAML, etc.)
- How reproducible it is (0-100 score based on ML Code Completeness Checklist)

This skill produces a structured JSON report consumed by other skills:
- **code-reproducer**: Uses the reproduction plan to run experiments
- **paper-presenter**: Uses AST analysis for code-theory alignment

## When to Use

- After paper-downloader has cloned source code
- User asks to "analyze", "understand", or "review" source code
- Before running code-reproducer (to generate the reproduction plan)
- When evaluating whether a codebase is worth trying to reproduce

## Quick Start

```bash
# Install optional dependencies (for flowchart generation)
pip install -r code-analyzer/requirements.txt

# Run full analysis
python code-analyzer/analyze.py workspace/<paper>/code/<repo>/ -o workspace/<paper>/code_analysis.json

# With optional code2flow flowchart
python code-analyzer/analyze.py <code_dir> -o analysis.json --flowchart
```

## What It Analyzes

### 1. Framework Detection
Scans imports and dependency files to identify:
- PyTorch, TensorFlow, JAX, HuggingFace, Diffusers, scikit-learn
- Gives confidence scores for each framework

### 2. AST Deep Analysis (Python `ast` module, PyCG-inspired)
- **Function call graph**: Who calls whom
- **Class hierarchy**: All classes, especially `nn.Module` subclasses
- **Model layer extraction**: `self.conv1 = nn.Conv2d(...)` from `__init__`
- **Key functions**: trains, forwards, losses, evaluates, samples, generates
- **Import dependency graph**: Module → imported modules

### 3. Training Loop Dissection
- Locates `for epoch in range(...)` training loops via AST
- Identifies optimizer type (Adam, SGD, AdamW, etc.)
- Identifies loss function type (CrossEntropy, MSE, custom, etc.)
- Detects LR scheduler, logging framework (WandB, TensorBoard, etc.)
- Extracts hyperparameters (lr, batch_size, epochs, etc.)
- Detects checkpoint saving, distributed training, mixed precision

### 4. Configuration System Detection
- Detects: argparse, Hydra, OmegaConf, click, fire, sacred, absl, yacs
- Extracts all argparse arguments with name, type, default, help
- Parses YAML/TOML config files
- Consolidates key hyperparameters

### 5. Reproducibility Scoring (ML Code Completeness Checklist)
Based on NeurIPS/PwC standards:

| Check | Points |
|-------|--------|
| Dependency spec (requirements.txt) | 15 |
| Training code | 15 |
| Evaluation code | 10 |
| Pre-trained models | 10 |
| Config files | 10 |
| README training commands | 10 |
| Results table | 10 |
| Dockerfile | 5 |
| LICENSE | 5 |
| .gitignore | 5 |
| Tests | 5 |

**Total: 100 points → Grade A/B/C/D/F**

### 6. Reproduction Plan Generation
Automatically generates a step-by-step reproduction plan with shell commands.

## Output Format

The JSON report contains:
```json
{
  "framework": {"primary": "pytorch", "all": {...}},
  "structure": {"total_files": 42, "total_py_files": 28},
  "ast_analysis": {
    "model_classes": [...],
    "key_functions": {"train": [...], "forward": [...], "loss": [...]},
    "call_graph": {"module.func": ["callee1", "callee2"]},
    "stats": {"total_functions": 150, "model_classes": 3}
  },
  "training": {
    "training_loops": [...],
    "optimizers": ["AdamW"],
    "loss_functions": ["CrossEntropyLoss"],
    "hyperparameters": {"lr": "0.001", "batch_size": "32"}
  },
  "configs": {
    "config_systems": ["argparse"],
    "argparse_args": [{"name": "--lr", "default": "0.001"}]
  },
  "reproducibility": {
    "total_score": 75,
    "grade": "B",
    "recommendations": [...]
  },
  "reproduction_plan": [
    {"step": 1, "name": "Environment Setup", "commands": [...]},
    {"step": 2, "name": "Training", "commands": [...]}
  ]
}
```

## Dependencies

- **Core**: Python 3.10+ (stdlib only — `ast`, `re`, `json`, `pathlib`)
- **Optional**: `code2flow` for flowchart generation (`pip install code2flow`)

## Integration with Other Skills

- **Input**: Cloned source code directory (from paper-downloader)
- **Output**: `code_analysis.json` used by:
  - `code-reproducer` → reads reproduction plan, training commands
  - `paper-presenter` → reads AST analysis for code-theory alignment
  - `result-analyzer` → reads expected metrics for comparison
