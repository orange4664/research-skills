"""
reproducibility.py — ML Code Completeness scoring.

Based on the ML Code Completeness Checklist (Papers With Code / NeurIPS).
Automatically scores a repository's reproducibility from 0-100.
"""

from pathlib import Path
import re


def _check_file_exists(code_dir: Path, patterns: list[str]) -> bool:
    """Check if any file matching patterns exists."""
    for pat in patterns:
        if "*" in pat:
            if list(code_dir.glob(pat)):
                return True
        elif (code_dir / pat).exists():
            return True
    return False


def _check_content_has(code_dir: Path, filename: str, keywords: list[str]) -> bool:
    """Check if a file contains any of the keywords."""
    fpath = code_dir / filename
    if not fpath.exists():
        return False
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace").lower()
        return any(kw.lower() in content for kw in keywords)
    except Exception:
        return False


def _readme_content(code_dir: Path) -> str:
    """Get README content."""
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        rpath = code_dir / name
        if rpath.exists():
            try:
                return rpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return ""


def score_reproducibility(code_dir: str) -> dict:
    """Score repository reproducibility based on ML Code Completeness Checklist.

    Returns dict with:
    - total_score: 0-100 overall score
    - grade: A/B/C/D/F letter grade
    - checks: individual check results with points
    - recommendations: things to improve
    """
    code_path = Path(code_dir)
    checks = []
    recommendations = []

    readme = _readme_content(code_path)
    readme_lower = readme.lower()

    # ── 1. Dependencies (15 pts) ──
    has_deps = _check_file_exists(code_path, [
        "requirements.txt", "environment.yml", "environment.yaml",
        "setup.py", "pyproject.toml", "Pipfile", "setup.cfg",
    ])
    checks.append({
        "name": "Dependency specification",
        "passed": has_deps,
        "points": 15 if has_deps else 0,
        "max_points": 15,
        "detail": "requirements.txt / environment.yml / setup.py / pyproject.toml",
    })
    if not has_deps:
        recommendations.append("Add requirements.txt or environment.yml for dependency management")

    # ── 2. Training script (15 pts) ──
    training_patterns = [
        "train.py", "main.py", "run.py", "run_train.py",
        "scripts/train.py", "scripts/run*.py",
        "tools/train.py", "src/train.py",
    ]
    has_training = _check_file_exists(code_path, training_patterns)
    # Also check via content
    if not has_training:
        for pyf in code_path.rglob("*.py"):
            if ".git" not in pyf.parts:
                try:
                    c = pyf.read_text(encoding="utf-8", errors="replace")
                    if "def train" in c and ("optimizer" in c.lower() or "loss" in c.lower()):
                        has_training = True
                        break
                except Exception:
                    pass

    checks.append({
        "name": "Training code",
        "passed": has_training,
        "points": 15 if has_training else 0,
        "max_points": 15,
        "detail": "Dedicated training script or training function",
    })
    if not has_training:
        recommendations.append("Add a clear training script (train.py)")

    # ── 3. Evaluation script (10 pts) ──
    eval_patterns = [
        "eval.py", "evaluate.py", "test.py", "inference.py",
        "scripts/eval*.py", "scripts/test*.py",
        "tools/eval*.py", "tools/test*.py",
    ]
    has_eval = _check_file_exists(code_path, eval_patterns)
    if not has_eval:
        for pyf in code_path.rglob("*.py"):
            if ".git" not in pyf.parts:
                try:
                    c = pyf.read_text(encoding="utf-8", errors="replace")
                    if any(kw in c for kw in ["def evaluate", "def eval", "def test", "def inference"]):
                        has_eval = True
                        break
                except Exception:
                    pass

    checks.append({
        "name": "Evaluation code",
        "passed": has_eval,
        "points": 10 if has_eval else 0,
        "max_points": 10,
        "detail": "Evaluation/test/inference script",
    })
    if not has_eval:
        recommendations.append("Add an evaluation or test script")

    # ── 4. Pre-trained models (10 pts) ──
    has_pretrained = bool(re.search(
        r"(?:pretrained|checkpoint|model.*download|weight|\.pth|\.pt|\.ckpt|\.h5|huggingface|model_zoo)",
        readme_lower,
    ))
    checks.append({
        "name": "Pre-trained models",
        "passed": has_pretrained,
        "points": 10 if has_pretrained else 0,
        "max_points": 10,
        "detail": "Pre-trained model download link in README",
    })
    if not has_pretrained:
        recommendations.append("Provide pre-trained model weights or download links")

    # ── 5. Configuration files (10 pts) ──
    config_patterns = [
        "config.yaml", "config.yml", "config.json", "config.py",
        "configs/*.yaml", "configs/*.yml", "configs/*.json",
        "hparams.yaml", "*.toml",
    ]
    has_config = _check_file_exists(code_path, config_patterns)
    checks.append({
        "name": "Configuration files",
        "passed": has_config,
        "points": 10 if has_config else 0,
        "max_points": 10,
        "detail": "Config files (YAML/JSON/TOML) for hyperparameters",
    })
    if not has_config:
        recommendations.append("Add configuration files for hyperparameters (configs/*.yaml)")

    # ── 6. README training instructions (10 pts) ──
    has_train_cmd = bool(re.search(
        r"(?:python|bash).*(?:train|run|main)",
        readme,
    ))
    checks.append({
        "name": "README training commands",
        "passed": has_train_cmd,
        "points": 10 if has_train_cmd else 0,
        "max_points": 10,
        "detail": "Training command examples in README",
    })
    if not has_train_cmd:
        recommendations.append("Add training command examples to README")

    # ── 7. Results table (10 pts) ──
    has_results = bool(re.search(r"\|.*\|.*\|", readme)) and any(
        kw in readme_lower for kw in [
            "accuracy", "f1", "fid", "inception", "bleu", "rouge",
            "map", "auc", "loss", "psnr", "ssim", "results", "performance",
            "score", "error", "metric",
        ]
    )
    checks.append({
        "name": "Results table",
        "passed": has_results,
        "points": 10 if has_results else 0,
        "max_points": 10,
        "detail": "Performance metrics/results table in README",
    })
    if not has_results:
        recommendations.append("Add a results table with metrics to README")

    # ── 8. Dockerfile (5 pts) ──
    has_docker = _check_file_exists(code_path, ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"])
    checks.append({
        "name": "Docker support",
        "passed": has_docker,
        "points": 5 if has_docker else 0,
        "max_points": 5,
        "detail": "Dockerfile or docker-compose for environment",
    })

    # ── 9. LICENSE (5 pts) ──
    has_license = _check_file_exists(code_path, ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"])
    checks.append({
        "name": "License file",
        "passed": has_license,
        "points": 5 if has_license else 0,
        "max_points": 5,
        "detail": "Open source license file",
    })

    # ── 10. .gitignore (5 pts) ──
    has_gitignore = _check_file_exists(code_path, [".gitignore"])
    checks.append({
        "name": ".gitignore",
        "passed": has_gitignore,
        "points": 5 if has_gitignore else 0,
        "max_points": 5,
        "detail": "Git ignore configuration",
    })

    # ── 11. Tests (5 pts) ──
    has_tests = _check_file_exists(code_path, [
        "tests/", "test/", "test_*.py", "*_test.py",
        "tests/*.py", "test/*.py",
    ])
    checks.append({
        "name": "Test files",
        "passed": has_tests,
        "points": 5 if has_tests else 0,
        "max_points": 5,
        "detail": "Unit tests or test directory",
    })

    # ── Calculate total ──
    total = sum(c["points"] for c in checks)
    max_total = sum(c["max_points"] for c in checks)
    passed = sum(1 for c in checks if c["passed"])

    # Letter grade
    pct = (total / max_total * 100) if max_total > 0 else 0
    if pct >= 90:
        grade = "A"
    elif pct >= 75:
        grade = "B"
    elif pct >= 60:
        grade = "C"
    elif pct >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "total_score": total,
        "max_score": max_total,
        "percentage": round(pct, 1),
        "grade": grade,
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "recommendations": recommendations,
    }
