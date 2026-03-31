#!/usr/bin/env python3
"""
Table Extractor — Extract metric data from paper-parser JSON output.
Also supports extracting from paper figures via OCR (optional).
"""
import json
import re
import os
from typing import Dict, List, Optional


def extract_from_parser_json(json_path: str) -> List[Dict]:
    """
    Extract tables from paper-parser JSON output.

    paper-parser typically produces:
    {
        "tables": [
            {
                "caption": "Table 1: Main results...",
                "content": "| Method | Acc | FID |\n|...",
                "rows": [...]
            }
        ]
    }
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tables = []

    # Try different JSON structures
    raw_tables = data.get('tables', [])
    if not raw_tables:
        # Some parsers nest differently
        for section in data.get('sections', []):
            if 'tables' in section:
                raw_tables.extend(section['tables'])

    for i, table in enumerate(raw_tables):
        parsed = {
            'table_id': i + 1,
            'caption': table.get('caption', f'Table {i+1}'),
            'headers': [],
            'rows': [],
            'metrics': {},
        }

        # Parse markdown table content
        content = table.get('content', '')
        if content:
            lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
            for j, line in enumerate(lines):
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if j == 0:
                    parsed['headers'] = cells
                elif all(c in '-:' or c == '' for c in cells):
                    continue  # separator line
                else:
                    parsed['rows'].append(cells)

        # Pre-process: try to parse rows with direct data
        if table.get('rows'):
            for row in table['rows']:
                if isinstance(row, list):
                    parsed['rows'].append(row)
                elif isinstance(row, dict):
                    parsed['rows'].append(list(row.values()))
                    if not parsed['headers']:
                        parsed['headers'] = list(row.keys())

        tables.append(parsed)

    return tables


def extract_metrics_from_table(
    table: Dict,
    method_name: Optional[str] = None,
) -> Dict[str, float]:
    """
    Extract numerical metrics from a parsed table for a specific method.

    Args:
        table: Parsed table dict (from extract_from_parser_json)
        method_name: If provided, look for this method's row.
                     If None, use the last row (often "Ours").

    Returns:
        Dict of metric_name → value
    """
    headers = table.get('headers', [])
    rows = table.get('rows', [])

    if not rows or not headers:
        return {}

    # Find the target row
    target_row = None

    if method_name:
        for row in rows:
            if row and method_name.lower() in str(row[0]).lower():
                target_row = row
                break

    if target_row is None:
        # Common patterns for "our method"
        our_patterns = [
            'ours', 'our method', 'proposed', 'this work',
            'our', 'this paper',
        ]
        for row in rows:
            if row and any(p in str(row[0]).lower() for p in our_patterns):
                target_row = row
                break

    if target_row is None and rows:
        # Default to last row
        target_row = rows[-1]

    if target_row is None:
        return {}

    # Parse values
    metrics = {}
    for i, header in enumerate(headers):
        if i < len(target_row):
            val_str = str(target_row[i]).strip()
            val = _parse_numeric(val_str)
            if val is not None and header.lower() not in ('method', 'model', 'name', '#'):
                metrics[header] = val

    return metrics


def _parse_numeric(s: str) -> Optional[float]:
    """Parse a numeric value from a string like '95.3', '95.3%', '3.17±0.02', etc."""
    s = s.strip()
    if not s:
        return None

    # Remove percentage sign
    s = s.rstrip('%')

    # Remove ± and everything after
    if '±' in s or '+-' in s:
        s = re.split(r'[±]|\+-', s)[0].strip()

    # Remove bold markers
    s = s.replace('**', '').replace('\\textbf{', '').rstrip('}')

    # Remove trailing non-numeric chars
    s = re.sub(r'[^\d.\-eE]$', '', s)

    try:
        return float(s)
    except ValueError:
        return None


def extract_metrics_from_text(
    text: str,
    metric_names: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    Extract metrics mentioned in free-form text.
    e.g., "We achieve 95.3% accuracy and FID of 3.17"

    Args:
        text: Free-form text from paper
        metric_names: If provided, look only for these metrics

    Returns:
        Dict of metric_name → value
    """
    metrics = {}

    # Common patterns: "X of Y", "X: Y", "X = Y", "Y% X", "X is Y"
    patterns = [
        # "accuracy of 95.3%"
        r'(\w[\w\s]*?)\s+of\s+(\d+\.?\d*)\s*%?',
        # "FID: 3.17"
        r'(\w[\w\s]*?):\s*(\d+\.?\d*)',
        # "FID = 3.17"
        r'(\w[\w\s]*?)\s*=\s*(\d+\.?\d*)',
        # "95.3% accuracy"
        r'(\d+\.?\d*)\s*%?\s+(accuracy|precision|recall|f1)',
        # "achieves 95.3 top-1 accuracy"
        r'achieves?\s+(\d+\.?\d*)\s*%?\s+([\w-]+\s*accuracy)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()
            if len(groups) == 2:
                # Determine which is name and which is value
                try:
                    val = float(groups[1])
                    name = groups[0].strip()
                except ValueError:
                    try:
                        val = float(groups[0])
                        name = groups[1].strip()
                    except ValueError:
                        continue

                if metric_names:
                    if any(m.lower() in name.lower() for m in metric_names):
                        metrics[name] = val
                else:
                    metrics[name] = val

    return metrics
