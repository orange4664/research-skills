#!/usr/bin/env python3
"""
Result Analyzer — Main CLI entry point.

Compare reproduced results against paper-reported values.
Generate reproduction reports in Markdown, JSON, and Beamer-ready formats.

Usage:
  # Compare metrics directly
  python analyze.py --paper-metrics '{"accuracy": 95.3, "FID": 3.17}' \
                    --repro-metrics '{"accuracy": 94.8, "FID": 3.45}' \
                    -o report/

  # From paper-parser JSON + training log CSV
  python analyze.py --paper-json paper_content.json \
                    --repro-log train_log.csv \
                    -o report/

  # Full comparison with images
  python analyze.py --paper-json paper_content.json \
                    --repro-log train_log.csv \
                    --repro-images generated/ \
                    --paper-figures figures/ \
                    --fid \
                    -o report/
"""
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description='Result Analyzer — Compare reproduction vs paper results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Input sources
    parser.add_argument('--paper-metrics', type=str,
                        help='Paper metrics as JSON string: \'{"acc": 95.3}\'')
    parser.add_argument('--repro-metrics', type=str,
                        help='Reproduced metrics as JSON string')
    parser.add_argument('--paper-json', type=str,
                        help='Path to paper-parser JSON (for table extraction)')
    parser.add_argument('--repro-log', type=str,
                        help='Path to training log CSV/JSON')
    parser.add_argument('--repro-images', type=str,
                        help='Path to reproduced images (file or directory)')
    parser.add_argument('--paper-figures', type=str,
                        help='Path to paper figures (file or directory)')
    parser.add_argument('--method-name', type=str, default=None,
                        help='Method name to look for in paper tables (default: auto-detect "Ours")')

    # Options
    parser.add_argument('-o', '--output', type=str, default='reproduction_report',
                        help='Output directory')
    parser.add_argument('--title', type=str, default='Paper Reproduction',
                        help='Paper title for the report')
    parser.add_argument('--abs-tol', type=float, default=1.0,
                        help='Absolute tolerance for metric comparison')
    parser.add_argument('--rel-tol', type=float, default=0.05,
                        help='Relative tolerance for metric comparison')
    parser.add_argument('--fid', action='store_true',
                        help='Compute FID score (optional, requires pytorch-fid)')
    parser.add_argument('--beamer', action='store_true',
                        help='Also generate beamer-skill compatible data')
    parser.add_argument('--no-plots', action='store_true',
                        help='Skip plot generation')

    args = parser.parse_args()

    # ═══════════════════════════════════════════════════════════
    # Step 1: Collect paper metrics
    # ═══════════════════════════════════════════════════════════
    paper_metrics = {}
    reproduced_metrics = {}

    if args.paper_metrics:
        paper_metrics = json.loads(args.paper_metrics)
        print(f"  📄 Paper metrics: {paper_metrics}")

    if args.repro_metrics:
        reproduced_metrics = json.loads(args.repro_metrics)
        print(f"  🔬 Reproduced metrics: {reproduced_metrics}")

    # Extract from paper-parser JSON
    if args.paper_json and os.path.exists(args.paper_json):
        print(f"  📄 Loading paper-parser JSON: {args.paper_json}")
        from comparators.table_extractor import extract_from_parser_json, extract_metrics_from_table
        tables = extract_from_parser_json(args.paper_json)
        print(f"     Found {len(tables)} tables")

        # Try to extract metrics from the first results table
        for table in tables:
            caption = table.get('caption', '').lower()
            if any(kw in caption for kw in ['result', 'comparison', 'performance', 'main']):
                extracted = extract_metrics_from_table(table, args.method_name)
                if extracted:
                    paper_metrics.update(extracted)
                    print(f"     Extracted from '{table['caption']}': {extracted}")
                    break

        # Also try paper title from JSON
        if not args.title or args.title == 'Paper Reproduction':
            with open(args.paper_json, 'r', encoding='utf-8') as f:
                paper_data = json.load(f)
            if 'title' in paper_data:
                args.title = paper_data['title']

    # ═══════════════════════════════════════════════════════════
    # Step 2: Load reproduced training log
    # ═══════════════════════════════════════════════════════════
    curve_results = None
    repro_log_data = None

    if args.repro_log and os.path.exists(args.repro_log):
        print(f"  📊 Loading training log: {args.repro_log}")
        from comparators.curve_comparator import load_training_log, compare_final_values
        repro_log_data = load_training_log(args.repro_log)
        print(f"     Found columns: {list(repro_log_data.keys())}")

        # Extract final values as reproduced metrics
        for key, vals in repro_log_data.items():
            if (isinstance(vals, list) and len(vals) > 0
                    and isinstance(vals[-1], (int, float))
                    and key.lower() not in ('epoch', 'step', 'iteration')):
                if key not in reproduced_metrics:
                    reproduced_metrics[key] = vals[-1]

        # Compare final values against paper
        if paper_metrics:
            curve_results = compare_final_values(repro_log_data, paper_metrics)

        # Generate training curve plot
        if not args.no_plots and repro_log_data:
            from comparators.curve_comparator import generate_comparison_plot
            figures_dir = os.path.join(args.output, 'figures')
            plot_path = generate_comparison_plot(
                repro_log_data,
                output_path=os.path.join(figures_dir, 'training_curves.png'),
                title=f'{args.title} — Training Curves',
            )
            if plot_path:
                print(f"  📈 Generated: {plot_path}")

    # ═══════════════════════════════════════════════════════════
    # Step 3: Compare metrics
    # ═══════════════════════════════════════════════════════════
    metric_results = None

    if paper_metrics and reproduced_metrics:
        from comparators.metric_comparator import compare_all_metrics
        metric_results = compare_all_metrics(
            paper_metrics, reproduced_metrics,
            abs_tolerance=args.abs_tol,
            rel_tolerance=args.rel_tol,
        )
        summary = metric_results['summary']
        print(f"\n  {summary['overall_emoji']} Overall: {summary['overall_status']}")
        print(f"     Passed: {summary['passed']}/{summary['total']}")

    # ═══════════════════════════════════════════════════════════
    # Step 4: Image comparison (optional)
    # ═══════════════════════════════════════════════════════════
    image_results = None

    if args.repro_images and args.paper_figures:
        print(f"\n  🖼️  Comparing images...")
        from comparators.image_comparator import compare_images, generate_side_by_side
        image_results = []

        if os.path.isfile(args.repro_images) and os.path.isfile(args.paper_figures):
            result = compare_images(args.repro_images, args.paper_figures, args.fid)
            image_results.append(result)

            if not args.no_plots:
                figures_dir = os.path.join(args.output, 'figures')
                generate_side_by_side(
                    args.repro_images, args.paper_figures,
                    os.path.join(figures_dir, 'sample_comparison.png'),
                )
        elif os.path.isdir(args.repro_images) and os.path.isdir(args.paper_figures):
            # Compare matching filenames
            repro_files = sorted(os.listdir(args.repro_images))
            paper_files = sorted(os.listdir(args.paper_figures))

            for rf in repro_files:
                if rf in paper_files:
                    result = compare_images(
                        os.path.join(args.repro_images, rf),
                        os.path.join(args.paper_figures, rf),
                    )
                    image_results.append(result)

            # FID on directories
            if args.fid:
                fid_result = compare_images(
                    args.repro_images, args.paper_figures,
                    compute_fid_flag=True,
                )
                if fid_result.get('fid') is not None:
                    image_results.append(fid_result)

    # ═══════════════════════════════════════════════════════════
    # Step 5: Generate reports
    # ═══════════════════════════════════════════════════════════
    print(f"\n  📝 Generating reports...")

    from reporters.markdown_report import (
        generate_markdown_report,
        generate_json_report,
        generate_beamer_data,
    )

    md_path = generate_markdown_report(
        paper_title=args.title,
        metric_results=metric_results,
        curve_results=curve_results,
        image_results=image_results,
        output_dir=args.output,
    )
    print(f"     Markdown: {md_path}")

    json_path = generate_json_report(
        paper_title=args.title,
        metric_results=metric_results,
        curve_results=curve_results,
        image_results=image_results,
        output_dir=args.output,
    )
    print(f"     JSON:     {json_path}")

    if args.beamer:
        beamer_result = generate_beamer_data(
            paper_title=args.title,
            metric_results=metric_results,
            curve_results=curve_results,
            image_results=image_results,
            output_dir=args.output,
        )
        print(f"     Beamer:   {beamer_result['data_path']}")

    print(f"\n  ✨ Done! Report saved to: {args.output}/")


if __name__ == '__main__':
    main()
