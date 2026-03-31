---
name: paper-finder
description: Search for academic papers and their source code repositories using multi-source APIs (arXiv, Semantic Scholar, HuggingFace Papers, GitHub).
---

# Paper Finder Skill

## Purpose
Find academic paper metadata and associated source code repositories from multiple data sources. This is the first step in a paper reproduction pipeline.

## When to Use
- User asks to "find", "search", or "look up" a paper
- User provides an arXiv ID, DOI, paper title, or URL
- User asks to "reproduce" or "replicate" a paper (run this first to find the paper and code)
- User wants to know if a paper has official source code

## How to Use

### Step 1: Run the Search Script
Execute the Python script with the user's query:

```bash
python skills/paper-finder/scripts/search_paper.py "<query>" --output workspace/paper_info.json
```

**Supported query formats:**
- **arXiv ID**: `1706.03762`, `2301.12345`
- **arXiv URL**: `https://arxiv.org/abs/1706.03762`
- **DOI**: `10.5555/3295222.3295349`
- **Paper title**: `Attention Is All You Need`
- **PDF path**: `/path/to/paper.pdf` (uses filename as title hint)

### Step 2: Read the Results
After execution, read `workspace/paper_info.json` to get structured results including paper metadata and code repositories.

### Step 3: Interpret Results
- **`is_official: true`** (confidence ≥ 0.50): Likely the authors' official repository
- **`source: "abstract_url"`**: GitHub URL was found directly in the paper text — very reliable
- **`source: "hf_papers"`**: Repository linked by HuggingFace community — reliable
- **`source: "github_search"`**: Found via GitHub search — verify manually

### Step 4: Present Findings to User
Summarize the results clearly: paper title, authors, year, PDF link, code repos (sorted by confidence).

## Dependencies
- Python 3.10+
- `requests` library (`pip install requests`)

## Optional: GitHub Token
Set `GITHUB_TOKEN` environment variable for higher GitHub API rate limits.

## Error Handling
- If Semantic Scholar returns 429, the search continues with other sources
- If no paper is found, suggest the user try a different query format
- Check `search_log` in output JSON for detailed step-by-step information
