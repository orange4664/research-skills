#!/usr/bin/env python3
"""
Curve Comparator — Compare training curves (loss, accuracy over epochs).
"""
import json
import csv
import os
from typing import Dict, List, Optional, Tuple


def load_training_log(path: str) -> Dict[str, List[float]]:
    """
    Load training log from CSV or JSON.

    Supports formats:
    - CSV with header: epoch, train_loss, val_loss, accuracy, ...
    - JSON list: [{"epoch": 1, "loss": 0.5}, ...]
    - JSON dict: {"train_loss": [0.5, 0.3, ...], "val_loss": [...]}
    - TensorBoard-style CSV: Step, Value
    """
    ext = os.path.splitext(path)[1].lower()

    if ext == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            # List of dicts → column dict
            columns = {}
            for row in data:
                for key, val in row.items():
                    if key not in columns:
                        columns[key] = []
                    try:
                        columns[key].append(float(val))
                    except (ValueError, TypeError):
                        columns[key].append(val)
            return columns
        elif isinstance(data, dict):
            return data
    elif ext == '.csv':
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            columns = {}
            for row in reader:
                for key, val in row.items():
                    if key not in columns:
                        columns[key] = []
                    try:
                        columns[key].append(float(val))
                    except (ValueError, TypeError):
                        columns[key].append(val)
            return columns

    raise ValueError(f"Unsupported file format: {ext}")


def compare_final_values(
    reproduced_log: Dict[str, List[float]],
    paper_metrics: Dict[str, float],
) -> Dict:
    """Compare the final value of each curve against paper-reported values."""
    from .metric_comparator import compare_metric

    comparisons = []
    for metric_name, paper_val in paper_metrics.items():
        # Try to find this metric in the log
        log_key = None
        for key in reproduced_log:
            if key.lower().strip() == metric_name.lower().strip():
                log_key = key
                break
            if metric_name.lower() in key.lower():
                log_key = key
                break

        if log_key and isinstance(reproduced_log[log_key], list) and len(reproduced_log[log_key]) > 0:
            final_val = reproduced_log[log_key][-1]
            comp = compare_metric(metric_name, paper_val, final_val)
            comp['curve_length'] = len(reproduced_log[log_key])
            comparisons.append(comp)

    return {'final_value_comparisons': comparisons}


def compute_curve_stats(
    values: List[float],
    metric_name: str = 'metric',
) -> Dict:
    """Compute statistics for a training curve."""
    if not values:
        return {}

    import numpy as np
    arr = np.array(values, dtype=float)

    # Find convergence point (when it's within 5% of final value)
    final_val = arr[-1]
    threshold = abs(final_val) * 0.05 if final_val != 0 else 0.01
    converge_epoch = len(arr) - 1
    for i, v in enumerate(arr):
        if abs(v - final_val) <= threshold:
            converge_epoch = i
            break

    return {
        'metric': metric_name,
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'final': float(arr[-1]),
        'mean': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'converge_epoch': converge_epoch,
        'total_epochs': len(arr),
        'converge_ratio': converge_epoch / len(arr) if len(arr) > 0 else 1.0,
    }


def compare_curves(
    reproduced_values: List[float],
    reference_values: List[float],
    metric_name: str = 'loss',
) -> Dict:
    """
    Compare two training curves.

    Returns:
        {
            'correlation': float,    # Pearson correlation
            'final_diff': float,     # Absolute diff of final values
            'trend_match': bool,     # Do they have the same trend?
            'reproduced_stats': dict,
            'reference_stats': dict,
        }
    """
    import numpy as np

    repro = np.array(reproduced_values, dtype=float)
    ref = np.array(reference_values, dtype=float)

    # Resample to same length if needed
    if len(repro) != len(ref):
        target_len = min(len(repro), len(ref))
        repro_resampled = np.interp(
            np.linspace(0, 1, target_len),
            np.linspace(0, 1, len(repro)),
            repro
        )
        ref_resampled = np.interp(
            np.linspace(0, 1, target_len),
            np.linspace(0, 1, len(ref)),
            ref
        )
    else:
        repro_resampled = repro
        ref_resampled = ref

    # Pearson correlation
    if np.std(repro_resampled) > 0 and np.std(ref_resampled) > 0:
        correlation = float(np.corrcoef(repro_resampled, ref_resampled)[0, 1])
    else:
        correlation = 0.0

    # Trend comparison (both decreasing or both increasing?)
    repro_trend = 'decreasing' if repro[-1] < repro[0] else 'increasing'
    ref_trend = 'decreasing' if ref[-1] < ref[0] else 'increasing'
    trend_match = repro_trend == ref_trend

    return {
        'metric': metric_name,
        'correlation': correlation,
        'final_diff': float(repro[-1] - ref[-1]),
        'trend_match': trend_match,
        'repro_trend': repro_trend,
        'ref_trend': ref_trend,
        'reproduced_stats': compute_curve_stats(reproduced_values, f'{metric_name}_reproduced'),
        'reference_stats': compute_curve_stats(reference_values, f'{metric_name}_reference'),
    }


def generate_comparison_plot(
    reproduced_log: Dict[str, List[float]],
    reference_log: Optional[Dict[str, List[float]]] = None,
    metrics: Optional[List[str]] = None,
    output_path: str = 'figures/training_curves.png',
    title: str = 'Training Curves Comparison',
) -> str:
    """
    Generate a comparison plot of training curves.

    Returns the output path.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    # Auto-detect metrics to plot
    if metrics is None:
        metrics = [k for k in reproduced_log.keys()
                   if isinstance(reproduced_log[k], list)
                   and len(reproduced_log[k]) > 1
                   and isinstance(reproduced_log[k][0], (int, float))
                   and k.lower() not in ('epoch', 'step', 'iteration')]

    n_metrics = len(metrics)
    if n_metrics == 0:
        return ''

    cols = min(n_metrics, 2)
    rows = (n_metrics + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
    if n_metrics == 1:
        axes = [axes]
    elif rows > 1 or cols > 1:
        axes = axes.flatten()

    for idx, metric in enumerate(metrics[:rows*cols]):
        ax = axes[idx]
        repro_vals = reproduced_log.get(metric, [])

        if repro_vals:
            epochs = list(range(1, len(repro_vals) + 1))
            ax.plot(epochs, repro_vals, 'b-', linewidth=2, label='Reproduced', alpha=0.8)

        if reference_log and metric in reference_log:
            ref_vals = reference_log[metric]
            ref_epochs = list(range(1, len(ref_vals) + 1))
            ax.plot(ref_epochs, ref_vals, 'r--', linewidth=2, label='Paper', alpha=0.8)

        ax.set_title(metric.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_xlabel('Epoch')
        ax.set_ylabel(metric)
        ax.legend()
        ax.grid(True, alpha=0.3)

    # Hide unused subplots
    for idx in range(n_metrics, rows*cols):
        axes[idx].set_visible(False)

    plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return output_path
