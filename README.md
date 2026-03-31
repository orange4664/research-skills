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
| [code-analyzer](./code-analyzer/) | Deep AST analysis, training loop dissection, reproducibility scoring | ✅ Ready |
| [formula2code](./formula2code/) | Convert LaTeX formulas to PyTorch/NumPy code (15 ML patterns + SymPy pipeline) | ✅ Ready |
| [code-writer](./code-writer/) | Generate project scaffolding from paper descriptions (no source code needed) | ✅ Ready |
| [paper-presenter](./paper-presenter/) | Generate Beamer presentations summarizing papers | ✅ Ready |
| [beamer-skill](./beamer-skill/) | Academic Beamer LaTeX presentation lifecycle tool | ✅ Ready (bundled) |
| [code-reproducer](./code-reproducer/) | Execute reproduction on remote GPU servers via mcp-ssh | ✅ Ready |
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
                    ┌──────────────────┐    ┌───────▼───────┐    ┌──────────────┐
                    │  code-analyzer   │◀───│paper-presenter│───▶│ beamer-skill │
                    │ (AST/ML scoring) │    │ (summarize)   │    │ (LaTeX PPT)  │
                    └────────┬─────────┘    └───────────────┘    └──────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
 ┌────────▼─────────┐ ┌──────▼───────┐ ┌────────▼─────────┐
 │  formula2code    │ │ code-writer  │ │ code-reproducer  │
 │ (LaTeX → code)   │ │ (scaffold)   │ │ (train via SSH)  │
 └────────┬─────────┘ └──────┬───────┘ └────────┬─────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                    ┌────────▼─────────┐
                    │ result-analyzer  │
                    │ (compare)        │
                    └──────────────────┘
```

### No Source Code? Two new paths:
- **formula2code**: Paper equations → PyTorch/NumPy functions
- **code-writer**: Paper description → complete project scaffolding (with reference code discovery)

## 📄 License

MIT License — see [LICENSE](LICENSE)

## 🙏 Third-Party

| Component | Author | License | Link |
|-----------|--------|---------|------|
| beamer-skill | [Noi1r](https://github.com/Noi1r) | MIT | [GitHub](https://github.com/Noi1r/beamer-skill) |
| latex2sympy2 | [HuggingFace](https://github.com/huggingface) | MIT | [GitHub](https://github.com/huggingface/latex2sympy2_extended) |
| sympytorch | [patrick-kidger](https://github.com/patrick-kidger) | Apache-2.0 | [GitHub](https://github.com/patrick-kidger/sympytorch) |
| Reproducibility scoring | [Papers With Code](https://paperswithcode.com) | — | [ML Code Completeness](https://medium.com/paperswithcode/ml-code-completeness-checklist-e9127b168501) |
| AST analysis approach | [PyCG](https://github.com/vitsalis/PyCG) (ICSE'21) | Apache-2.0 | [Paper](https://arxiv.org/abs/2103.00587) |
