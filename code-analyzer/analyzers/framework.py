"""
framework.py — ML framework detection.
"""

from pathlib import Path

FRAMEWORK_INDICATORS = {
    "pytorch": {
        "imports": ["torch", "torch.nn", "torchvision", "pytorch_lightning", "lightning"],
        "deps": ["torch", "torchvision", "pytorch-lightning", "lightning", "timm"],
    },
    "tensorflow": {
        "imports": ["tensorflow", "tf.keras", "keras"],
        "deps": ["tensorflow", "tensorflow-gpu", "keras", "tf-nightly"],
    },
    "jax": {
        "imports": ["jax", "flax", "optax", "haiku"],
        "deps": ["jax", "jaxlib", "flax", "optax", "dm-haiku"],
    },
    "huggingface": {
        "imports": ["transformers", "datasets", "accelerate", "peft", "trl"],
        "deps": ["transformers", "datasets", "accelerate", "peft", "trl"],
    },
    "diffusers": {
        "imports": ["diffusers"],
        "deps": ["diffusers"],
    },
    "sklearn": {
        "imports": ["sklearn", "scikit-learn"],
        "deps": ["scikit-learn", "sklearn"],
    },
}


def detect_framework(code_dir: str, py_contents: dict[str, str] | None = None) -> dict:
    """Detect ML framework(s) used in the repository."""
    code_path = Path(code_dir)

    if py_contents is None:
        py_contents = {}
        for f in code_path.rglob("*.py"):
            if ".git" not in f.parts and "__pycache__" not in f.parts:
                try:
                    py_contents[str(f.relative_to(code_path))] = f.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except Exception:
                    pass

    scores: dict[str, int] = {}

    for fw_name, indicators in FRAMEWORK_INDICATORS.items():
        score = 0
        for content in py_contents.values():
            for imp in indicators["imports"]:
                if f"import {imp}" in content or f"from {imp}" in content:
                    score += 3

        for dep_file in ["requirements.txt", "setup.py", "pyproject.toml", "environment.yml"]:
            dep_path = code_path / dep_file
            if dep_path.exists():
                try:
                    dep_content = dep_path.read_text(encoding="utf-8", errors="replace").lower()
                    for dep in indicators["deps"]:
                        if dep in dep_content:
                            score += 2
                except Exception:
                    pass

        scores[fw_name] = score

    if not scores or max(scores.values()) == 0:
        return {"primary": "unknown", "all": {}, "scores": scores}

    primary = max(scores, key=scores.get)
    detected = {k: v for k, v in sorted(scores.items(), key=lambda x: -x[1]) if v > 0}

    return {"primary": primary, "all": detected, "scores": scores}
