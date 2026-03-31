#!/usr/bin/env python3
"""
analyze_repo.py — Analyze a source code repository to understand how to reproduce it.

Outputs a structured reproduction plan including:
- Framework detection (PyTorch, TF, JAX)
- Training script identification
- Config/hyperparameter extraction
- Dependency analysis
- README reproduction instructions parsing

Usage:
    python analyze_repo.py <code_dir> [-o output.json]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Framework Detection
# ---------------------------------------------------------------------------
FRAMEWORK_INDICATORS = {
    "pytorch": {
        "imports": ["torch", "torch.nn", "torchvision", "pytorch_lightning", "lightning"],
        "files": ["*.pt", "*.pth"],
        "deps": ["torch", "torchvision", "pytorch-lightning", "lightning"],
    },
    "tensorflow": {
        "imports": ["tensorflow", "tf.keras", "keras"],
        "files": ["*.pb", "*.h5", "*.savedmodel"],
        "deps": ["tensorflow", "tensorflow-gpu", "keras", "tf-nightly"],
    },
    "jax": {
        "imports": ["jax", "flax", "optax", "haiku"],
        "files": [],
        "deps": ["jax", "jaxlib", "flax", "optax", "dm-haiku"],
    },
    "diffusers": {
        "imports": ["diffusers"],
        "files": [],
        "deps": ["diffusers"],
    },
    "huggingface": {
        "imports": ["transformers", "datasets", "accelerate"],
        "files": [],
        "deps": ["transformers", "datasets", "accelerate"],
    },
}

TRAINING_SCRIPTS = [
    "train.py", "main.py", "run.py", "run_train.py", "run_training.py",
    "train_net.py", "trainer.py", "experiment.py",
    "scripts/train.py", "scripts/run.py", "scripts/main.py",
    "tools/train.py", "tools/run.py",
    "src/train.py", "src/main.py",
]

CONFIG_FILES = [
    "config.yaml", "config.yml", "config.json", "config.py",
    "configs/*.yaml", "configs/*.yml", "configs/*.json",
    "hparams.yaml", "hyperparameters.json",
    "args.py", "options.py", "flags.py",
]


def detect_framework(code_dir: Path, py_contents: dict[str, str]) -> dict:
    """Detect ML framework used in the repository."""
    scores: dict[str, int] = {}

    for fw_name, indicators in FRAMEWORK_INDICATORS.items():
        score = 0
        # Check imports
        for filepath, content in py_contents.items():
            for imp in indicators["imports"]:
                if f"import {imp}" in content or f"from {imp}" in content:
                    score += 3
        # Check dependency files
        for dep_file in ["requirements.txt", "setup.py", "pyproject.toml", "environment.yml"]:
            dep_path = code_dir / dep_file
            if dep_path.exists():
                dep_content = dep_path.read_text(encoding="utf-8", errors="replace").lower()
                for dep in indicators["deps"]:
                    if dep in dep_content:
                        score += 2
        scores[fw_name] = score

    if not scores or max(scores.values()) == 0:
        return {"primary": "unknown", "scores": scores}

    primary = max(scores, key=scores.get)
    return {
        "primary": primary,
        "scores": {k: v for k, v in sorted(scores.items(), key=lambda x: -x[1]) if v > 0},
    }


# ---------------------------------------------------------------------------
# Training Script Detection
# ---------------------------------------------------------------------------
def find_training_scripts(code_dir: Path, py_contents: dict[str, str]) -> list[dict]:
    """Find and rank potential training scripts."""
    candidates = []

    # Check known patterns
    for pattern in TRAINING_SCRIPTS:
        if "*" in pattern:
            matches = list(code_dir.glob(pattern))
        else:
            p = code_dir / pattern
            matches = [p] if p.exists() else []

        for f in matches:
            rel = str(f.relative_to(code_dir))
            candidates.append({
                "path": rel,
                "confidence": "high",
                "reason": "matches common training script pattern",
            })

    # Search for training-like patterns in all .py files
    seen = {c["path"] for c in candidates}
    for filepath, content in py_contents.items():
        if filepath in seen:
            continue
        train_score = 0
        if "argparse" in content or "ArgumentParser" in content:
            train_score += 1
        if "train(" in content or "def train" in content:
            train_score += 2
        if "optimizer" in content.lower() and "loss" in content.lower():
            train_score += 2
        if "epoch" in content.lower():
            train_score += 1
        if "__main__" in content:
            train_score += 1
        if "wandb" in content or "tensorboard" in content:
            train_score += 1

        if train_score >= 4:
            candidates.append({
                "path": filepath,
                "confidence": "medium",
                "reason": f"contains training patterns (score: {train_score})",
            })

    return candidates


# ---------------------------------------------------------------------------
# Config/Hyperparameter Extraction
# ---------------------------------------------------------------------------
def find_configs(code_dir: Path) -> list[dict]:
    """Find configuration files and extract key hyperparameters."""
    configs = []

    for pattern in CONFIG_FILES:
        if "*" in pattern:
            matches = list(code_dir.glob(pattern))
        else:
            p = code_dir / pattern
            matches = [p] if p.exists() else []

        for f in matches:
            rel = str(f.relative_to(code_dir))
            info = {"path": rel, "type": f.suffix, "params": {}}

            content = f.read_text(encoding="utf-8", errors="replace")

            # Extract common hyperparameters
            hp_patterns = {
                "learning_rate": r"(?:learning_rate|lr)\s*[:=]\s*([\d.e-]+)",
                "batch_size": r"(?:batch_size|bs)\s*[:=]\s*(\d+)",
                "epochs": r"(?:epochs|num_epochs|max_epoch)\s*[:=]\s*(\d+)",
                "weight_decay": r"(?:weight_decay|wd)\s*[:=]\s*([\d.e-]+)",
                "optimizer": r"(?:optimizer)\s*[:=]\s*['\"]?(\w+)['\"]?",
                "seed": r"(?:seed|random_seed)\s*[:=]\s*(\d+)",
            }

            for param, pat in hp_patterns.items():
                m = re.search(pat, content, re.IGNORECASE)
                if m:
                    info["params"][param] = m.group(1)

            configs.append(info)

    return configs


# ---------------------------------------------------------------------------
# Dependency Analysis
# ---------------------------------------------------------------------------
def analyze_dependencies(code_dir: Path) -> dict:
    """Analyze project dependencies."""
    deps = {
        "files_found": [],
        "packages": [],
        "python_version": None,
        "cuda_required": False,
        "gpu_required": False,
    }

    dep_files = {
        "requirements.txt": "pip",
        "environment.yml": "conda",
        "setup.py": "setuptools",
        "pyproject.toml": "pyproject",
        "Pipfile": "pipenv",
        "setup.cfg": "setuptools",
    }

    for fname, manager in dep_files.items():
        fpath = code_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8", errors="replace")
            deps["files_found"].append({"file": fname, "manager": manager})

            # Extract package names
            if fname == "requirements.txt":
                for line in content.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        pkg = re.split(r"[>=<!\[\]]", line)[0].strip()
                        if pkg:
                            deps["packages"].append(pkg)

            # Check CUDA/GPU indicators
            if "cuda" in content.lower() or "gpu" in content.lower():
                deps["cuda_required"] = True
                deps["gpu_required"] = True
            if "torch" in content and "cu" in content:
                deps["cuda_required"] = True

    # Check Dockerfile
    dockerfile = code_dir / "Dockerfile"
    if dockerfile.exists():
        content = dockerfile.read_text(encoding="utf-8", errors="replace")
        deps["files_found"].append({"file": "Dockerfile", "manager": "docker"})
        # Extract base image
        base = re.search(r"FROM\s+(.+)", content)
        if base:
            deps["docker_base_image"] = base.group(1).strip()
        if "cuda" in content.lower() or "nvidia" in content.lower():
            deps["cuda_required"] = True
            deps["gpu_required"] = True

    return deps


# ---------------------------------------------------------------------------
# README Parsing
# ---------------------------------------------------------------------------
def parse_readme(code_dir: Path) -> dict:
    """Parse README for reproduction instructions."""
    readme_info = {
        "found": False,
        "has_install_instructions": False,
        "has_training_command": False,
        "install_commands": [],
        "training_commands": [],
        "data_instructions": [],
        "evaluation_commands": [],
    }

    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        rpath = code_dir / name
        if rpath.exists():
            readme_info["found"] = True
            content = rpath.read_text(encoding="utf-8", errors="replace")
            break
    else:
        return readme_info

    # Extract code blocks
    code_blocks = re.findall(r"```(?:bash|sh|shell|python)?\n(.*?)```", content, re.DOTALL)

    for block in code_blocks:
        lines = block.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Installation commands
            if any(kw in line for kw in ["pip install", "conda install", "apt-get", "pip3 install"]):
                readme_info["install_commands"].append(line)
                readme_info["has_install_instructions"] = True

            # Training commands
            if "python" in line and any(kw in line for kw in ["train", "run", "main", "experiment"]):
                readme_info["training_commands"].append(line)
                readme_info["has_training_command"] = True

            # Evaluation commands
            if "python" in line and any(kw in line for kw in ["eval", "test", "infer", "sample", "generate"]):
                readme_info["evaluation_commands"].append(line)

    # Look for data download instructions
    data_patterns = [
        r"(?:download|get|fetch|prepare)\s+(?:the\s+)?data",
        r"dataset",
        r"data[\s_]?(?:dir|path|root|folder)",
    ]
    for pat in data_patterns:
        if re.search(pat, content, re.IGNORECASE):
            # Find the section around this mention
            for line in content.split("\n"):
                if re.search(pat, line, re.IGNORECASE):
                    readme_info["data_instructions"].append(line.strip())
                    break

    return readme_info


# ---------------------------------------------------------------------------
# Generate Reproduction Plan
# ---------------------------------------------------------------------------
def generate_repro_plan(
    framework: dict,
    scripts: list,
    configs: list,
    deps: dict,
    readme: dict,
) -> list[dict]:
    """Generate a step-by-step reproduction plan."""
    steps = []

    # Step 1: Environment setup
    env_cmds = []
    if deps.get("files_found"):
        manager = deps["files_found"][0]["manager"]
        if manager == "conda":
            env_cmds.append("conda env create -f environment.yml")
            env_cmds.append("conda activate <env_name>")
        elif manager == "pip":
            env_cmds.append("conda create -n repro python=3.10 -y")
            env_cmds.append("conda activate repro")
            env_cmds.append("pip install -r requirements.txt")
        elif manager == "docker":
            env_cmds.append(f"docker build -t repro .")
            env_cmds.append(f"docker run --gpus all -it repro")
    if readme.get("install_commands"):
        env_cmds.extend(readme["install_commands"])

    steps.append({
        "step": 1,
        "name": "Environment Setup",
        "commands": env_cmds,
        "notes": "Create isolated environment and install dependencies",
    })

    # Step 2: Data preparation (if mentioned)
    if readme.get("data_instructions"):
        steps.append({
            "step": 2,
            "name": "Data Preparation",
            "commands": [],
            "notes": "Follow dataset instructions: " + "; ".join(readme["data_instructions"][:3]),
        })

    # Step 3: Training
    train_cmds = []
    if readme.get("training_commands"):
        train_cmds = readme["training_commands"][:3]
    elif scripts:
        best = scripts[0]
        train_cmds = [f"python {best['path']}"]

    # Add GPU/distributed hints
    fw = framework.get("primary", "unknown")
    if fw == "pytorch" and deps.get("gpu_required"):
        if not any("CUDA" in c for c in train_cmds):
            train_cmds.insert(0, "# Verify GPU: python -c \"import torch; print(torch.cuda.is_available())\"")
    elif fw == "tensorflow":
        train_cmds.insert(0, "# Verify GPU: python -c \"import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))\"")

    steps.append({
        "step": len(steps) + 1,
        "name": "Training",
        "commands": train_cmds,
        "notes": f"Framework: {fw}. Use tmux for persistent session.",
    })

    # Step 4: Evaluation
    if readme.get("evaluation_commands"):
        steps.append({
            "step": len(steps) + 1,
            "name": "Evaluation",
            "commands": readme["evaluation_commands"][:3],
            "notes": "Run evaluation/inference after training",
        })

    # Step 5: Collect results
    steps.append({
        "step": len(steps) + 1,
        "name": "Collect Results",
        "commands": [
            "# Download: output/, results/, checkpoints/, logs/",
            "# Download: any .png, .jpg, .csv, .json result files",
            "# Download: training logs for loss/accuracy curves",
        ],
        "notes": "Download all result artifacts for comparison",
    })

    return steps


# ---------------------------------------------------------------------------
# Main Analysis
# ---------------------------------------------------------------------------
def analyze_repo(code_dir: str, output_path: str | None = None) -> dict:
    """Main entry point — full repository analysis."""
    print("  [log] === Repository Analyzer started ===")

    code = Path(code_dir)
    if not code.is_dir():
        return {"success": False, "error": f"Not a directory: {code_dir}"}

    # Read all Python files
    py_contents: dict[str, str] = {}
    for f in code.rglob("*.py"):
        if ".git" in f.parts or "__pycache__" in f.parts:
            continue
        try:
            rel = str(f.relative_to(code))
            py_contents[rel] = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
    print(f"  [log] Scanned {len(py_contents)} Python files")

    # Run analyses
    framework = detect_framework(code, py_contents)
    print(f"  [log] Framework: {framework['primary']}")

    scripts = find_training_scripts(code, py_contents)
    print(f"  [log] Training scripts: {len(scripts)} found")

    configs = find_configs(code)
    print(f"  [log] Config files: {len(configs)} found")

    deps = analyze_dependencies(code)
    print(f"  [log] Dependencies: {len(deps.get('packages', []))} packages, GPU: {deps.get('gpu_required')}")

    readme = parse_readme(code)
    print(f"  [log] README: {'found' if readme['found'] else 'not found'}, training commands: {len(readme.get('training_commands', []))}")

    # Generate reproduction plan
    plan = generate_repro_plan(framework, scripts, configs, deps, readme)
    print(f"  [log] Generated {len(plan)}-step reproduction plan")

    # File inventory
    all_files = []
    for f in code.rglob("*"):
        if f.is_file() and ".git" not in f.parts:
            rel = str(f.relative_to(code))
            all_files.append({"path": rel, "size_kb": round(f.stat().st_size / 1024, 1)})

    report = {
        "success": True,
        "repo_name": code.name,
        "total_files": len(all_files),
        "python_files": len(py_contents),
        "framework": framework,
        "training_scripts": scripts,
        "configs": configs,
        "dependencies": deps,
        "readme": readme,
        "reproduction_plan": plan,
    }

    # Save
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  [log] Report saved → {output_path}")

    print("  [log] === Analysis complete ===")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Analyze a code repository for reproduction.")
    parser.add_argument("code_dir", help="Path to source code directory")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path")

    args = parser.parse_args()
    output = args.output or os.path.join(args.code_dir, "repo_analysis.json")

    report = analyze_repo(args.code_dir, output)

    print()
    if report["success"]:
        fw = report["framework"]
        print(f"✅ Repository: {report['repo_name']}")
        print(f"🔧 Framework: {fw['primary']}")
        print(f"📄 Files: {report['total_files']} total, {report['python_files']} Python")
        print(f"🎯 Training scripts: {len(report['training_scripts'])}")
        if report["training_scripts"]:
            for s in report["training_scripts"][:3]:
                print(f"   → {s['path']} [{s['confidence']}]")
        print(f"⚙️  Configs: {len(report['configs'])}")
        print(f"📦 Dependencies: {len(report['dependencies'].get('packages', []))} packages")
        print(f"📋 Reproduction plan: {len(report['reproduction_plan'])} steps")
        for step in report["reproduction_plan"]:
            print(f"   {step['step']}. {step['name']}")
            for cmd in step.get("commands", [])[:2]:
                print(f"      $ {cmd}")
    else:
        print(f"❌ {report.get('error')}")

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
