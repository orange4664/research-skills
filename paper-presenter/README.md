# 🎯 Paper Presenter

Prepare structured presentation materials from parsed papers. Acts as the bridge between
[paper-parser](../paper-parser/) (MinerU output) and [beamer-skill](https://github.com/Noi1r/beamer-skill).

## 🚀 Quick Start

```bash
# Standard paper overview
python prepare_presentation.py parsed_output/ -o materials.md

# Reproduction report with code analysis
python prepare_presentation.py parsed_output/ \
    --code-dir code/repo/ \
    --style reproduction-report \
    -o materials.md
```

Then tell your AI agent:
```
Create a beamer presentation based on the materials in materials.md
```

## 🏗️ Architecture

```
  paper-parser output          paper-downloader output
  (markdown, images, JSON)     (cloned source code)
         │                              │
         ▼                              ▼
  ┌──────────────────────────────────────────┐
  │         paper-presenter                  │
  │                                          │
  │  • Analyze paper structure               │
  │  • Catalog figures                       │
  │  • Extract key formulas                  │
  │  • Analyze source code                   │
  │  • Map paper ↔ code alignment            │
  │  • Generate slide structure suggestion   │
  └─────────────────┬────────────────────────┘
                    │
                    ▼
         presentation_materials.md
                    │
                    ▼
  ┌──────────────────────────────────────────┐
  │  beamer-skill  `create [topic]`          │
  │  Phase 0: Read materials                 │
  │  Phase 1-5: Build presentation           │
  └──────────────────────────────────────────┘
```

## 🎨 Presentation Styles

| Style | Slides | Best For |
|-------|--------|----------|
| `overview` | 15-20 | Paper reading groups, seminars |
| `deep-dive` | 30-40 | Technical talks, thesis defense |
| `reproduction-report` | 20-30 | **Reproduction analysis with code comparison** |

### `reproduction-report` (Key Feature)

When combined with `--code-dir`, generates:

- **Paper ↔ Code Alignment Table** — which code file implements which paper section
- **Comparison Slide Suggestions** — paper formula on left, code snippet on right
- **Delta Analysis Structure** — original vs reproduced results
- **Implementation Detail Highlights** — undocumented tricks found in code

## 🔧 CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--code-dir`, `-c` | None | Source code repo path |
| `--output`, `-o` | `presentation_materials.md` | Output path |
| `--style`, `-s` | `overview` | Presentation style |
| `--language`, `-l` | `en` | Output language (en/zh) |
| `--paper-info`, `-p` | auto-detect | Path to paper_info.json |

## 📄 License

MIT — see [LICENSE](../LICENSE)
