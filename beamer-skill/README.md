# 🎓 Beamer Skill

> **This is a bundled copy of [Noi1r/beamer-skill](https://github.com/Noi1r/beamer-skill), included for convenience.**
>
> Original author: **Noi1r** · License: **MIT** · [Original repository](https://github.com/Noi1r/beamer-skill)

A Claude Code / AI Agent skill for creating, compiling, reviewing, and polishing academic Beamer LaTeX presentations. Full lifecycle workflow with quality scoring, pedagogical review, TikZ audit, and more.

## 📦 Why It's Bundled Here

The `paper-presenter` skill in this monorepo generates structured materials from parsed papers, which feed directly into beamer-skill's `create` workflow. Bundling beamer-skill here enables **one-click installation** of the entire pipeline.

## 🔗 Integration with Research Pipeline

```
paper-finder → paper-downloader → paper-parser → paper-presenter → beamer-skill
                                                        │                  │
                                                        └── materials.md ──┘
```

### Usage with paper-presenter

```bash
# 1. Generate materials from parsed paper
python paper-presenter/prepare_presentation.py workspace/parsed/ \
    --code-dir workspace/code/repo/ \
    --style reproduction-report \
    -o workspace/presentation_materials.md

# 2. Point your AI agent to the materials + beamer-skill
#    "Create a beamer presentation based on workspace/presentation_materials.md"
#    The agent reads beamer-skill/beamer/SKILL.md for workflow rules
```

## 📖 Installation

To use beamer-skill with Claude Code, symlink or copy `beamer/` to your project's skill directory:

```bash
# Option A: Symlink (recommended)
ln -s /path/to/research-skills/beamer-skill/beamer .gemini/skills/beamer

# Option B: Copy
cp -r /path/to/research-skills/beamer-skill/beamer .gemini/skills/beamer
```

## 📄 License & Attribution

This directory contains a copy of [beamer-skill](https://github.com/Noi1r/beamer-skill) by **Noi1r**, distributed under the **MIT License**.

- Original license: [LICENSE-UPSTREAM](./LICENSE-UPSTREAM)
- Original README: [README-UPSTREAM.md](./README-UPSTREAM.md)
- Original repository: https://github.com/Noi1r/beamer-skill

The MIT License requires that the original copyright notice and permission notice be included in all copies or substantial portions of the Software. The `LICENSE-UPSTREAM` file fulfills this requirement.

## 📚 Documentation

For full beamer-skill documentation, see:
- [SKILL.md](./beamer/SKILL.md) — Complete skill instructions for Claude Code
- [AGENTS.md](./beamer/AGENTS.md) — Shorter version for OpenAI Codex
- [README-UPSTREAM.md](./README-UPSTREAM.md) — Original project README
