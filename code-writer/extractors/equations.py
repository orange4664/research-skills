"""
Extract LaTeX equations from paper content for formula2code conversion.
"""
import re
from typing import List, Dict


def extract_equations(paper_data: dict) -> List[Dict]:
    """
    Extract LaTeX equations from paper-parser JSON output.

    Returns list of dicts with: latex, context, equation_number, category
    """
    equations = []

    if isinstance(paper_data, dict):
        # Direct equation list
        for key in ('equations', 'formulas', 'latex_equations'):
            if key in paper_data and isinstance(paper_data[key], list):
                for eq in paper_data[key]:
                    if isinstance(eq, str):
                        equations.append({'latex': eq, 'context': '', 'category': 'unknown'})
                    elif isinstance(eq, dict):
                        equations.append({
                            'latex': eq.get('latex', eq.get('text', '')),
                            'context': eq.get('context', ''),
                            'category': _classify_equation(eq.get('latex', '')),
                        })

        # Search in content blocks (MinerU format)
        if 'content' in paper_data and isinstance(paper_data['content'], list):
            context = ''
            for block in paper_data['content']:
                if isinstance(block, dict):
                    if block.get('type') in ('text', 'paragraph'):
                        context = block.get('text', '')[:100]
                    elif block.get('type') in ('equation', 'formula', 'math'):
                        tex = block.get('latex', block.get('text', ''))
                        if tex:
                            equations.append({
                                'latex': tex,
                                'context': context,
                                'category': _classify_equation(tex),
                                'number': block.get('number', ''),
                            })

    return equations


def extract_equations_from_text(text: str) -> List[Dict]:
    """
    Extract LaTeX equations from raw text/markdown.
    Looks for $...$ and $$...$$ and \\[...\\] patterns.
    """
    equations = []

    # Display math: $$...$$ or \[...\]
    for pattern in [r'\$\$(.*?)\$\$', r'\\\[(.*?)\\\]']:
        for m in re.finditer(pattern, text, re.DOTALL):
            tex = m.group(1).strip()
            if tex and len(tex) > 3:
                # Get surrounding context
                start = max(0, m.start() - 80)
                context = text[start:m.start()].strip()
                equations.append({
                    'latex': tex,
                    'context': context[-80:],
                    'category': _classify_equation(tex),
                })

    return equations


def _classify_equation(latex: str) -> str:
    """Classify an equation into a category based on content."""
    tex = latex.lower()

    if any(kw in tex for kw in ['\\mathcal{l}', 'loss', '\\ell']):
        return 'loss'
    elif any(kw in tex for kw in ['softmax', 'relu', 'sigmoid', 'tanh', 'gelu']):
        return 'activation'
    elif any(kw in tex for kw in ['attention', 'query', 'key', 'value']):
        return 'attention'
    elif any(kw in tex for kw in ['\\nabla', 'gradient', '\\theta', 'update']):
        return 'optimization'
    elif any(kw in tex for kw in ['p(', 'q(', '\\mathcal{n}', 'distribution']):
        return 'probability'
    elif any(kw in tex for kw in ['\\mu', '\\sigma', 'norm', 'batch']):
        return 'normalization'
    elif any(kw in tex for kw in ['\\sum', '\\prod', '\\int']):
        return 'aggregation'
    else:
        return 'other'
