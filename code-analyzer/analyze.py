#!/usr/bin/env python3
"""
analyze.py — Comprehensive ML repository analyzer.

Runs all analysis modules and produces a full report.

Usage:
    python analyze.py <code_dir> [-o output.json] [--flowchart]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzers.framework import detect_framework
from analyzers.structure import analyze_structure
from analyzers.ast_analyzer import analyze_ast
from analyzers.training_loop import analyze_training_loop
from analyzers.config_extractor import extract_configs
from analyzers.dependency import analyze_dependencies
from analyzers.readme_parser import parse_readme
from analyzers.reproducibility import score_reproducibility


def generate_flowchart(code_dir: str, output_dir: str) -> str | None:
    """Generate call graph flowchart using code2flow (optional dependency)."""
    try:
        import subprocess
        # Find main training script
        for name in ["train.py", "main.py", "run.py"]:
            target = os.path.join(code_dir, name)
            if os.path.exists(target):
                output = os.path.join(output_dir, f"flowchart_{name.replace('.py', '')}.png")
                result = subprocess.run(
                    ["code2flow", target, "-o", output, "--no-trimming"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    return output
    except (ImportError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def generate_reproduction_plan(analysis: dict) -> list[dict]:
    """Generate a step-by-step reproduction plan from analysis results."""
    steps = []
    deps = analysis.get("dependencies", {})
    readme = analysis.get("readme", {})
    training = analysis.get("training", {})
    framework = analysis.get("framework", {})

    # Step 1: Environment
    env_cmds = []
    if deps.get("files_found"):
        mgr = deps["files_found"][0]["manager"]
        if mgr == "conda":
            env_cmds.append("conda env create -f environment.yml")
        elif mgr == "pip":
            env_cmds.extend([
                "conda create -n repro python=3.10 -y",
                "conda activate repro",
                "pip install -r requirements.txt",
            ])
    if readme.get("install_commands"):
        env_cmds.extend(readme["install_commands"][:5])

    steps.append({"step": 1, "name": "Environment Setup", "commands": env_cmds})

    # Step 2: Data
    if readme.get("data_instructions"):
        steps.append({
            "step": 2,
            "name": "Data Preparation",
            "commands": [],
            "notes": "; ".join(readme["data_instructions"][:3]),
        })

    # Step 3: Training
    train_cmds = []
    if readme.get("training_commands"):
        train_cmds = readme["training_commands"][:3]
    elif training.get("training_loops"):
        loop = training["training_loops"][0]
        train_cmds = [f"python {loop['file']}"]

    fw = framework.get("primary", "")
    gpu_check = {
        "pytorch": 'python -c "import torch; print(torch.cuda.is_available())"',
        "tensorflow": 'python -c "import tensorflow as tf; print(tf.config.list_physical_devices(\'GPU\'))"',
        "jax": 'python -c "import jax; print(jax.devices())"',
    }
    if fw in gpu_check:
        train_cmds.insert(0, f"# Verify GPU: {gpu_check[fw]}")

    steps.append({"step": len(steps) + 1, "name": "Training", "commands": train_cmds})

    # Step 4: Evaluation
    if readme.get("evaluation_commands"):
        steps.append({
            "step": len(steps) + 1,
            "name": "Evaluation",
            "commands": readme["evaluation_commands"][:3],
        })

    # Step 5: Collect results
    steps.append({
        "step": len(steps) + 1,
        "name": "Collect Results",
        "commands": ["# Download: checkpoints/, output/, logs/, figures/"],
    })

    return steps


def analyze(code_dir: str, output_path: str | None = None, do_flowchart: bool = False) -> dict:
    """Run full analysis pipeline."""
    t0 = time.time()
    print("  [log] === Code Analyzer started ===")
    print(f"  [log] Target: {code_dir}")

    # Run all analyzers
    print("  [log] [1/7] Analyzing structure...")
    structure = analyze_structure(code_dir)
    print(f"  [log]   {structure['total_files']} files, {structure['total_py_files']} Python")

    print("  [log] [2/7] Detecting framework...")
    framework = detect_framework(code_dir)
    print(f"  [log]   Framework: {framework['primary']}")

    print("  [log] [3/7] AST deep analysis...")
    ast_result = analyze_ast(code_dir)
    print(f"  [log]   {ast_result['stats']['total_functions']} functions, {ast_result['stats']['model_classes']} model classes, {ast_result['stats']['total_call_edges']} call edges")

    print("  [log] [4/7] Training loop analysis...")
    training = analyze_training_loop(code_dir)
    print(f"  [log]   {training['stats']['loops_found']} loops, optimizers: {training['optimizers']}, loss: {training['loss_functions']}")

    print("  [log] [5/7] Config extraction...")
    configs = extract_configs(code_dir)
    print(f"  [log]   Systems: {configs['config_systems']}, {len(configs['argparse_args'])} argparse args")

    print("  [log] [6/7] Dependency analysis...")
    deps = analyze_dependencies(code_dir)
    print(f"  [log]   {len(deps['packages'])} packages, GPU: {deps['gpu_required']}")

    print("  [log] [7/7] README + Reproducibility scoring...")
    readme = parse_readme(code_dir)
    repro = score_reproducibility(code_dir)
    print(f"  [log]   Reproducibility: {repro['total_score']}/{repro['max_score']} ({repro['grade']})")

    # Flowchart (optional)
    flowchart_path = None
    if do_flowchart and output_path:
        print("  [log] Generating flowchart (code2flow)...")
        out_dir = os.path.dirname(output_path) or "."
        flowchart_path = generate_flowchart(code_dir, out_dir)
        if flowchart_path:
            print(f"  [log]   Flowchart → {flowchart_path}")
        else:
            print("  [log]   code2flow not available or failed")

    # Generate reproduction plan
    analysis = {
        "framework": framework,
        "dependencies": deps,
        "readme": readme,
        "training": training,
    }
    plan = generate_reproduction_plan(analysis)

    elapsed = round(time.time() - t0, 2)

    # Assemble full report
    report = {
        "success": True,
        "repo_name": Path(code_dir).name,
        "analysis_time_seconds": elapsed,
        "framework": framework,
        "structure": structure,
        "ast_analysis": {
            "model_classes": ast_result["model_classes"],
            "key_functions": ast_result["key_functions"],
            "call_graph": ast_result["call_graph"],
            "stats": ast_result["stats"],
        },
        "training": training,
        "configs": configs,
        "dependencies": deps,
        "readme": readme,
        "reproducibility": repro,
        "reproduction_plan": plan,
        "flowchart": flowchart_path,
    }

    # Save
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"  [log] Report saved → {output_path}")

    print(f"  [log] === Analysis complete ({elapsed}s) ===")
    return report


def main():
    parser = argparse.ArgumentParser(description="Comprehensive ML repository analyzer.")
    parser.add_argument("code_dir", help="Path to source code directory")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path")
    parser.add_argument("--flowchart", action="store_true", help="Generate code2flow flowchart (requires code2flow)")

    args = parser.parse_args()
    output = args.output or os.path.join(args.code_dir, "code_analysis.json")

    report = analyze(args.code_dir, output, args.flowchart)

    # Pretty print summary
    print()
    fw = report["framework"]
    ast_s = report["ast_analysis"]["stats"]
    tr = report["training"]
    repro = report["reproducibility"]

    print(f"{'═' * 60}")
    print(f"  📊 Code Analysis Report: {report['repo_name']}")
    print(f"{'═' * 60}")
    print(f"  🔧 Framework     : {fw['primary']} {dict(list(fw.get('all', {}).items())[:3])}")
    print(f"  📁 Files          : {report['structure']['total_files']} ({report['structure']['total_py_files']} .py)")
    print(f"  🏗️  Classes        : {ast_s['total_classes']} ({ast_s['model_classes']} model)")
    print(f"  📐 Functions      : {ast_s['total_functions']}")
    print(f"  🔗 Call edges     : {ast_s['total_call_edges']}")
    print(f"  🔄 Training loops : {tr['stats']['loops_found']} (high-conf: {tr['stats']['high_confidence_loops']})")
    print(f"  ⚡ Optimizers     : {', '.join(tr['optimizers']) or 'none detected'}")
    print(f"  📉 Loss functions : {', '.join(tr['loss_functions']) or 'none detected'}")
    print(f"  📊 LR Schedulers  : {', '.join(tr['lr_schedulers']) or 'none detected'}")
    print(f"  📦 Packages       : {len(report['dependencies']['packages'])}")
    print(f"  🎯 Reproducibility: {repro['total_score']}/{repro['max_score']} = {repro['grade']} ({repro['percentage']}%)")
    print()

    if report["ast_analysis"]["model_classes"]:
        print("  🧠 Model classes:")
        for mc in report["ast_analysis"]["model_classes"][:5]:
            layers = f" ({len(mc['layers'])} layers)" if mc["layers"] else ""
            print(f"     → {mc['name']} [{mc['file']}]{layers}")
        print()

    if repro["recommendations"]:
        print("  💡 Recommendations:")
        for rec in repro["recommendations"]:
            print(f"     • {rec}")
        print()

    plan = report["reproduction_plan"]
    print(f"  📋 Reproduction plan ({len(plan)} steps):")
    for step in plan:
        print(f"     {step['step']}. {step['name']}")
        for cmd in step.get("commands", [])[:2]:
            print(f"        $ {cmd}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
