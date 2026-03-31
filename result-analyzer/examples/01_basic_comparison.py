#!/usr/bin/env python3
"""Quick test for result-analyzer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from comparators.metric_comparator import compare_all_metrics
from reporters.markdown_report import generate_markdown_report, generate_json_report, generate_beamer_data

# ═══════════════════════════════════════════════════════════════
# Test 1: Metric Comparison
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("  Test 1: Metric Comparison")
print("=" * 60)

paper_metrics = {
    'accuracy': 95.3,
    'FID': 3.17,
    'PSNR': 28.5,
    'SSIM': 0.92,
    'loss': 0.15,
}

reproduced_metrics = {
    'accuracy': 94.8,
    'FID': 3.45,
    'PSNR': 27.9,
    'SSIM': 0.91,
    'loss': 0.18,
}

results = compare_all_metrics(paper_metrics, reproduced_metrics)

print(f"\n  {'Status':<8} {'Metric':<12} {'Paper':<8} {'Repro':<8} {'Diff':<12} {'Note'}")
print(f"  {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*12} {'-'*20}")

for comp in results['comparisons']:
    print(f"  {comp['emoji']} {comp['status']:<5} {comp['metric']:<12} "
          f"{comp['paper']:<8.4g} {comp['reproduced']:<8.4g} "
          f"{comp['diff_str']:<12} {comp['note']}")

summary = results['summary']
print(f"\n  {summary['overall_emoji']} Overall: {summary['overall_status']}")
print(f"  Passed: {summary['passed']}/{summary['total']} | "
      f"Warned: {summary['warned']} | Failed: {summary['failed']}")

# ═══════════════════════════════════════════════════════════════
# Test 2: Report Generation
# ═══════════════════════════════════════════════════════════════
print(f"\n\n{'=' * 60}")
print("  Test 2: Report Generation")
print("=" * 60)

output_dir = os.path.join(os.path.dirname(__file__), '..', 'test_output')

md_path = generate_markdown_report(
    paper_title='DDPM: Denoising Diffusion Probabilistic Models',
    metric_results=results,
    output_dir=output_dir,
)
print(f"\n  ✅ Markdown report: {md_path}")

json_path = generate_json_report(
    paper_title='DDPM: Denoising Diffusion Probabilistic Models',
    metric_results=results,
    output_dir=output_dir,
)
print(f"  ✅ JSON report: {json_path}")

beamer_data = generate_beamer_data(
    paper_title='DDPM: Denoising Diffusion Probabilistic Models',
    metric_results=results,
    output_dir=output_dir,
)
print(f"  ✅ Beamer data: {beamer_data['data_path']}")
print(f"     {len(beamer_data['slides'])} slides generated")

# Show report content
print(f"\n\n{'=' * 60}")
print("  Generated Markdown Report (first 30 lines)")
print("=" * 60)
with open(md_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 30:
            print("  ...")
            break
        print(f"  {line.rstrip()}")

print("\n\nDone! ✨")
