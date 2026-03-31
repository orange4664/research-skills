# 🔍 Paper Finder

A multi-source academic paper & source code search tool. Given a paper title, arXiv ID, or DOI, it automatically searches across **4 data sources** to find paper metadata and official code repositories.

## ✨ Features

- **Multi-source search**: arXiv API → Semantic Scholar → HuggingFace Papers → GitHub Search
- **Smart input parsing**: Accepts arXiv ID, URL, DOI, paper title, or PDF file path
- **Official repo detection**: Uses confidence scoring to identify official code repositories
- **Journal tracking**: Finds journal DOI via Semantic Scholar for arXiv preprints
- **Structured output**: Clean JSON with paper metadata, repos, and detailed search logs
- **Zero config**: Works out of the box with just `requests` — no API keys required

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/<your-username>/paper-finder.git
cd paper-finder
pip install -r requirements.txt
```

### Usage

```bash
# Search by arXiv ID
python search_paper.py 1706.03762

# Search by paper title
python search_paper.py "Attention Is All You Need"

# Search by DOI
python search_paper.py "10.5555/3295222.3295349"

# Search by arXiv URL
python search_paper.py "https://arxiv.org/abs/2006.11239"

# Custom output path
python search_paper.py "Denoising Diffusion Probabilistic Models" -o results/ddpm.json
```

### Example Output

```
  [log] === Paper Finder started ===
  [log] Parsed input as title: 'Denoising Diffusion Probabilistic Models'
  [log] Semantic Scholar: found 'Denoising Diffusion Probabilistic Models' (citations: 28738)
  [log] arXiv API: found 'Denoising Diffusion Probabilistic Models' (2020-06-19)
  [log] Found 1 GitHub URL(s) in abstract/comments

✅ Results saved to: paper_info.json
📄 Paper: Denoising Diffusion Probabilistic Models
   arXiv: 2006.11239
   Venue: Neural Information Processing Systems
   Citations: 28738

💻 Found 1 code repo(s):
   ✅ Official [65%] https://github.com/hojonathanho/diffusion (⭐ 0) [abstract_url]
```

## 📖 Supported Input Formats

| Format | Example |
|--------|---------|
| arXiv ID | `1706.03762` |
| arXiv URL | `https://arxiv.org/abs/1706.03762` |
| DOI | `10.5555/3295222.3295349` |
| DOI URL | `https://doi.org/10.5555/3295222.3295349` |
| Paper Title | `Attention Is All You Need` |
| PDF File | `/path/to/paper.pdf` (uses filename as title hint) |

## 🏗️ Architecture

```
User Input
    │
    ▼
┌─────────────────────┐
│  Input Parser        │  Detects: arXiv ID / URL / DOI / Title / PDF
└──────────┬──────────┘
           │
    ┌──────┼──────────────────┐
    ▼      ▼                  ▼
 arXiv   Semantic           (arXiv
  API    Scholar             title
         API                search)
    │      │                  │
    └──────┼──────────────────┘
           ▼
   Paper Metadata (title, authors, abstract, arxiv_id, doi...)
           │
    ┌──────┼────────────────────────┐
    ▼      ▼                        ▼
 Abstract  HuggingFace            GitHub
 URL       Papers API             Search API
 Extract   (githubRepo field)     (title+author)
    │      │                        │
    └──────┼────────────────────────┘
           ▼
   Confidence Scoring & Ranking
           │
           ▼
   paper_info.json
```

## 📊 Confidence Scoring

Each candidate repository is scored based on multiple signals:

| Signal | Score |
|--------|-------|
| GitHub URL found in paper abstract/comments | +0.50 |
| HuggingFace Papers `githubRepo` field | +0.45 |
| Repo description matches paper title keywords | +0.20 |
| Repo name contains paper title keywords | +0.15 |
| Repo owner matches first author name | +0.15 |
| Repo created within ±1 year of paper | +0.10 |
| Star count ≥ 100 | +0.05 |

Repositories with confidence ≥ 0.50 are marked as **official**.

## 📋 Output Schema

```json
{
  "query": "user's original input",
  "found": true,
  "paper": {
    "title": "Paper Title",
    "authors": ["Author 1", "Author 2"],
    "year": 2024,
    "abstract": "...",
    "arxiv_id": "2401.12345",
    "doi": "10.xxxx/...",
    "pdf_url": "https://arxiv.org/pdf/2401.12345.pdf",
    "venue": "NeurIPS",
    "citation_count": 100,
    "journal_url": "https://doi.org/10.xxxx/..."
  },
  "code": {
    "found": true,
    "repositories": [
      {
        "url": "https://github.com/author/repo",
        "stars": 500,
        "is_official": true,
        "confidence": 0.85,
        "source": "abstract_url",
        "reason": "URL found in paper abstract/comments"
      }
    ]
  },
  "search_log": ["step-by-step search details..."]
}
```

## 🔑 Optional: GitHub Token

Without a token, GitHub Search API allows 10 requests/minute (sufficient for single searches). For heavy usage, set a GitHub Personal Access Token:

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
```

**How to create a token:**
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Generate new token (fine-grained) → only needs **Public Repositories (read-only)**

## 🔌 Use as a Claude Code Skill

This tool can also be used as an AI agent skill. Copy the `skill/` directory into your project:

```
your-project/
├── .claude/commands/
│   └── find-paper.md       ← Copy from skill/commands/
└── skills/paper-finder/
    ├── SKILL.md             ← Copy from skill/
    └── scripts/
        └── search_paper.py  ← Copy from root
```

Then use `/find-paper <query>` in Claude Code.

## 📡 Data Sources

| Source | What it provides | Rate Limit |
|--------|-----------------|------------|
| [arXiv API](https://arxiv.org/help/api) | Paper metadata, PDF links | 3s/request (courtesy) |
| [Semantic Scholar](https://api.semanticscholar.org/) | Citations, DOI, venue | 100 req/5min (no key) |
| [HuggingFace Papers](https://huggingface.co/papers) | Paper → GitHub repo mapping | Free |
| [GitHub Search](https://docs.github.com/en/rest/search) | Repository search | 10 req/min (no token) |

> **Note**: Papers with Code was shut down in 2025. HuggingFace Papers serves as its replacement for paper → repo discovery.

## 📄 License

MIT License — see [LICENSE](LICENSE)

## 🤝 Contributing

Issues and PRs are welcome! Some ideas:
- Add support for more paper sources (e.g., PubMed, IEEE Xplore)
- Improve title matching with fuzzy search
- Add a web UI
- Support batch search from a list of papers
