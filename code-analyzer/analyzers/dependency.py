"""
dependency.py — Dependency and environment analysis.
"""

import re
from pathlib import Path


def analyze_dependencies(code_dir: str) -> dict:
    """Analyze project dependencies."""
    code_path = Path(code_dir)
    deps = {
        "files_found": [],
        "packages": [],
        "python_version": None,
        "cuda_required": False,
        "gpu_required": False,
        "docker_base_image": None,
    }

    dep_files = {
        "requirements.txt": "pip",
        "environment.yml": "conda",
        "environment.yaml": "conda",
        "setup.py": "setuptools",
        "pyproject.toml": "pyproject",
        "Pipfile": "pipenv",
        "setup.cfg": "setuptools",
    }

    for fname, manager in dep_files.items():
        fpath = code_path / fname
        if fpath.exists():
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            deps["files_found"].append({"file": fname, "manager": manager})

            if fname == "requirements.txt":
                for line in content.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        pkg = re.split(r"[>=<!\[\];@]", line)[0].strip()
                        if pkg:
                            deps["packages"].append(pkg)

            if "cuda" in content.lower() or "gpu" in content.lower():
                deps["cuda_required"] = True
                deps["gpu_required"] = True

            # Python version from pyproject.toml
            if fname == "pyproject.toml":
                m = re.search(r'python.*?["\']([><=!~\d.]+)["\']', content)
                if m:
                    deps["python_version"] = m.group(1)

    # Dockerfile
    dockerfile = code_path / "Dockerfile"
    if dockerfile.exists():
        try:
            content = dockerfile.read_text(encoding="utf-8", errors="replace")
            deps["files_found"].append({"file": "Dockerfile", "manager": "docker"})
            base = re.search(r"FROM\s+(.+)", content)
            if base:
                deps["docker_base_image"] = base.group(1).strip()
            if "cuda" in content.lower() or "nvidia" in content.lower():
                deps["cuda_required"] = True
                deps["gpu_required"] = True
        except Exception:
            pass

    return deps
