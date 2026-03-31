"""
config_extractor.py — Configuration system detection and hyperparameter extraction.

Detects: argparse, Hydra, OmegaConf, click, fire, sacred, absl-py
"""

import ast
import re
from pathlib import Path


CONFIG_SYSTEMS = {
    "argparse": r"(?:import argparse|ArgumentParser\()",
    "hydra": r"(?:from hydra|@hydra\.main|OmegaConf)",
    "omegaconf": r"(?:from omegaconf|OmegaConf)",
    "click": r"(?:import click|@click\.command|@click\.option)",
    "fire": r"(?:import fire|fire\.Fire)",
    "sacred": r"(?:from sacred|Experiment\()",
    "absl": r"(?:from absl|absl\.flags)",
    "ml_collections": r"(?:from ml_collections|ConfigDict)",
    "yacs": r"(?:from yacs|CfgNode)",
}

CONFIG_FILES = [
    "config.yaml", "config.yml", "config.json", "config.py", "config.toml",
    "configs/*.yaml", "configs/*.yml", "configs/*.json",
    "conf/*.yaml", "conf/*.yml",
    "hparams.yaml", "hyperparameters.json",
    "args.py", "options.py", "flags.py",
]


class ArgparseExtractor(ast.NodeVisitor):
    """Extract argparse arguments from AST."""

    def __init__(self):
        self.arguments: list[dict] = []

    def visit_Call(self, node: ast.Call):
        try:
            func_str = ast.unparse(node.func)
        except Exception:
            self.generic_visit(node)
            return

        if "add_argument" in func_str:
            arg_info = {"name": "", "type": None, "default": None, "help": ""}

            # Extract argument name
            if node.args:
                try:
                    name = ast.unparse(node.args[-1])
                    arg_info["name"] = name.strip("'\"")
                except Exception:
                    pass

            # Extract keyword arguments
            for kw in node.keywords:
                try:
                    val = ast.unparse(kw.value)
                    if kw.arg == "type":
                        arg_info["type"] = val
                    elif kw.arg == "default":
                        arg_info["default"] = val
                    elif kw.arg == "help":
                        arg_info["help"] = val.strip("'\"")[:100]
                    elif kw.arg == "choices":
                        arg_info["choices"] = val
                except Exception:
                    pass

            if arg_info["name"]:
                self.arguments.append(arg_info)

        self.generic_visit(node)


def _parse_yaml_simple(content: str) -> dict:
    """Simple YAML key-value extraction (no external dependency)."""
    params = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\w[\w.]*)\s*:\s*(.+)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value and not value.startswith("{") and not value.startswith("["):
                params[key] = value
    return params


def extract_configs(code_dir: str) -> dict:
    """Detect config system and extract hyperparameters.

    Returns:
        dict with:
        - config_system: detected configuration management system
        - config_files: list of config files found
        - argparse_args: extracted argparse arguments
        - yaml_params: parameters from YAML config files
        - hyperparameters: consolidated key hyperparameters
    """
    code_path = Path(code_dir)
    detected_systems = []
    config_files_found = []
    argparse_args = []
    yaml_params = {}
    hyperparams = {}

    # Detect config system from source code
    for pyfile in code_path.rglob("*.py"):
        if ".git" in pyfile.parts or "__pycache__" in pyfile.parts:
            continue
        try:
            content = pyfile.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for system, pattern in CONFIG_SYSTEMS.items():
            if re.search(pattern, content) and system not in detected_systems:
                detected_systems.append(system)

        # Extract argparse arguments
        if "add_argument" in content:
            try:
                tree = ast.parse(content)
                extractor = ArgparseExtractor()
                extractor.visit(tree)
                for arg in extractor.arguments:
                    arg["file"] = str(pyfile.relative_to(code_path))
                    argparse_args.append(arg)
            except SyntaxError:
                pass

    # Find config files
    for pattern in CONFIG_FILES:
        if "*" in pattern:
            matches = list(code_path.glob(pattern))
        else:
            p = code_path / pattern
            matches = [p] if p.exists() else []

        for f in matches:
            rel = str(f.relative_to(code_path))
            info = {"path": rel, "type": f.suffix}

            # Parse YAML/YML files
            if f.suffix in [".yaml", ".yml"]:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    params = _parse_yaml_simple(content)
                    info["params"] = params
                    yaml_params.update(params)
                except Exception:
                    pass

            config_files_found.append(info)

    # Consolidate important hyperparameters
    hp_keys = [
        "learning_rate", "lr", "batch_size", "epochs", "num_epochs",
        "max_epochs", "weight_decay", "seed", "dropout", "hidden_size",
        "num_layers", "num_heads", "warmup", "gradient_clip",
    ]
    for key in hp_keys:
        if key in yaml_params:
            hyperparams[key] = yaml_params[key]
        for arg in argparse_args:
            if key in arg["name"].lower() and arg.get("default"):
                hyperparams[arg["name"].lstrip("-").replace("-", "_")] = arg["default"]

    return {
        "config_systems": detected_systems,
        "config_files": config_files_found,
        "argparse_args": argparse_args[:50],  # cap
        "yaml_params": dict(list(yaml_params.items())[:50]),
        "hyperparameters": hyperparams,
    }
