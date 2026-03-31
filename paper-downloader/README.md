# 📥 Paper Downloader

Download paper PDFs and clone source code repositories. Works as the second step in the research pipeline, reading the `paper_info.json` output from [paper-finder](../paper-finder/).

## 🚀 Quick Start

```bash
# Step 1: Find a paper (requires paper-finder)
cd ../paper-finder
python search_paper.py "Denoising Diffusion Probabilistic Models" -o ../paper-downloader/paper_info.json

# Step 2: Download everything
cd ../paper-downloader
pip install -r requirements.txt
python download_paper.py paper_info.json
```

## 📖 Usage

```bash
# Basic: download PDF + clone code
python download_paper.py paper_info.json

# With Sci-Hub fallback enabled
python download_paper.py paper_info.json --allow-scihub

# Custom output directory
python download_paper.py paper_info.json -o my_project/

# Skip code clone (PDF only)
python download_paper.py paper_info.json --skip-code

# Full git history (not shallow clone)
python download_paper.py paper_info.json --clone-depth 0
```

## 📄 PDF Download Priority

| Priority | Source | Description |
|----------|--------|-------------|
| 1️⃣ | **arXiv** | Direct download from `pdf_url` in paper_info.json |
| 2️⃣ | **Unpaywall** | Open Access discovery via DOI |
| 3️⃣ | **Sci-Hub** | Fallback (requires `--allow-scihub` flag) |

> ⚠️ Sci-Hub is disabled by default. Use `--allow-scihub` to enable it.

## 💻 Code Clone

- Clones the **highest-confidence** repository from paper_info.json
- Uses **shallow clone** (`--depth 1`) by default to save disk space
- Auto-detects dependency files (`requirements.txt`, `setup.py`, etc.)

## 📁 Output Structure

```
workspace/<paper-slug>/
├── paper/
│   ├── paper.pdf              ← Downloaded PDF
│   └── paper_info.json        ← Metadata from paper-finder
├── code/
│   └── <repo-name>/           ← Cloned source code
│       ├── README.md
│       ├── requirements.txt
│       └── ...
└── download_report.json       ← Download log
```

## 🔧 CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir`, `-o` | `workspace/<slug>` | Output directory |
| `--allow-scihub` | off | Enable Sci-Hub as PDF fallback |
| `--clone-depth` | 1 | Git clone depth (0 = full) |
| `--skip-code` | off | Skip cloning code repos |
| `--skip-pdf` | off | Skip downloading PDF |

## 📋 Requirements

- Python 3.10+
- `requests` library
- `git` (for cloning repositories)

## 📄 License

MIT — see [LICENSE](../LICENSE)
