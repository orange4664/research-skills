"""
Extract basic paper metadata from paper-parser JSON output.
"""
import json
import re
from typing import Dict, Optional


def extract_paper_info(paper_json_path: str) -> Dict:
    """
    Extract title, authors, year, abstract, and key sections from paper-parser output.

    Args:
        paper_json_path: Path to paper-parser JSON output

    Returns:
        Dict with: title, authors, year, abstract, sections, references
    """
    with open(paper_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    info = {
        'title': '',
        'authors': [],
        'year': '',
        'abstract': '',
        'sections': [],
        'references': [],
        'keywords': [],
    }

    # Handle different JSON structures from MinerU / paper-parser
    if isinstance(data, dict):
        info['title'] = data.get('title', data.get('doc_title', ''))
        info['authors'] = data.get('authors', [])
        info['year'] = str(data.get('year', data.get('publication_year', '')))
        info['abstract'] = data.get('abstract', '')

        # Extract sections
        if 'sections' in data:
            info['sections'] = data['sections']
        elif 'content' in data and isinstance(data['content'], list):
            current_section = None
            for block in data['content']:
                if isinstance(block, dict):
                    if block.get('type') in ('heading', 'section_title'):
                        current_section = {
                            'title': block.get('text', ''),
                            'content': '',
                        }
                        info['sections'].append(current_section)
                    elif current_section and block.get('type') in ('text', 'paragraph'):
                        current_section['content'] += block.get('text', '') + '\n'

        # Extract references
        if 'references' in data:
            info['references'] = data['references']
        elif 'bibliography' in data:
            info['references'] = data['bibliography']

    return info


def extract_from_markdown(md_path: str) -> Dict:
    """
    Extract paper info from a markdown file (alternative to JSON).
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    info = {
        'title': '',
        'authors': [],
        'abstract': '',
        'sections': [],
        'full_text': text,
    }

    # Try to extract title (first H1)
    h1 = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if h1:
        info['title'] = h1.group(1).strip()

    # Extract abstract
    abs_match = re.search(
        r'(?:abstract|摘要)[:\s]*\n(.*?)(?=\n#|\n\*\*|$)',
        text, re.IGNORECASE | re.DOTALL
    )
    if abs_match:
        info['abstract'] = abs_match.group(1).strip()

    # Extract sections
    sections = re.findall(r'^##\s+(.+)$', text, re.MULTILINE)
    for sec_title in sections:
        # Get content until next section
        pattern = re.escape(f'## {sec_title}') + r'\n(.*?)(?=\n##\s|\Z)'
        content_match = re.search(pattern, text, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ''
        info['sections'].append({
            'title': sec_title,
            'content': content,
        })

    return info
