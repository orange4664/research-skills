---
name: paper-downloader
description: Download paper PDFs and clone source code repositories from paper_info.json output.
---

# Paper Downloader Skill

## Purpose
Download paper PDFs and clone associated source code repositories. This is the second step in the paper reproduction pipeline, following paper-finder.

## When to Use
- After running paper-finder to get paper_info.json
- User asks to "download", "get", or "fetch" a paper's PDF
- User asks to "clone" or "get the code" for a paper
- User asks to "reproduce" a paper (run paper-finder first, then this)

## How to Use

### Step 1: Ensure paper_info.json exists
Run paper-finder first if needed:
```bash
python skills/paper-finder/scripts/search_paper.py "<query>" --output workspace/paper_info.json
```

### Step 2: Run the Download Script
```bash
python skills/paper-downloader/download_paper.py workspace/paper_info.json
```

**Options:**
- `--allow-scihub` — Enable Sci-Hub as fallback PDF source
- `--clone-depth 0` — Full git clone (default: shallow clone)
- `--skip-code` — Only download PDF
- `--skip-pdf` — Only clone code
- `-o <dir>` — Custom output directory

### Step 3: Read the Results
Check `workspace/<paper-slug>/download_report.json` for:
- PDF download status and path
- Code clone status and path
- Step-by-step log

### Step 4: Report to User
Tell the user:
- Where the PDF was saved
- Where the code was cloned
- Which dependency files were found in the repo

## Dependencies
- Python 3.10+
- `requests` library
- `git` command-line tool
