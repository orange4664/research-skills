---
name: result-analyzer
description: Compare reproduced results against paper-reported values. Generate Markdown/JSON/Beamer reports.
---

# Result-Analyzer Skill

## Purpose
The **final piece** of the reproduction pipeline. After running experiments, this skill compares your results against the paper's reported metrics, figures, and training curves — then generates a structured report.

## When to Use
- After `code-reproducer` has finished training on the remote GPU
- User says "compare my results" or "how close are we to the paper?"
- When writing a reproduction report or paper
- To decide if reproduction was successful

## Architecture

```
Inputs                           Comparators                     Outputs
───────────────────             ──────────────                  ────────────────
paper-parser JSON ──┐
                    ├──→ table_extractor ───┐
paper metrics     ──┘                      │
                                           ├──→ metric_comparator ──→ Markdown Report
repro metrics   ────────────────────────────┘                    ──→ JSON Report
                                                                 ──→ Beamer Data
repro train.csv ────→ curve_comparator ──→ comparison plots      ──→ latex-paper-skills
                                                                 ──→ beamer-skill PPT
repro images    ────→ image_comparator ──→ SSIM/PSNR/FID
paper figures   ────┘                  ──→ side-by-side figures
```

## Quick Start

### Simple Metric Comparison
```bash
python result-analyzer/analyze.py \
    --paper-metrics '{"accuracy": 95.3, "FID": 3.17}' \
    --repro-metrics '{"accuracy": 94.8, "FID": 3.45}' \
    --title "DDPM Reproduction" \
    -o report/
```

### Full Pipeline (paper JSON + training log + images)
```bash
python result-analyzer/analyze.py \
    --paper-json workspace/<paper>/paper_content.json \
    --repro-log workspace/<paper>/train_log.csv \
    --repro-images workspace/<paper>/generated/ \
    --paper-figures workspace/<paper>/figures/ \
    --fid \
    --beamer \
    -o workspace/<paper>/report/
```

### From Paper-Parser JSON Only
```bash
python result-analyzer/analyze.py \
    --paper-json paper_content.json \
    --repro-metrics '{"accuracy": 94.8}' \
    --method-name "Ours" \
    -o report/
```

## Comparators

### 1. Metric Comparator (Core)
Compares reproduced values against paper values with tolerance-based judgment.

**Built-in Knowledge Base**: 50+ metrics with direction info:
- `higher_better`: accuracy, BLEU, PSNR, SSIM, IS, mAP, AUC, F1...
- `lower_better`: FID, loss, perplexity, WER, MAE, RMSE, LPIPS...

**Judgment Logic**:
| Status | Condition |
|--------|-----------|
| ✅ PASS | Within tolerance (default: ±1 abs, ±5% rel) |
| 🟢 PASS | Better than paper! |
| ⚠️ WARN | Within 2× tolerance |
| ❌ FAIL | Outside tolerance |

### 2. Curve Comparator
- Loads CSV/JSON training logs
- Compares final values against paper
- Pearson correlation between curves
- Convergence speed analysis
- Generates matplotlib comparison plots

### 3. Image Comparator
- **SSIM** (Structural Similarity) — via scikit-image
- **PSNR** (Peak Signal-to-Noise Ratio)
- **FID** (Fréchet Inception Distance) — **optional**, requires `pytorch-fid`
- Side-by-side comparison figures

### 4. Table Extractor
- Reads paper-parser JSON output → finds result tables
- Auto-detects "Ours" / "Proposed" / last row
- Handles `±`, bold markers, `%` signs
- Free-text metric extraction (e.g., "We achieve 95.3% accuracy")

## Output Formats

### Markdown Report (`reproduction_report.md`)
```markdown
# Reproduction Report
## 🟢 Overall: PASS
| Status | Metric | Paper | Reproduced | Diff | Note |
|--------|--------|-------|-----------|------|------|
| ✅ PASS | Accuracy | 95.3 | 94.8 | -0.5 ↓ | Within tolerance |
| ⚠️ WARN | FID | 3.17 | 3.45 | +0.28 ↑ | Close but slightly off |
```

### JSON Report (`reproduction_report.json`)
Structured data for downstream consumption:
- `latex-paper-skills` → `results-backfill` skill
- `beamer-skill` → reproduction PPT

### Beamer Data (`beamer_report_data.json`)
Slide-by-slide data for generating a Beamer PPT:
1. Title slide (paper name + overall status)
2. Metric comparison table
3. Training curves figure
4. Sample comparison figure
5. Conclusion slide

## Integration with Other Skills

### → beamer-skill (Generate PPT)
```bash
# 1. Run result-analyzer with --beamer flag
python result-analyzer/analyze.py ... --beamer -o report/

# 2. Use beamer-skill to create PPT from the JSON
beamer-skill: create presentation from report/beamer_report_data.json
```

### → latex-paper-skills (Write LaTeX Paper)
```bash
# 1. Run result-analyzer
python result-analyzer/analyze.py ... -o report/

# 2. Copy JSON to paper/results/ for results-backfill
cp report/reproduction_report.json paper/results/

# 3. Use latex-paper-skills results-backfill
results-backfill: update paper with real results from paper/results/
```

### ← paper-parser (Input)
```
paper-parser outputs paper_content.json with tables
    → result-analyzer extracts paper metrics from tables
    → compares against reproduced values
```

### ← code-reproducer (Input)
```
code-reproducer outputs train_log.csv + generated images
    → result-analyzer loads CSV for curve comparison
    → compares images via SSIM/PSNR
```

## Dependencies
```bash
pip install -r result-analyzer/requirements.txt
# Core: numpy, matplotlib, scikit-image, pandas
# Optional: pytorch-fid (for FID score)
```

## 📚 Reference URLs (for agent self-help)

| Topic | URL |
|-------|-----|
| **scikit-image SSIM docs** | `https://scikit-image.org/docs/stable/api/skimage.metrics.html` |
| **scikit-image PSNR docs** | `https://scikit-image.org/docs/stable/api/skimage.metrics.html` |
| **pytorch-fid** | `https://github.com/mseitzer/pytorch-fid` |
| **matplotlib savefig** | `https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html` |
| **pandas read_csv** | `https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html` |
| **latex-paper-skills** | `https://github.com/yunshenwuchuxun/latex-paper-skills` |
| **results-backfill skill** | `https://github.com/yunshenwuchuxun/latex-paper-skills/tree/main/.codex/skills/results-backfill` |
| **ML metrics overview** | `https://paperswithcode.com/task/image-generation` |

## Limitations
- SSIM is sensitive to image alignment — ensure consistent cropping
- FID requires ≥2048 images per directory for reliable scores
- Table extraction depends on paper-parser JSON quality
- Free-text metric extraction uses regex patterns — may miss complex phrasing
