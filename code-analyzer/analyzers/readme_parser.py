"""
readme_parser.py — Parse README for reproduction-relevant information.
"""

import re
from pathlib import Path


def parse_readme(code_dir: str) -> dict:
    """Parse README for reproduction instructions."""
    code_path = Path(code_dir)
    info = {
        "found": False,
        "has_install_instructions": False,
        "has_training_command": False,
        "install_commands": [],
        "training_commands": [],
        "evaluation_commands": [],
        "data_instructions": [],
        "has_results_table": False,
        "has_figures": False,
    }

    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        rpath = code_path / name
        if rpath.exists():
            info["found"] = True
            try:
                content = rpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return info
            break
    else:
        return info

    # Extract code blocks
    code_blocks = re.findall(r"```(?:bash|sh|shell|python)?\n(.*?)```", content, re.DOTALL)

    for block in code_blocks:
        for line in block.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if any(kw in line for kw in ["pip install", "conda install", "apt-get", "pip3 install"]):
                info["install_commands"].append(line)
                info["has_install_instructions"] = True

            if "python" in line and any(kw in line for kw in ["train", "run", "main", "experiment"]):
                info["training_commands"].append(line)
                info["has_training_command"] = True

            if "python" in line and any(kw in line for kw in ["eval", "test", "infer", "sample", "generate"]):
                info["evaluation_commands"].append(line)

    # Data instructions
    data_section = re.search(r"(?:##?\s*(?:data|dataset).*?\n)(.*?)(?=\n##?\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if data_section:
        for line in data_section.group(1).split("\n")[:5]:
            if line.strip():
                info["data_instructions"].append(line.strip())

    # Results table
    info["has_results_table"] = bool(re.search(r"\|.*\|.*\|", content))
    info["has_figures"] = bool(re.search(r"!\[.*\]\(.*\)", content))

    return info
