#!/usr/bin/env python3
"""
code-writer Example 2: Extractors Demo
========================================
Shows each extractor individually to understand what they detect.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from extractors.architecture import extract_architecture
from extractors.experiment import extract_experiment
from extractors.reference_finder import find_reference_code

# ═══════════════════════════════════════════════════════════════
# Sample paper text (simulating parsed content)
# ═══════════════════════════════════════════════════════════════

sections = [
    {
        'title': 'Method',
        'content': (
            'We propose our model TransDiff, which combines a Transformer '
            'encoder with a diffusion decoder. The encoder uses multi-head '
            'self-attention with 8 heads and hidden dimension 512. '
            'The decoder is a U-Net with residual connections and '
            'layer normalization. We use dropout rate 0.1.'
        ),
    },
    {
        'title': 'Experiments',
        'content': (
            'We train using AdamW optimizer with learning rate 1e-4 '
            'and weight decay 0.01. Batch size is 64 for 200 epochs. '
            'We evaluate on CIFAR-10 and ImageNet using FID and IS metrics. '
            'Training is done on 2x NVIDIA A100 GPUs with gradient clipping 1.0. '
            'Random seed is 42.'
        ),
    },
]

full_text = ' '.join(s['content'] for s in sections)

# ═══════════════════════════════════════════════════════════════
# 1. Architecture Extraction
# ═══════════════════════════════════════════════════════════════

print("=" * 60)
print("  Architecture Extractor")
print("=" * 60)

arch = extract_architecture(sections, full_text)
print(f"  Model name:      {arch['model_name']}")
print(f"  Architecture:    {arch['architecture_type']}")
print(f"  Components:      {arch['components']}")
print(f"  Layer details:   {arch['layer_descriptions']}")

# ═══════════════════════════════════════════════════════════════
# 2. Experiment Extraction
# ═══════════════════════════════════════════════════════════════

print(f"\n{'=' * 60}")
print("  Experiment Extractor")
print("=" * 60)

exp = extract_experiment(sections, full_text)
print(f"  Hyperparameters:")
for k, v in exp['hyperparameters'].items():
    print(f"    {k:15s} = {v}")
print(f"  Datasets:  {exp['datasets']}")
print(f"  Metrics:   {exp['metrics']}")
print(f"  Hardware:  {exp['hardware']}")

# ═══════════════════════════════════════════════════════════════
# 3. Reference Code Finder
# ═══════════════════════════════════════════════════════════════

print(f"\n{'=' * 60}")
print("  Reference Code Finder")
print("=" * 60)

paper_info = {
    'title': 'TransDiff: Transformer-Diffusion Hybrid Model',
    'abstract': full_text,
    'sections': sections,
    'references': [
        'Vaswani et al., "Attention Is All You Need", NeurIPS 2017',
        'Ho et al., "DDPM", code: https://github.com/hojonathanho/diffusion',
    ],
}

refs = find_reference_code(paper_info)
print(f"  Base methods: {refs['base_methods']}")
print(f"  Strategy: {refs['strategy']}")
print(f"\n  Search queries:")
for q in refs['search_queries']:
    print(f"    [{q['source']:15s}] {q['query']}")

if refs['cited_papers']:
    print(f"\n  High-priority cited papers:")
    for p in refs['cited_papers']:
        print(f"    [{p['priority']}] {p['reference'][:80]}")
