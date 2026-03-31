# /find-paper

Search for an academic paper and its source code repositories.

## Usage
/find-paper <query>

Where `<query>` can be:
- An arXiv ID (e.g., `1706.03762`)
- A paper title (e.g., `Attention Is All You Need`)
- A DOI (e.g., `10.5555/3295222.3295349`)  
- An arXiv URL (e.g., `https://arxiv.org/abs/1706.03762`)

## Instructions

1. Read the skill instructions: `skills/paper-finder/SKILL.md`
2. Run the search script:
   ```bash
   python skills/paper-finder/scripts/search_paper.py "$ARGUMENTS" --output workspace/paper_info.json
   ```
3. Read and present the results from `workspace/paper_info.json`
4. Highlight:
   - Paper metadata (title, authors, year, venue)
   - PDF download link
   - Source code repositories (mark official vs unofficial)
   - Journal DOI and URL if available
