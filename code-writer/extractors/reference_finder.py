"""
Reference Code Finder — "Standing on the shoulders of giants"

When a paper has NO source code, this module searches for related/cited papers
that DO have code, and collects them as reference material.

The agent can then study these implementations to help write code from scratch.
"""
import re
from typing import Dict, List


def find_reference_code(paper_info: Dict) -> Dict:
    """
    Generate a reference code discovery plan from paper metadata.

    This doesn't execute searches directly (that's the agent's job via paper-finder),
    but it produces structured search queries the agent should use.

    Args:
        paper_info: Dict from paper_info extractor (title, abstract, references, etc.)

    Returns:
        Dict with:
            - base_methods: list of foundational methods to search for
            - search_queries: structured queries for paper-finder
            - cited_papers: papers worth checking for code
            - strategy: recommended approach
    """
    result = {
        'base_methods': [],
        'search_queries': [],
        'cited_papers': [],
        'strategy': '',
    }

    abstract = paper_info.get('abstract', '')
    title = paper_info.get('title', '')
    references = paper_info.get('references', [])
    sections = paper_info.get('sections', [])

    full_text = title + ' ' + abstract
    for sec in sections:
        full_text += ' ' + sec.get('content', '')

    # ── 1. Identify base methods ──
    base_methods = _detect_base_methods(full_text)
    result['base_methods'] = base_methods

    # ── 2. Generate search queries ──
    queries = []

    # Search for the base methods
    for method in base_methods:
        queries.append({
            'query': f'{method} implementation PyTorch',
            'source': 'github',
            'reason': f'Find reference implementation of {method}',
        })
        queries.append({
            'query': method,
            'source': 'paperswithcode',
            'reason': f'Find papers implementing {method} with code',
        })

    # Search for the paper's own topic
    if title:
        queries.append({
            'query': title,
            'source': 'paperswithcode',
            'reason': 'Check if any implementation exists of this exact paper',
        })

    result['search_queries'] = queries

    # ── 3. Identify cited papers worth checking ──
    if references:
        for ref in references[:20]:  # Check first 20 references
            ref_text = ref if isinstance(ref, str) else ref.get('text', str(ref))
            # Prioritize references that mention code, implementation, or are foundational
            if any(kw in ref_text.lower() for kw in ['github', 'code', 'implementation',
                                                      'pytorch', 'tensorflow', 'library']):
                result['cited_papers'].append({
                    'reference': ref_text[:200],
                    'priority': 'high',
                    'reason': 'Explicitly mentions code/implementation',
                })

    # ── 4. Strategy recommendation ──
    if base_methods:
        result['strategy'] = (
            f"This paper builds on {', '.join(base_methods[:3])}. "
            f"Search for implementations of these base methods first. "
            f"Clone the most relevant one and adapt it for this paper's specific modifications. "
            f"Key approach: modify existing {base_methods[0]} code rather than writing from scratch."
        )
    else:
        result['strategy'] = (
            "No clear base method identified. Search for papers on the same task/topic "
            "that do have code. Use them as structural reference for the project layout, "
            "data loading pipeline, and training loop."
        )

    return result


def _detect_base_methods(text: str) -> List[str]:
    """
    Detect foundational methods/architectures mentioned in the paper text.
    These are likely to have existing implementations we can reference.
    """
    # Well-known methods with likely available implementations
    known_methods = [
        # Architectures
        ('ResNet', r'\bResNet\b|\bresnet\b|\bResidual Network\b'),
        ('VGG', r'\bVGG\b'),
        ('Transformer', r'\bTransformer\b'),
        ('BERT', r'\bBERT\b'),
        ('GPT', r'\bGPT\b'),
        ('ViT', r'\bViT\b|\bVision Transformer\b'),
        ('U-Net', r'\bU-?Net\b'),
        ('GAN', r'\bGAN\b|\bGenerative Adversarial\b'),
        ('VAE', r'\bVAE\b|\bVariational Auto-?[Ee]ncoder\b'),
        ('DDPM', r'\bDDPM\b|\bDenoising Diffusion\b'),
        ('Diffusion Model', r'\b[Dd]iffusion [Mm]odel\b|\bscore.based\b'),
        ('Flow', r'\b[Nn]ormalizing [Ff]low\b|\b[Ff]low-based\b'),
        ('EfficientNet', r'\bEfficientNet\b'),
        ('MobileNet', r'\bMobileNet\b'),
        ('YOLO', r'\bYOLO\b'),
        ('Faster R-CNN', r'\bFaster R-CNN\b|\bFasterRCNN\b'),
        ('CLIP', r'\bCLIP\b'),
        ('Stable Diffusion', r'\bStable Diffusion\b'),

        # Techniques
        ('Attention Mechanism', r'\b[Ss]elf-[Aa]ttention\b|\b[Mm]ulti-[Hh]ead [Aa]ttention\b'),
        ('Contrastive Learning', r'\b[Cc]ontrastive [Ll]earning\b|\bSimCLR\b|\bMoCo\b'),
        ('Knowledge Distillation', r'\b[Kk]nowledge [Dd]istillation\b'),
        ('Graph Neural Network', r'\bGNN\b|\bGCN\b|\b[Gg]raph [Nn]eural\b'),
        ('Reinforcement Learning', r'\bRL\b|\b[Rr]einforcement [Ll]earning\b|\bPPO\b|\bDQN\b'),
    ]

    detected = []
    for name, pattern in known_methods:
        if re.search(pattern, text):
            detected.append(name)

    return detected
