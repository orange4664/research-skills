---
name: code-writer
description: Generate implementation code scaffolding from paper descriptions when no source code exists.
---

# Code-Writer Skill

## Purpose
When a paper has **no source code**, this skill generates a complete project scaffolding with model, training, data loading, and evaluation code — ready to fill in and run.

## When to Use
- Paper has no associated GitHub repository
- User says "implement this paper" or "write code for this model"
- After `paper-parser` has extracted the paper content but `paper-finder` found no code
- When reproducing a paper from scratch

## Prerequisites
- Paper content (from `paper-parser` JSON/MD, or user description)
- `formula2code` skill (for converting paper equations to code)
- `code-analyzer` skill (for analyzing reference implementations)
- `paper-finder` skill (for searching reference code)

## Architecture

```
Paper Content (JSON/MD/description)
    │
    ▼
Phase 0: Reference Code Discovery ← KEY INNOVATION
    │  "Papers don't exist in a vacuum — find code for what they build on"
    │  → paper-finder: search for base methods' implementations
    │  → code-analyzer: analyze found repos for reusable components
    ▼
Phase 1: Paper Info Extraction
    │  → extractors/paper_info.py: title, abstract, sections
    │  → extractors/architecture.py: model components, layer types
    │  → extractors/equations.py: LaTeX formulas
    │  → extractors/experiment.py: hyperparameters, datasets, metrics
    ▼
Phase 2: Code Generation (with reference code guidance)
    │  → generate.py: fill templates with extracted info
    │  → formula2code: convert equations to loss/model code
    ▼
Phase 3: Output
    project/
    ├── configs/default.yaml        # Hyperparameters from paper
    ├── src/
    │   ├── model.py                # Architecture skeleton with TODOs
    │   ├── train.py                # Training loop (standard PyTorch)
    │   ├── data.py                 # Data loading skeleton
    │   └── evaluate.py             # (generated when metrics detected)
    ├── references/
    │   └── search_plan.md          # What code to search for
    ├── implementation_checklist.md  # Step-by-step guide
    ├── requirements.txt
    └── README.md
```

## Usage

### Quick Start
```bash
# From paper-parser JSON
python code-writer/generate.py --paper workspace/<paper>/paper_content.json -o workspace/<paper>/implementation/

# From markdown
python code-writer/generate.py --markdown workspace/<paper>/paper.md -o workspace/<paper>/implementation/

# From text description
python code-writer/generate.py --describe "A transformer-based model for image classification with self-attention" -o project/
```

## Agent Workflow — How to Implement a Paper from Scratch

> This is the most important section. Follow this methodology step by step.

### Step 0: Reference Code Discovery (BEFORE writing any code)

The paper you're implementing is NOT invented from nothing. It builds on existing methods. **Find their code first.**

1. **Read the paper** (from paper-parser output) and identify:
   - What base methods/architectures it uses (e.g., "extends ResNet", "uses Transformer encoder")
   - Which cited papers are most important (usually the "baseline" they compare against)

2. **Run `generate.py`** to get the scaffold AND the `references/search_plan.md`

3. **Execute the search plan** using `paper-finder`:
   ```
   paper-finder: search "ResNet PyTorch implementation" on GitHub
   paper-finder: search base paper on Papers With Code
   ```

4. **Clone & analyze** the most relevant reference repo:
   ```
   git clone <reference_repo> workspace/<paper>/references/<name>
   code-analyzer: analyze workspace/<paper>/references/<name>
   ```

5. **Study the reference code** — pay attention to:
   - How they implement the specific layers you need
   - Their training loop structure
   - Data preprocessing pipeline
   - Loss function implementation

### Step 1: Data Pipeline (FIRST!)
```
Why first? Because wrong data = nothing else matters.
```
1. Read the paper's experiment section for dataset details
2. Implement `src/data.py` with actual data loading
3. **Verify**: `print(next(iter(loader)))` should match expected shapes
4. Check normalization: [0,1] or [-1,1]? ImageNet stats?

### Step 2: Model Components (Bottom-Up)
```
Why bottom-up? Build small, test small, then compose.
```
1. Implement each component as a separate `nn.Module`
2. For each component:
   ```python
   # Test with dummy tensor
   block = MyBlock()
   x = torch.randn(2, 64, 32, 32)  # (batch, channels, h, w)
   print(block(x).shape)  # Should match expected output
   ```
3. Use `formula2code` for any mathematical operations:
   ```bash
   python formula2code/convert.py "<latex from paper>" --to pytorch -v
   ```

### Step 3: Assemble Model
1. Connect components in the main model class
2. **Verify**: `model(dummy_input).shape` should match paper's output description
3. Check parameter count against paper (if reported)

### Step 4: Loss Function
1. Use `formula2code` to convert the paper's loss equation
2. If it's a standard loss (CE, MSE, etc.), use PyTorch built-in
3. **Verify**: loss should be a scalar

### Step 5: Training Loop
1. The scaffold already generates a working loop — customize it:
   - Add learning rate scheduler (check paper for warmup/cosine)
   - Add gradient clipping (if mentioned)
   - Add evaluation loop
2. **Critical test**: Overfit on 5 samples
   ```python
   # If loss doesn't approach ~0, you have a bug
   python src/train.py --epochs 1000 --batch-size 5
   ```

### Step 6: Evaluate & Compare
1. Implement evaluation metrics from the paper
2. Compare against paper's reported results (Table 1)

## Common Pitfalls & Debugging Guide

| Problem | Symptom | Fix |
|---------|---------|-----|
| Wrong normalization | Training doesn't converge | Check if paper uses [0,1] or [-1,1] |
| Missing weight init | Poor performance | Check paper appendix for init method |
| Wrong norm layer | NaN losses | BatchNorm vs LayerNorm matters! |
| No LR schedule | Can't match paper results | Add warmup + cosine decay |
| Wrong loss function | Loss doesn't decrease | Verify with formula2code |
| Dimension mismatch | Runtime crash | Test each component with dummy tensors |

## Dependencies
```bash
pip install -r code-writer/requirements.txt
# Requires: jinja2, pyyaml
```
