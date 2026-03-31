# 📑 Paper Parser

Parse PDF papers into structured data (Markdown, JSON, images) using [MinerU](https://mineru.net)'s precision extraction API.

## 🔑 Prerequisites

You need a **MinerU API Token**:
1. Go to [mineru.net/apiManage](https://mineru.net/apiManage)
2. Register/Login and get your API token
3. Set it as an environment variable:

```bash
# Windows
set MINERU_TOKEN=your_token_here

# Linux/Mac
export MINERU_TOKEN=your_token_here
```

## 🚀 Quick Start

```bash
# Parse a PDF with VLM model (highest precision)
python parse_paper.py paper.pdf

# Custom output directory
python parse_paper.py paper.pdf -o parsed_output/

# Use pipeline model (faster, less precise)
python parse_paper.py paper.pdf --model pipeline

# Pass token directly
python parse_paper.py paper.pdf --token your_token_here

# Set OCR language (for scanned papers)
python parse_paper.py paper.pdf --language ch
```

## 🏗️ How It Works

```
Local PDF
    │
    ▼
┌─────────────────────────┐
│ 1. Request presigned URL │  POST /api/v4/file-urls/batch
│    from MinerU API       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ 2. PUT upload PDF to     │  Upload to MinerU OSS
│    presigned URL         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ 3. Auto-parse triggered  │  MinerU processes with
│    (VLM/pipeline model)  │  selected model
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ 4. Poll for completion   │  GET /api/v4/extract-results/batch/{id}
│    (progress updates)    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ 5. Download result zip   │  Contains: markdown, images,
│    & extract locally     │  tables, formulas, metadata
└─────────────────────────┘
```

## 📁 Output Structure

MinerU produces a zip containing:
```
<paper>_parsed/
├── auto/                    ← MinerU structured output
│   ├── <paper>.md           ← Full markdown
│   ├── images/              ← Extracted figures
│   ├── tables/              ← Table data
│   └── ...
└── parse_report.json        ← Our parsing log
```

## 🔧 CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir`, `-o` | `<pdf_name>_parsed/` | Output directory |
| `--model`, `-m` | `vlm` | MinerU model: `vlm` (precise) or `pipeline` (fast) |
| `--token`, `-t` | env `MINERU_TOKEN` | API token |
| `--timeout` | 600 | Polling timeout (seconds) |
| `--language`, `-l` | `en` | OCR language hint |

## 📊 Models

| Model | Speed | Precision | Best For |
|-------|-------|-----------|----------|
| `vlm` | Slower | ⭐⭐⭐ Highest | Complex papers with formulas, tables |
| `pipeline` | Faster | ⭐⭐ Good | Simple text-heavy documents |

## ⚠️ Limits

- Max file size: 200 MB
- Max pages: 600
- Daily quota: 2000 pages at highest priority

## 📄 License

MIT — see [LICENSE](../LICENSE)
