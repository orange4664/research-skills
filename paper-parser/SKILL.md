---
name: paper-parser
description: Parse PDF papers into structured Markdown/JSON using MinerU's precision extraction API.
---

# Paper Parser Skill

## Purpose
Parse PDF papers into structured data (Markdown, images, tables, formulas) using MinerU's precision API. This is the third step in the paper reproduction pipeline.

## When to Use
- After downloading a paper PDF with paper-downloader
- User asks to "parse", "extract", or "analyze" a PDF paper
- User needs structured content from a paper for summarization or reproduction

## First-Time Setup
On first use, the user needs to provide their MinerU API token:
1. Ask the user to visit https://mineru.net/apiManage to get their token
2. Set the environment variable: `set MINERU_TOKEN=<token>` (Windows) or `export MINERU_TOKEN=<token>` (Linux/Mac)
3. The token is a long JWT string starting with "eyJ..."

## How to Use

### Step 1: Ensure PDF exists
The PDF should have been downloaded by paper-downloader, typically at:
`workspace/<paper-slug>/paper/paper.pdf`

### Step 2: Run the Parser
```bash
python skills/paper-parser/parse_paper.py workspace/<paper-slug>/paper/paper.pdf -o workspace/<paper-slug>/parsed/
```

**Options:**
- `--model vlm` — Highest precision (default, recommended for academic papers)
- `--model pipeline` — Faster but less precise
- `--language en` — For English papers (default)
- `--language ch` — For Chinese papers
- `--timeout 600` — Increase timeout for large papers

### Step 3: Read the Results
Check `workspace/<paper-slug>/parsed/` for:
- `*.md` — Full paper in Markdown format
- `images/` — Extracted figures and diagrams
- `tables/` — Extracted table data
- `parse_report.json` — Parsing log and file list

### Step 4: Report to User
Tell the user:
- How many pages were parsed
- Key files generated (Markdown, images count)
- Any errors or warnings from the parser

## Dependencies
- Python 3.10+
- `requests` library
- MinerU API token (from https://mineru.net/apiManage)

## Error Handling
- If token is missing, prompt user to set MINERU_TOKEN
- If parsing fails, check parse_report.json for error details
- For large papers (>600 pages), suggest splitting or using a different tool
- If upload fails, check network connectivity to mineru.net
