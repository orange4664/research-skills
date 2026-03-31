---
name: paper-presenter
description: Prepare structured presentation materials from parsed papers for beamer-skill's create workflow.
---

# Paper Presenter Skill

## Purpose
Bridge between paper-parser (MinerU output) and beamer-skill. Analyzes parsed paper content + optional source code to produce a structured "materials package" that feeds directly into beamer-skill's `create [topic]` workflow.

## When to Use
- After running paper-parser to get structured markdown/figures
- User asks to "make a presentation", "create slides", or "summarize this paper as a talk"
- User asks to "present the reproduction results" or "make a comparison between paper and code"

## How to Use

### Step 1: Ensure Prerequisites
- Parsed output from paper-parser (directory with `full.md`, `images/`, JSON files)
- (Optional) Source code from paper-downloader

### Step 2: Run the Preparation Script

**Standard paper overview:**
```bash
python skills/paper-presenter/prepare_presentation.py workspace/<paper>/parsed/ -o workspace/<paper>/presentation_materials.md
```

**With source code analysis (paper ↔ code comparison):**
```bash
python skills/paper-presenter/prepare_presentation.py workspace/<paper>/parsed/ \
    --code-dir workspace/<paper>/code/<repo>/ \
    --style reproduction-report \
    -o workspace/<paper>/presentation_materials.md
```

**Options:**
- `--style overview` — Standard paper overview (~15-20 slides)
- `--style deep-dive` — Technical deep-dive (~30-40 slides)
- `--style reproduction-report` — Paper + code + reproduction results comparison
- `--code-dir <dir>` — Source code repo for paper-code alignment analysis
- `--paper-info <file>` — paper_info.json for metadata (auto-detected if in standard layout)
- `--language en|zh` — Output language

### Step 3: Feed Materials to beamer-skill
The output `presentation_materials.md` is designed as **Phase 0 input** for beamer-skill's `create` workflow.

Tell the agent:
```
Create a beamer presentation based on the materials in workspace/<paper>/presentation_materials.md
```

The beamer-skill will:
1. Read the materials file (Phase 0)
2. Ask the user about duration, audience, scope (Phase 1)
3. Build a slide structure plan (Phase 2)
4. Draft slides using extracted figures and formulas (Phase 3-4)
5. Run quality checks (Phase 5)

### Key Features for Reproduction Presentations
When `--style reproduction-report` and `--code-dir` are used:
- **Code-Theory Alignment Table** — maps paper sections to source code files
- **Comparison Slide Suggestions** — paper formula on left, code on right
- **Implementation Detail Highlights** — what's in code but not in paper
- **Delta Analysis Structure** — original results vs reproduced results

## Dependencies
- Python 3.10+
- No external libraries required (uses only stdlib + json)
- Requires: beamer-skill installed for the actual presentation generation

## Output Format
The output is a structured Markdown file containing:
1. Paper metadata (title, authors, venue)
2. Section-by-section content analysis
3. Available figures with paths
4. Key mathematical formulas
5. Source code analysis (if provided)
6. Code-theory alignment mapping (if code provided)
7. Suggested slide structure for the chosen style
8. Instructions for beamer-skill agent
