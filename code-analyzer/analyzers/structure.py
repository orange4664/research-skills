"""
structure.py — File and directory structure analysis.
"""

import os
from pathlib import Path

TRAINING_SCRIPTS = [
    "train.py", "main.py", "run.py", "run_train.py", "run_training.py",
    "trainer.py", "experiment.py",
    "scripts/train.py", "scripts/run.py", "scripts/main.py",
    "tools/train.py", "tools/run.py",
    "src/train.py", "src/main.py",
]


def analyze_structure(code_dir: str) -> dict:
    """Analyze repository file structure."""
    code_path = Path(code_dir)

    files = []
    dirs = set()
    total_py = 0
    total_size = 0
    extensions: dict[str, int] = {}

    for f in code_path.rglob("*"):
        if ".git" in f.parts:
            continue
        if f.is_file():
            rel = str(f.relative_to(code_path))
            size = f.stat().st_size
            ext = f.suffix.lower()
            files.append({"path": rel, "size_kb": round(size / 1024, 1), "ext": ext})
            total_size += size
            extensions[ext] = extensions.get(ext, 0) + 1
            if ext == ".py":
                total_py += 1
        elif f.is_dir():
            dirs.add(str(f.relative_to(code_path)))

    # Detect training scripts
    training_scripts = []
    for pattern in TRAINING_SCRIPTS:
        p = code_path / pattern
        if p.exists():
            training_scripts.append({
                "path": pattern,
                "confidence": "high",
                "reason": "matches common pattern",
            })

    return {
        "total_files": len(files),
        "total_dirs": len(dirs),
        "total_py_files": total_py,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "extensions": dict(sorted(extensions.items(), key=lambda x: -x[1])),
        "training_scripts": training_scripts,
        "top_dirs": sorted(dirs)[:20],
    }
