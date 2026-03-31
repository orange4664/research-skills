#!/usr/bin/env python3
"""
formula2code — Convert LaTeX math formulas to executable PyTorch/NumPy code.

Usage:
    python convert.py "\\frac{1}{N}\\sum_{i=1}^{N}(y_i - \\hat{y}_i)^2"
    python convert.py "\\frac{1}{N}\\sum_{i=1}^{N}(y_i - \\hat{y}_i)^2" --to pytorch
    python convert.py --from-paper paper_content.json --to pytorch -o formulas/
    python convert.py --list-patterns
"""
import argparse
import json
import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from converters.ml_patterns import match_ml_pattern, get_all_pattern_names, BUILTIN_PATTERNS
from converters.latex_parser import parse_latex, parse_latex_batch
from converters.to_python import sympy_to_python_code, format_expression_info, sympy_to_latex_roundtrip


def convert_single(latex: str, target: str = "all", validate: bool = True) -> dict:
    """
    Convert a single LaTeX formula to code.

    Args:
        latex: LaTeX math string
        target: "pytorch", "numpy", "python", or "all"
        validate: Whether to run numerical validation

    Returns:
        Conversion result dict
    """
    result = {
        'input_latex': latex,
        'method': None,
        'outputs': {},
        'errors': [],
    }

    # ── Layer 1: ML Pattern Matching ──
    pattern = match_ml_pattern(latex)
    if pattern:
        result['method'] = 'pattern_match'
        result['pattern'] = pattern
        result['outputs'] = {
            'pytorch_functional': pattern.get('pytorch_functional', ''),
            'pytorch_class': pattern.get('pytorch_class', ''),
            'numpy_code': pattern.get('numpy_code', ''),
            'description': pattern.get('description', ''),
        }
        return result

    # ── Layer 2: LaTeX → SymPy ──
    expr, meta = parse_latex(latex)
    result['parse_meta'] = meta

    if expr is None:
        result['method'] = 'failed'
        result['errors'] = meta.get('errors', ['Parse failed'])
        return result

    result['method'] = 'sympy_pipeline'
    result['sympy_expr'] = str(expr)
    result['sympy_latex'] = sympy_to_latex_roundtrip(expr)
    result['expression_info'] = format_expression_info(expr)

    # ── Layer 3: SymPy → Code ──
    outputs = {}

    if target in ('pytorch', 'all'):
        try:
            from converters.to_pytorch import sympy_to_pytorch, generate_pytorch_code
            pt_result = sympy_to_pytorch(expr)
            outputs['pytorch_code'] = pt_result['code']
            outputs['pytorch_symbols'] = pt_result['symbols']
        except Exception as e:
            result['errors'].append(f'PyTorch conversion: {e}')

    if target in ('numpy', 'all'):
        try:
            from converters.to_numpy import sympy_to_numpy, generate_numpy_code
            np_func, np_symbols, np_code = sympy_to_numpy(expr)
            outputs['numpy_code'] = np_code
            outputs['numpy_symbols'] = np_symbols
        except Exception as e:
            result['errors'].append(f'NumPy conversion: {e}')

    if target in ('python', 'all'):
        try:
            outputs['python_code'] = sympy_to_python_code(expr)
        except Exception as e:
            result['errors'].append(f'Python conversion: {e}')

    result['outputs'] = outputs

    # ── Layer 4: Validation ──
    if validate and expr is not None:
        try:
            from converters.to_numpy import sympy_to_numpy as _s2n
            from converters.validator import validate_conversion
            np_func, _, _ = _s2n(expr)
            report = validate_conversion(expr, numpy_func=np_func, n_samples=5)
            result['validation'] = {
                'passed': report['passed'],
                'summary': report['summary'],
                'errors': report['errors'],
            }
        except Exception as e:
            result['validation'] = {'passed': False, 'error': str(e)}

    return result


def convert_from_paper(paper_json_path: str, target: str = "pytorch") -> list:
    """
    Extract LaTeX formulas from a paper-parser JSON and convert them all.

    Args:
        paper_json_path: Path to paper-parser output JSON
        target: Output target ("pytorch", "numpy", "python", "all")

    Returns:
        List of conversion results
    """
    with open(paper_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract LaTeX formulas from MinerU output
    formulas = []
    if isinstance(data, dict):
        # Try common MinerU JSON structures
        for key in ('equations', 'formulas', 'latex_equations'):
            if key in data:
                formulas.extend(data[key])
        # Also search in content blocks
        if 'content' in data and isinstance(data['content'], list):
            for block in data['content']:
                if isinstance(block, dict) and block.get('type') in ('equation', 'formula'):
                    tex = block.get('latex', block.get('text', ''))
                    if tex:
                        formulas.append(tex)

    if not formulas:
        print(f"[!] No formulas found in {paper_json_path}")
        return []

    print(f"[*] Found {len(formulas)} formulas in paper JSON")
    results = []
    for i, tex in enumerate(formulas):
        print(f"  [{i+1}/{len(formulas)}] Converting: {tex[:50]}...")
        result = convert_single(tex, target=target)
        results.append(result)

    return results


def print_result(result: dict, verbose: bool = False):
    """Pretty-print a conversion result."""
    method = result.get('method', 'unknown')
    latex = result.get('input_latex', '')

    print(f"\n{'═' * 70}")
    print(f"  📐 Input:  {latex[:60]}{'...' if len(latex) > 60 else ''}")
    print(f"  🔧 Method: {method}")

    if method == 'pattern_match':
        p = result.get('pattern', {})
        print(f"  🎯 Pattern: {p.get('name', '?')} ({p.get('description', '')})")
        print(f"  📦 PyTorch: {p.get('pytorch_functional', '')}")
        if p.get('pytorch_class'):
            print(f"  📦 Class:   {p.get('pytorch_class', '')}")
        if p.get('numpy_code'):
            print(f"  🔢 NumPy:   {p.get('numpy_code', '')}")

    elif method == 'sympy_pipeline':
        print(f"  🧮 SymPy:  {result.get('sympy_expr', '')}")
        outputs = result.get('outputs', {})
        if 'pytorch_code' in outputs and verbose:
            print(f"\n  ── PyTorch Code ──")
            for line in outputs['pytorch_code'].split('\n'):
                print(f"  {line}")
        elif 'pytorch_code' in outputs:
            # Just show the return line
            for line in outputs['pytorch_code'].split('\n'):
                if 'return' in line:
                    print(f"  📦 PyTorch: {line.strip()}")

        if 'numpy_code' in outputs and verbose:
            print(f"\n  ── NumPy Code ──")
            for line in outputs['numpy_code'].split('\n'):
                print(f"  {line}")

        val = result.get('validation', {})
        if val:
            status = '✅' if val.get('passed') else '❌'
            print(f"  {status} Validation: {val.get('summary', 'N/A')}")

    elif method == 'failed':
        print(f"  ❌ Errors: {result.get('errors', [])}")

    if result.get('errors'):
        for err in result['errors']:
            print(f"  ⚠️  {err}")


def main():
    parser = argparse.ArgumentParser(
        description='formula2code — Convert LaTeX formulas to executable code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "\\frac{1}{N}\\sum_{i=1}^{N}(y_i - \\hat{y}_i)^2"
  %(prog)s "\\text{softmax}(x)" --to pytorch
  %(prog)s --from-paper paper.json --to pytorch -o results.json
  %(prog)s --list-patterns
        """,
    )

    parser.add_argument('latex', nargs='?', help='LaTeX formula string')
    parser.add_argument('--to', choices=['pytorch', 'numpy', 'python', 'all'],
                        default='all', help='Output target (default: all)')
    parser.add_argument('--from-paper', metavar='JSON',
                        help='Extract and convert formulas from paper-parser JSON')
    parser.add_argument('-o', '--output', metavar='PATH',
                        help='Output path (JSON file or directory)')
    parser.add_argument('--no-validate', action='store_true',
                        help='Skip numerical validation')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show full generated code')
    parser.add_argument('--list-patterns', action='store_true',
                        help='List all built-in ML formula patterns')

    args = parser.parse_args()

    # List patterns mode
    if args.list_patterns:
        print(f"\n{'═' * 70}")
        print(f"  📋 Built-in ML Formula Patterns ({len(BUILTIN_PATTERNS)} total)")
        print(f"{'═' * 70}")
        for p in BUILTIN_PATTERNS:
            print(f"\n  [{p['category'].upper():>14}] {p['name']}")
            print(f"    {p['description']}")
            print(f"    PyTorch: {p.get('pytorch_functional', 'N/A')}")
        return

    # From paper mode
    if args.from_paper:
        results = convert_from_paper(args.from_paper, target=args.to)
        for r in results:
            print_result(r, verbose=args.verbose)

        if args.output:
            # Serialize (remove non-serializable items)
            for r in results:
                r.pop('function', None)
                r.pop('module', None)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n[✓] Results saved to {args.output}")
        return

    # Single formula mode
    if not args.latex:
        parser.print_help()
        return

    result = convert_single(args.latex, target=args.to, validate=not args.no_validate)
    print_result(result, verbose=args.verbose)

    if args.output:
        result.pop('function', None)
        result.pop('module', None)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[✓] Result saved to {args.output}")


if __name__ == '__main__':
    main()
