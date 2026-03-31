# 🧪 Research Skills

A collection of modular AI agent skills for automating academic research workflows — from paper discovery to reproduction.

Each skill is a self-contained tool that can be used:
- 🖥️ **Standalone** — as a CLI tool
- 🤖 **As an AI Skill** — integrated into Claude Code or other AI coding agents

## 📦 Available Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [paper-finder](./paper-finder/) | Search for papers & source code across arXiv, Semantic Scholar, HuggingFace, GitHub | ✅ Ready |
| [paper-downloader](./paper-downloader/) | Download paper PDFs and clone source code repos | ✅ Ready |
| [paper-parser](./paper-parser/) | Parse PDF papers into structured JSON (via MinerU) | ✅ Ready |
| [paper-presenter](./paper-presenter/) | Generate Beamer presentations summarizing papers | ✅ Ready |
| code-reproducer | SSH to GPU servers and reproduce training pipelines | 🔜 Coming |
| result-analyzer | Compare reproduced results against original figures | 🔜 Coming |

## 🚀 Quick Start

```bash
git clone https://github.com/orange4664/research-skills.git
cd research-skills

# Use paper-finder
cd paper-finder
pip install -r requirements.txt
python search_paper.py "Attention Is All You Need"
```

## 🏗️ Pipeline Architecture

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│ paper-finder │───▶│ paper-downloader │───▶│ paper-parser │
│ (search)     │    │ (download)       │    │ (PDF → JSON) │
└──────────────┘    └──────────────────┘    └──────┬───────┘
                                                   │
                    ┌──────────────────┐    ┌───────▼───────┐
                    │ result-analyzer  │◀───│paper-presenter│
                    │ (compare)        │    │ (summarize)   │
                    └──────────────────┘    └───────┬───────┘
                           ▲                       │
                    ┌──────┴───────────┐           │
                    │ code-reproducer  │◀──────────┘
                    │ (train on GPU)   │
                    └──────────────────┘
```

## 📄 License

MIT License — see [LICENSE](LICENSE)
