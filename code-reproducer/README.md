# 🖥️ Code Reproducer

Analyze source code repositories and automate paper reproduction on remote GPU servers.

**Architecture**: This skill provides the **intelligence layer** (code analysis, reproduction planning).
SSH operations are handled by **[mcp-ssh](https://github.com/shuakami/mcp-ssh)**.

## 🚀 Quick Start

```bash
# Step 1: Analyze the repository (local)
python analyze_repo.py path/to/code/

# Step 2: Use mcp-ssh to connect to GPU server
# Step 3: Follow the reproduction plan
```

## 🏗️ Architecture

```
┌──────────────────────────────┐      ┌────────────────────┐
│     code-reproducer          │      │     mcp-ssh        │
│                              │      │  (MCP SSH tool)    │
│  analyze_repo.py             │      │                    │
│  ├── Framework detection     │ ───▶ │  SSH connect       │
│  ├── Training script finder  │      │  Command execution │
│  ├── Config extraction       │      │  File transfer     │
│  ├── Dependency analysis     │      │  tmux sessions     │
│  └── Reproduction plan       │      │  (persistent)      │
└──────────────────────────────┘      └────────────────────┘
```

## 🔍 analyze_repo.py

Scans a cloned repository and produces a structured reproduction plan.

```bash
python analyze_repo.py workspace/code/repo/ -o analysis.json
```

### What It Detects

| Feature | How |
|---------|-----|
| **Framework** | Import scanning + dependency file analysis (PyTorch, TF, JAX, HF) |
| **Training scripts** | Pattern matching (`train.py`, `main.py`) + content analysis |
| **Hyperparameters** | Regex extraction from config files (lr, batch_size, epochs) |
| **Dependencies** | `requirements.txt`, `environment.yml`, `setup.py`, Dockerfile |
| **README commands** | Parses code blocks for install/train/eval commands |

### Output Example

```json
{
  "framework": {"primary": "pytorch"},
  "training_scripts": [
    {"path": "scripts/run_cifar.py", "confidence": "high"}
  ],
  "reproduction_plan": [
    {"step": 1, "name": "Environment Setup", "commands": [...]},
    {"step": 2, "name": "Training", "commands": ["python scripts/run_cifar.py"]},
    {"step": 3, "name": "Collect Results", "commands": [...]}
  ]
}
```

## 📋 Full Reproduction Workflow

1. **Analyze** (local) → `analyze_repo.py` → understand the code
2. **Connect** (mcp-ssh) → SSH to GPU server
3. **Upload** (mcp-ssh) → Transfer code to server
4. **Setup** (mcp-ssh + tmux) → Install dependencies, verify GPU
5. **Train** (mcp-ssh + tmux) → Run training in persistent session
6. **Monitor** (mcp-ssh) → Periodically check logs
7. **Download** (mcp-ssh) → Get results back to local
8. **Compare** → Pass to result-analyzer

## ⚡ Prerequisites

- **mcp-ssh**: https://github.com/shuakami/mcp-ssh (for SSH operations)
- Python 3.10+ (for `analyze_repo.py`, no external deps)

## 📄 License

MIT — see [LICENSE](../LICENSE)
