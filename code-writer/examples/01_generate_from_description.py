#!/usr/bin/env python3
"""
code-writer Example 1: Generate from Description
==================================================
Simplest usage: pass a text description → get a full project.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from generate import generate_project

# ═══════════════════════════════════════════════════════════════
# Example: Generate a DDPM project from description
# ═══════════════════════════════════════════════════════════════

paper_data = {
    'title': 'Denoising Diffusion Probabilistic Models',
    'abstract': (
        'We present high quality image synthesis results using diffusion '
        'probabilistic models. Our best results are obtained by training '
        'on a weighted variational bound designed according to a novel '
        'connection between diffusion probabilistic models and denoising '
        'score matching with Langevin dynamics.'
    ),
    'sections': [
        {
            'title': 'Method',
            'content': (
                'We use a U-Net architecture with self-attention layers '
                'at the 16x16 resolution. The model is trained with Adam '
                'optimizer with learning rate 2e-4 and batch size 128 '
                'for 800000 steps on CIFAR-10.'
            ),
        },
        {
            'title': 'Experiments',
            'content': (
                'We evaluate using FID and Inception Score (IS) on '
                'CIFAR-10 and LSUN. With dropout rate 0.1 and '
                '4 NVIDIA V100 GPUs.'
            ),
        },
    ],
    'references': [
        'Ho et al., "Denoising Diffusion Probabilistic Models", NeurIPS 2020',
        'See https://github.com/hojonathanho/diffusion for code.',
    ],
    'full_text': '',
}

# Build full_text for architecture detection
paper_data['full_text'] = paper_data['title'] + ' ' + paper_data['abstract']
for sec in paper_data['sections']:
    paper_data['full_text'] += ' ' + sec['content']

output_dir = os.path.join(os.path.dirname(__file__), '..', 'test_ddpm_output')
generate_project(paper_data, output_dir, framework='pytorch')

print(f"\n\n📂 Check generated project at: {output_dir}")
print("   Key files to review:")
print("   - src/model.py          → model skeleton with detected components")
print("   - src/train.py          → training loop with extracted hyperparams")
print("   - configs/default.yaml  → all settings in one place")
print("   - references/search_plan.md → where to find reference code")
print("   - implementation_checklist.md → step-by-step guide")
