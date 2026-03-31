#!/usr/bin/env python3
"""
Metric Comparator — Core module for result-analyzer.
Compares reproduced metrics against paper-reported values.
"""
import math
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# Metric Direction Knowledge Base
# 'higher_better' = accuracy, BLEU, etc.
# 'lower_better'  = loss, FID, perplexity, etc.
# ═══════════════════════════════════════════════════════════════

METRIC_DIRECTION = {
    # Classification
    'accuracy': 'higher_better', 'acc': 'higher_better',
    'top1': 'higher_better', 'top5': 'higher_better',
    'top1_accuracy': 'higher_better', 'top5_accuracy': 'higher_better',
    'precision': 'higher_better', 'recall': 'higher_better',
    'f1': 'higher_better', 'f1_score': 'higher_better',
    'auc': 'higher_better', 'auroc': 'higher_better',
    'ap': 'higher_better', 'map': 'higher_better', 'mAP': 'higher_better',

    # Generation Quality
    'fid': 'lower_better', 'FID': 'lower_better',
    'is': 'higher_better', 'IS': 'higher_better',
    'inception_score': 'higher_better',
    'psnr': 'higher_better', 'PSNR': 'higher_better',
    'ssim': 'higher_better', 'SSIM': 'higher_better',
    'lpips': 'lower_better', 'LPIPS': 'lower_better',

    # NLP
    'bleu': 'higher_better', 'BLEU': 'higher_better',
    'bleu4': 'higher_better', 'rouge': 'higher_better',
    'meteor': 'higher_better', 'cider': 'higher_better',
    'perplexity': 'lower_better', 'ppl': 'lower_better',
    'wer': 'lower_better', 'WER': 'lower_better',
    'cer': 'lower_better',

    # Loss / Error
    'loss': 'lower_better', 'train_loss': 'lower_better',
    'val_loss': 'lower_better', 'test_loss': 'lower_better',
    'mse': 'lower_better', 'rmse': 'lower_better', 'mae': 'lower_better',
    'error': 'lower_better', 'error_rate': 'lower_better',

    # Time / Resources
    'training_time': 'lower_better', 'inference_time': 'lower_better',
    'latency': 'lower_better', 'throughput': 'higher_better',
    'params': 'neutral', 'flops': 'neutral',
}


def get_metric_direction(metric_name: str) -> str:
    """Return 'higher_better', 'lower_better', or 'neutral'."""
    name_lower = metric_name.lower().strip()
    # Exact match
    if name_lower in METRIC_DIRECTION:
        return METRIC_DIRECTION[name_lower]
    # Partial match
    for key, direction in METRIC_DIRECTION.items():
        if key in name_lower or name_lower in key:
            return direction
    return 'neutral'


def compare_metric(
    metric_name: str,
    paper_value: float,
    reproduced_value: float,
    abs_tolerance: float = 1.0,
    rel_tolerance: float = 0.05,
) -> Dict:
    """
    Compare a single metric.

    Returns:
        {
            'metric': str,
            'paper': float,
            'reproduced': float,
            'diff_abs': float,
            'diff_rel': float,
            'direction': str,
            'status': 'PASS' | 'WARN' | 'FAIL',
            'emoji': str,
            'note': str,
        }
    """
    direction = get_metric_direction(metric_name)

    diff_abs = reproduced_value - paper_value
    diff_rel = abs(diff_abs) / abs(paper_value) if paper_value != 0 else float('inf')

    # Determine status
    if abs(diff_abs) <= abs_tolerance and diff_rel <= rel_tolerance:
        status = 'PASS'
        emoji = '✅'
        note = 'Within tolerance'
    elif diff_rel <= rel_tolerance * 2:
        status = 'WARN'
        emoji = '⚠️'
        note = 'Close but slightly off'
    else:
        # Check if it's actually better than the paper
        if direction == 'higher_better' and reproduced_value > paper_value:
            status = 'PASS'
            emoji = '🟢'
            note = 'Better than paper!'
        elif direction == 'lower_better' and reproduced_value < paper_value:
            status = 'PASS'
            emoji = '🟢'
            note = 'Better than paper!'
        else:
            status = 'FAIL'
            emoji = '❌'
            if direction == 'higher_better':
                note = f'Below paper by {abs(diff_rel)*100:.1f}%'
            elif direction == 'lower_better':
                note = f'Above paper by {abs(diff_rel)*100:.1f}%'
            else:
                note = f'Differs by {abs(diff_rel)*100:.1f}%'

    # Format diff string
    sign = '+' if diff_abs > 0 else ''
    diff_str = f'{sign}{diff_abs:.4g}'
    if direction == 'higher_better':
        diff_str += ' ↑' if diff_abs > 0 else ' ↓'
    elif direction == 'lower_better':
        diff_str += ' ↓' if diff_abs < 0 else ' ↑'

    return {
        'metric': metric_name,
        'paper': paper_value,
        'reproduced': reproduced_value,
        'diff_abs': diff_abs,
        'diff_rel': diff_rel,
        'diff_str': diff_str,
        'direction': direction,
        'status': status,
        'emoji': emoji,
        'note': note,
    }


def compare_all_metrics(
    paper_metrics: Dict[str, float],
    reproduced_metrics: Dict[str, float],
    abs_tolerance: float = 1.0,
    rel_tolerance: float = 0.05,
) -> Dict:
    """
    Compare all metrics between paper and reproduced results.

    Returns:
        {
            'comparisons': List[Dict],
            'summary': {
                'total': int,
                'passed': int,
                'warned': int,
                'failed': int,
                'overall_status': 'PASS' | 'WARN' | 'FAIL',
                'overall_emoji': str,
            }
        }
    """
    comparisons = []
    matched_metrics = set()

    # Compare metrics that exist in both
    for metric_name, paper_val in paper_metrics.items():
        # Try direct match first
        repro_val = None
        for key in reproduced_metrics:
            if key.lower().strip() == metric_name.lower().strip():
                repro_val = reproduced_metrics[key]
                matched_metrics.add(key)
                break

        if repro_val is not None:
            comp = compare_metric(
                metric_name, paper_val, repro_val,
                abs_tolerance, rel_tolerance
            )
            comparisons.append(comp)
        else:
            comparisons.append({
                'metric': metric_name,
                'paper': paper_val,
                'reproduced': None,
                'diff_abs': None,
                'diff_rel': None,
                'diff_str': 'N/A',
                'direction': get_metric_direction(metric_name),
                'status': 'MISSING',
                'emoji': '⬜',
                'note': 'Not reproduced',
            })

    # Metrics only in reproduced (bonus)
    for key, val in reproduced_metrics.items():
        if key not in matched_metrics:
            comparisons.append({
                'metric': key,
                'paper': None,
                'reproduced': val,
                'diff_abs': None,
                'diff_rel': None,
                'diff_str': 'N/A',
                'direction': get_metric_direction(key),
                'status': 'EXTRA',
                'emoji': 'ℹ️',
                'note': 'Not in paper',
            })

    # Summary
    statuses = [c['status'] for c in comparisons if c['status'] not in ('MISSING', 'EXTRA')]
    passed = statuses.count('PASS')
    warned = statuses.count('WARN')
    failed = statuses.count('FAIL')
    total = len(statuses)

    if failed > 0:
        overall = 'FAIL'
        overall_emoji = '🔴'
    elif warned > 0:
        overall = 'WARN'
        overall_emoji = '🟡'
    elif total > 0:
        overall = 'PASS'
        overall_emoji = '🟢'
    else:
        overall = 'NO_DATA'
        overall_emoji = '⬜'

    return {
        'comparisons': comparisons,
        'summary': {
            'total': total,
            'passed': passed,
            'warned': warned,
            'failed': failed,
            'overall_status': overall,
            'overall_emoji': overall_emoji,
        },
    }
