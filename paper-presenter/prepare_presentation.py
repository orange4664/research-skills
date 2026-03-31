#!/usr/bin/env python3
"""
prepare_presentation.py — Prepare structured materials for Beamer presentation generation.

Takes MinerU-parsed paper output + optional source code, analyzes them,
and produces a structured material package that feeds into beamer-skill's
`create` workflow.

Usage:
    python prepare_presentation.py <parsed_dir> [options]

Options:
    --code-dir <dir>       Path to cloned source code repository
    --output <path>        Output material package path (default: presentation_materials.md)
    --style <type>         Presentation style: overview | deep-dive | reproduction-report
    --language <lang>      Output language: en | zh (default: en)

Output:
    A structured Markdown file containing:
    1. Paper metadata and summary
    2. Section-by-section content analysis
    3. Key figures with file paths and descriptions
    4. Mathematical formulas extracted
    5. Code-theory alignment analysis (if code provided)
    6. Suggested slide structure
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Content Extraction from MinerU Output
# ---------------------------------------------------------------------------
def load_parsed_content(parsed_dir: str) -> dict:
    """Load and parse MinerU output files."""
    result = {
        "markdown": "",
        "content_list": [],
        "images": [],
        "layout": None,
    }

    parsed = Path(parsed_dir)

    # Load full markdown
    md_files = list(parsed.glob("*.md"))
    if md_files:
        # Prefer full.md
        md_file = None
        for f in md_files:
            if f.name == "full.md":
                md_file = f
                break
        if not md_file:
            md_file = md_files[0]
        result["markdown"] = md_file.read_text(encoding="utf-8", errors="replace")
        print(f"  [log] Loaded markdown: {md_file.name} ({len(result['markdown'])} chars)")

    # Load content list JSON (structured content)
    for json_file in parsed.glob("*content_list*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                result["content_list"] = data
            elif isinstance(data, dict):
                result["content_list"] = data.get("content_list", [data])
            print(f"  [log] Loaded content list: {json_file.name} ({len(result['content_list'])} items)")
            break
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

    # Catalog images
    img_dir = parsed / "images"
    if img_dir.exists():
        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() in (".jpg", ".jpeg", ".png", ".svg"):
                result["images"].append({
                    "path": str(img),
                    "name": img.name,
                    "size_kb": img.stat().st_size / 1024,
                })
        print(f"  [log] Found {len(result['images'])} images")

    return result


# ---------------------------------------------------------------------------
# Paper Structure Analysis
# ---------------------------------------------------------------------------
def analyze_paper_structure(markdown: str) -> dict:
    """Analyze paper structure from markdown content."""
    sections = []
    current_section = {"title": "Abstract", "level": 1, "content": "", "formulas": [], "figures": []}

    lines = markdown.split("\n")
    for line in lines:
        # Detect section headers
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            # Save previous section
            if current_section["content"].strip():
                sections.append(current_section)
            level = len(m.group(1))
            title = m.group(2).strip()
            current_section = {"title": title, "level": level, "content": "", "formulas": [], "figures": []}
        else:
            current_section["content"] += line + "\n"

        # Detect formulas
        if "$$" in line or "\\begin{equation}" in line or "\\begin{align}" in line:
            current_section["formulas"].append(line.strip())

        # Detect figure references
        if "![" in line or "\\includegraphics" in line:
            current_section["figures"].append(line.strip())

    # Don't forget last section
    if current_section["content"].strip():
        sections.append(current_section)

    # Extract inline math formulas
    all_formulas = []
    for m in re.finditer(r'\$\$(.+?)\$\$', markdown, re.DOTALL):
        formula = m.group(1).strip()
        if len(formula) > 10:  # Skip trivial formulas
            all_formulas.append(formula)

    print(f"  [log] Found {len(sections)} sections, {len(all_formulas)} significant formulas")

    return {
        "sections": sections,
        "formulas": all_formulas,
        "total_chars": len(markdown),
        "estimated_pages": len(markdown) // 3000,  # rough estimate
    }


# ---------------------------------------------------------------------------
# Source Code Analysis (optional)
# ---------------------------------------------------------------------------
def analyze_source_code(code_dir: str) -> dict:
    """Analyze source code repository for paper-code alignment."""
    if not code_dir or not os.path.exists(code_dir):
        return {"available": False}

    code_path = Path(code_dir)
    result = {
        "available": True,
        "repo_name": code_path.name,
        "files": [],
        "key_files": [],
        "dependencies": [],
        "model_files": [],
        "training_files": [],
        "readme_summary": "",
    }

    # Scan all Python/code files
    code_extensions = {".py", ".ipynb", ".sh", ".yaml", ".yml", ".cfg", ".toml"}
    for f in code_path.rglob("*"):
        if f.is_file() and f.suffix in code_extensions:
            rel = str(f.relative_to(code_path))
            size_kb = f.stat().st_size / 1024
            result["files"].append({"path": rel, "size_kb": round(size_kb, 1)})

            # Classify files
            name_lower = f.name.lower()
            rel_lower = rel.lower()

            if any(kw in name_lower for kw in ["model", "network", "architecture", "backbone", "module"]):
                result["model_files"].append(rel)
            elif any(kw in name_lower for kw in ["train", "trainer", "run", "main", "experiment"]):
                result["training_files"].append(rel)

    # Read README
    for readme_name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        readme = code_path / readme_name
        if readme.exists():
            text = readme.read_text(encoding="utf-8", errors="replace")
            # Truncate to first 2000 chars for summary
            result["readme_summary"] = text[:2000]
            break

    # Check dependency files
    dep_files = ["requirements.txt", "environment.yml", "setup.py", "pyproject.toml", "Pipfile"]
    for dep in dep_files:
        dep_path = code_path / dep
        if dep_path.exists():
            content = dep_path.read_text(encoding="utf-8", errors="replace")
            result["dependencies"].append({
                "file": dep,
                "content": content[:1000],  # Truncate
            })

    print(f"  [log] Code analysis: {len(result['files'])} files, "
          f"{len(result['model_files'])} model files, "
          f"{len(result['training_files'])} training files")

    return result


# ---------------------------------------------------------------------------
# Code-Theory Alignment Analysis
# ---------------------------------------------------------------------------
def analyze_code_theory_alignment(paper_sections: list, code_info: dict) -> list:
    """
    Analyze alignment between paper sections and code implementation.
    Returns a list of alignment observations.
    """
    if not code_info.get("available"):
        return []

    alignments = []

    # Map paper sections to likely code files
    section_keywords = {}
    for sec in paper_sections:
        title_lower = sec["title"].lower()
        keywords = set(re.findall(r"\w{4,}", title_lower))
        section_keywords[sec["title"]] = keywords

    # Check which code files might correspond to which sections
    for code_file in code_info.get("files", []):
        path_lower = code_file["path"].lower()
        path_words = set(re.findall(r"\w{4,}", path_lower))

        for sec_title, sec_kw in section_keywords.items():
            overlap = sec_kw & path_words
            if overlap and len(overlap) >= 1:
                alignments.append({
                    "paper_section": sec_title,
                    "code_file": code_file["path"],
                    "matching_keywords": list(overlap),
                    "note": f"Code file '{code_file['path']}' likely implements section '{sec_title}'"
                })

    # Model architecture alignment
    if code_info.get("model_files"):
        alignments.append({
            "paper_section": "Model / Architecture",
            "code_file": ", ".join(code_info["model_files"][:3]),
            "matching_keywords": ["model", "architecture"],
            "note": "Model architecture implementation files"
        })

    # Training pipeline alignment
    if code_info.get("training_files"):
        alignments.append({
            "paper_section": "Experiments / Training",
            "code_file": ", ".join(code_info["training_files"][:3]),
            "matching_keywords": ["train", "experiment"],
            "note": "Training pipeline implementation files"
        })

    print(f"  [log] Found {len(alignments)} code-theory alignment points")
    return alignments


# ---------------------------------------------------------------------------
# Generate Presentation Materials
# ---------------------------------------------------------------------------
def generate_materials(
    parsed_content: dict,
    paper_structure: dict,
    code_info: dict,
    alignments: list,
    paper_meta: dict,
    style: str,
    language: str,
) -> str:
    """Generate the structured material package for beamer-skill."""

    lang_label = "中文" if language == "zh" else "English"

    output = []
    output.append("# 📊 Paper Presentation Materials\n")
    output.append(f"> Auto-generated by paper-presenter for beamer-skill `create` workflow.\n")
    output.append(f"> Language: {lang_label} | Style: {style}\n")
    output.append("")

    # --- Section 1: Paper Metadata ---
    output.append("## 1. Paper Metadata\n")
    if paper_meta:
        output.append(f"- **Title**: {paper_meta.get('title', 'N/A')}")
        authors = paper_meta.get("authors", [])
        if authors:
            output.append(f"- **Authors**: {', '.join(authors[:5])}")
            if len(authors) > 5:
                output.append(f"  - ... and {len(authors) - 5} more")
        output.append(f"- **Year**: {paper_meta.get('year', 'N/A')}")
        output.append(f"- **Venue**: {paper_meta.get('venue', 'N/A')}")
        if paper_meta.get("arxiv_id"):
            output.append(f"- **arXiv**: [{paper_meta['arxiv_id']}](https://arxiv.org/abs/{paper_meta['arxiv_id']})")
        if paper_meta.get("citation_count"):
            output.append(f"- **Citations**: {paper_meta['citation_count']}")
    output.append("")

    # --- Section 2: Paper Structure Overview ---
    output.append("## 2. Paper Structure\n")
    output.append(f"- Estimated length: ~{paper_structure['estimated_pages']} pages")
    output.append(f"- Sections: {len(paper_structure['sections'])}")
    output.append(f"- Significant formulas: {len(paper_structure['formulas'])}")
    output.append(f"- Figures: {len(parsed_content['images'])}")
    output.append("")

    output.append("### Section Outline\n")
    for i, sec in enumerate(paper_structure["sections"], 1):
        level_indent = "  " * (sec["level"] - 1)
        # Truncate content for preview
        preview = sec["content"][:150].replace("\n", " ").strip()
        if len(sec["content"]) > 150:
            preview += "..."
        formula_count = len(sec.get("formulas", []))
        fig_count = len(sec.get("figures", []))
        extras = []
        if formula_count:
            extras.append(f"📐 {formula_count} formulas")
        if fig_count:
            extras.append(f"🖼️ {fig_count} figures")
        extra_str = f" [{', '.join(extras)}]" if extras else ""

        output.append(f"{level_indent}{i}. **{sec['title']}**{extra_str}")
        if preview:
            output.append(f"{level_indent}   > {preview}")
    output.append("")

    # --- Section 3: Key Figures ---
    if parsed_content["images"]:
        output.append("## 3. Available Figures\n")
        output.append("These figures were extracted from the paper by MinerU and can be directly")
        output.append("included in slides using `\\includegraphics`.\n")
        for i, img in enumerate(parsed_content["images"], 1):
            output.append(f"{i}. `{img['name']}` ({img['size_kb']:.0f} KB)")
            output.append(f"   - Path: `{img['path']}`")
            if img['size_kb'] > 50:
                output.append(f"   - ⭐ Large figure — likely a key result/diagram")
        output.append("")

        # Highlight large figures (likely key results)
        large_figs = [img for img in parsed_content["images"] if img["size_kb"] > 50]
        if large_figs:
            output.append("### Key Figures (large, likely important)\n")
            for img in sorted(large_figs, key=lambda x: -x["size_kb"]):
                output.append(f"- `{img['name']}` ({img['size_kb']:.0f} KB)")
            output.append("")

    # --- Section 4: Key Formulas ---
    if paper_structure["formulas"]:
        output.append("## 4. Key Mathematical Formulas\n")
        output.append("These formulas were extracted from the paper and should be included in slides.\n")
        for i, formula in enumerate(paper_structure["formulas"][:20], 1):
            # Clean up formula display
            clean = formula.replace("\n", " ").strip()
            if len(clean) > 200:
                clean = clean[:200] + "..."
            output.append(f"{i}. `{clean}`")
        if len(paper_structure["formulas"]) > 20:
            output.append(f"\n... and {len(paper_structure['formulas']) - 20} more formulas")
        output.append("")

    # --- Section 5: Code Analysis ---
    if code_info.get("available"):
        output.append("## 5. Source Code Analysis\n")
        output.append(f"- **Repository**: {code_info['repo_name']}")
        output.append(f"- **Total files**: {len(code_info['files'])}")

        if code_info.get("model_files"):
            output.append(f"\n### Model Architecture Files")
            for f in code_info["model_files"][:10]:
                output.append(f"- `{f}`")

        if code_info.get("training_files"):
            output.append(f"\n### Training Pipeline Files")
            for f in code_info["training_files"][:10]:
                output.append(f"- `{f}`")

        if code_info.get("dependencies"):
            output.append(f"\n### Dependencies")
            for dep in code_info["dependencies"]:
                output.append(f"- `{dep['file']}`:")
                # Show first few lines
                lines = dep["content"].strip().split("\n")[:10]
                for line in lines:
                    output.append(f"  - {line}")

        if code_info.get("readme_summary"):
            output.append(f"\n### README Summary")
            readme_preview = code_info["readme_summary"][:500]
            output.append(f"```\n{readme_preview}\n```")

        output.append("")

    # --- Section 6: Code-Theory Alignment ---
    if alignments:
        output.append("## 6. Code-Theory Alignment\n")
        output.append("Mapping between paper sections and source code implementation.\n")
        output.append("| Paper Section | Code File(s) | Notes |")
        output.append("|--------------|-------------|-------|")
        for a in alignments:
            output.append(f"| {a['paper_section']} | `{a['code_file']}` | {a['note']} |")
        output.append("")

        output.append("### Suggested Comparison Slides\n")
        output.append("For the reproduction presentation, consider creating comparison slides that show:\n")
        for a in alignments[:5]:
            output.append(f"- **{a['paper_section']}**: Paper formula/algorithm ↔ Code implementation in `{a['code_file']}`")
        output.append("")

    # --- Section 7: Suggested Slide Structure ---
    output.append("## 7. Suggested Slide Structure\n")

    if style == "overview":
        output.append(_generate_overview_structure(paper_structure, code_info, parsed_content))
    elif style == "deep-dive":
        output.append(_generate_deepdive_structure(paper_structure, code_info, parsed_content))
    elif style == "reproduction-report":
        output.append(_generate_reproduction_structure(paper_structure, code_info, parsed_content, alignments))
    else:
        output.append(_generate_overview_structure(paper_structure, code_info, parsed_content))

    # --- Section 8: beamer-skill Instructions ---
    output.append("\n## 8. Instructions for beamer-skill\n")
    output.append("Use this material package with the beamer-skill `create` workflow:\n")
    output.append("```")
    output.append("1. Read this materials file (Phase 0)")
    output.append("2. Conduct needs interview with user (Phase 1)")
    output.append("3. Build structure plan based on Section 7 above (Phase 2)")
    output.append("4. Draft slides using content from Sections 2-6 (Phase 3)")
    output.append("5. Include extracted figures from Section 3 (Phase 4)")
    output.append("6. Quality loop (Phase 5)")
    output.append("```\n")
    output.append("### Key directives for the AI agent:\n")
    output.append("- **Use extracted figures directly** — copy images from the parsed directory to the presentation folder")
    output.append("- **Include paper formulas** — use the exact LaTeX formulas from Section 4")
    output.append("- **Cite the original paper** — add to references slide")
    if code_info.get("available"):
        output.append("- **Show code snippets** — include relevant code from the source repository")
        output.append("- **Create comparison slides** — paper formula on left, code on right")
        output.append("- **Highlight implementation details** — what's in the code but not in the paper")
    output.append("")

    return "\n".join(output)


def _generate_overview_structure(paper: dict, code: dict, content: dict) -> str:
    """Generate a standard paper overview slide structure."""
    lines = []
    lines.append("### Standard Paper Overview (~15-20 slides)\n")
    lines.append("1. **Title slide** (1 slide)")
    lines.append("2. **Motivation & Problem** (2-3 slides) — Why does this paper exist?")
    lines.append("3. **Background & Related Work** (2-3 slides) — What came before?")
    lines.append("4. **Method / Approach** (4-6 slides) — Core contribution")
    lines.append("   - Architecture diagram (use extracted figures)")
    lines.append("   - Key formulas")
    lines.append("   - Algorithm overview")
    lines.append("5. **Experiments & Results** (3-4 slides)")
    lines.append("   - Setup (dataset, metrics, baselines)")
    lines.append("   - Main results table")
    lines.append("   - Key comparisons (use extracted figures)")
    lines.append("6. **Analysis & Discussion** (1-2 slides)")
    lines.append("7. **Conclusion & Future Work** (1 slide)")
    lines.append("8. **References** (1 slide)")
    lines.append("9. **Thank You** (1 slide)")
    lines.append("10. **Backup slides** (3-5 slides)")
    return "\n".join(lines)


def _generate_deepdive_structure(paper: dict, code: dict, content: dict) -> str:
    """Generate a deep-dive technical talk structure."""
    lines = []
    lines.append("### Deep-Dive Technical Talk (~30-40 slides)\n")
    lines.append("1. **Title + Outline** (2 slides)")
    lines.append("2. **Problem Setup** (3-4 slides) — Formal problem definition")
    lines.append("3. **Background Theory** (4-5 slides) — Prerequisites")
    lines.append("4. **Core Method** (8-12 slides) — Full technical details")
    lines.append("   - Step-by-step derivations")
    lines.append("   - All key formulas with worked examples")
    lines.append("   - Architecture diagrams")
    lines.append("5. **Theoretical Analysis** (3-4 slides) — Proofs, complexity, guarantees")
    lines.append("6. **Experimental Setup** (2-3 slides)")
    lines.append("7. **Results & Ablations** (4-6 slides)")
    lines.append("8. **Limitations & Future Work** (2 slides)")
    lines.append("9. **References** (1 slide)")
    lines.append("10. **Thank You** (1 slide)")
    lines.append("11. **Backup slides** (5-8 slides)")
    return "\n".join(lines)


def _generate_reproduction_structure(paper: dict, code: dict, content: dict, alignments: list) -> str:
    """Generate a reproduction report structure with code-theory comparison."""
    lines = []
    lines.append("### 🔬 Reproduction Report (~20-30 slides)\n")
    lines.append("1. **Title slide** (1 slide) — Paper title + \"Reproduction Report\"")
    lines.append("2. **Paper Overview** (2-3 slides) — Quick summary of the paper")
    lines.append("   - Core contribution")
    lines.append("   - Key results claimed")
    lines.append("3. **Method Summary** (3-4 slides) — Paper's approach")
    lines.append("   - Key formulas from the paper")
    lines.append("   - Architecture diagram (use extracted figures)")
    lines.append("4. **Code Architecture** (2-3 slides) — How the code implements the paper")
    lines.append("   - Repository structure")
    lines.append("   - Key files and their roles")

    if alignments:
        lines.append("5. **Paper ↔ Code Comparison** (4-6 slides) — Side-by-side analysis")
        for a in alignments[:4]:
            lines.append(f"   - {a['paper_section']}: paper formula ↔ `{a['code_file']}`")
    else:
        lines.append("5. **Implementation Details** (3-4 slides)")

    lines.append("6. **Reproduction Setup** (2-3 slides)")
    lines.append("   - Environment, hardware, hyperparameters")
    lines.append("   - Differences from paper's setup (if any)")
    lines.append("7. **Results Comparison** (3-5 slides)")
    lines.append("   - Original results (from paper figures)")
    lines.append("   - Reproduced results")
    lines.append("   - Delta analysis — what matches, what doesn't")
    lines.append("8. **Challenges & Findings** (2 slides)")
    lines.append("   - Undocumented tricks / missing details")
    lines.append("   - Bugs found / deviations from paper")
    lines.append("9. **Conclusion** (1 slide)")
    lines.append("10. **References** (1 slide)")
    lines.append("11. **Thank You** (1 slide)")
    lines.append("12. **Backup** (3-5 slides) — full training curves, extra ablations")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------
def prepare_presentation(
    parsed_dir: str,
    code_dir: str | None = None,
    output_path: str = "presentation_materials.md",
    style: str = "overview",
    language: str = "en",
    paper_info_path: str | None = None,
) -> dict:
    """Main entry point."""
    print("  [log] === Paper Presenter started ===")

    # Load paper metadata
    paper_meta = {}
    if paper_info_path and os.path.exists(paper_info_path):
        with open(paper_info_path, "r", encoding="utf-8") as f:
            info = json.load(f)
            paper_meta = info.get("paper", {})
        print(f"  [log] Loaded paper metadata: {paper_meta.get('title', 'N/A')}")
    else:
        # Try to find paper_info.json in parent directories
        for parent in [Path(parsed_dir).parent, Path(parsed_dir).parent.parent]:
            for name in ["paper_info.json"]:
                p = parent / "paper" / name
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        info = json.load(f)
                        paper_meta = info.get("paper", {})
                    print(f"  [log] Found paper_info.json at {p}")
                    break

    # Step 1: Load parsed content
    parsed = load_parsed_content(parsed_dir)
    if not parsed["markdown"]:
        return {"success": False, "error": "No markdown content found in parsed directory"}

    # Step 2: Analyze paper structure
    structure = analyze_paper_structure(parsed["markdown"])

    # Step 3: Analyze source code (if provided)
    code_info = analyze_source_code(code_dir) if code_dir else {"available": False}

    # Step 4: Code-theory alignment
    alignments = analyze_code_theory_alignment(structure["sections"], code_info)

    # Step 5: Generate materials
    materials = generate_materials(
        parsed, structure, code_info, alignments, paper_meta, style, language
    )

    # Step 6: Save output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(materials)

    print(f"\n  [log] Materials saved to: {output_path}")
    print(f"  [log] === Preparation complete ===")

    return {
        "success": True,
        "output_path": output_path,
        "paper_title": paper_meta.get("title", "Unknown"),
        "sections": len(structure["sections"]),
        "figures": len(parsed["images"]),
        "formulas": len(structure["formulas"]),
        "code_available": code_info.get("available", False),
        "alignments": len(alignments),
        "style": style,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Prepare structured materials for Beamer presentation from parsed paper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("parsed_dir", help="Path to MinerU parsed output directory")
    parser.add_argument(
        "--code-dir", "-c",
        default=None,
        help="Path to source code repository (optional)"
    )
    parser.add_argument(
        "--output", "-o",
        default="presentation_materials.md",
        help="Output materials file path"
    )
    parser.add_argument(
        "--style", "-s",
        default="overview",
        choices=["overview", "deep-dive", "reproduction-report"],
        help="Presentation style (default: overview)"
    )
    parser.add_argument(
        "--language", "-l",
        default="en",
        choices=["en", "zh"],
        help="Output language (default: en)"
    )
    parser.add_argument(
        "--paper-info", "-p",
        default=None,
        help="Path to paper_info.json for metadata"
    )

    args = parser.parse_args()

    result = prepare_presentation(
        parsed_dir=args.parsed_dir,
        code_dir=args.code_dir,
        output_path=args.output,
        style=args.style,
        language=args.language,
        paper_info_path=args.paper_info,
    )

    print()
    if result["success"]:
        print(f"✅ Materials prepared!")
        print(f"📄 Output: {result['output_path']}")
        print(f"📊 Sections: {result['sections']} | Figures: {result['figures']} | Formulas: {result['formulas']}")
        if result["code_available"]:
            print(f"💻 Code analysis: {result['alignments']} alignment points")
        print(f"🎨 Style: {result['style']}")
        print(f"\n🎯 Next step: Use beamer-skill `create` with this materials file")
    else:
        print(f"❌ Failed: {result.get('error', 'unknown')}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
