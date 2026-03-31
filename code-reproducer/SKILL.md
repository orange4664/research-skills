---
name: code-reproducer
description: Analyze source code repos and automate paper reproduction on remote GPU servers via mcp-ssh.
---

# Code Reproducer Skill

## Purpose
Automate the full reproduction of a research paper's experiments on remote GPU servers. This skill handles the **intelligence layer** (analyzing code, generating setup commands, monitoring training) while delegating SSH operations to **mcp-ssh** (MCP protocol SSH tool).

## Architecture
```
code-reproducer (this skill)         mcp-ssh (MCP tool)
  └── analyze_repo.py                 └── SSH connection
      ├── Framework detection              ├── Command execution
      ├── Training script detection        ├── File upload/download
      ├── Config extraction                ├── tmux session management
      └── Reproduction plan                └── Persistent sessions
```

## Prerequisites
- **mcp-ssh** must be installed and configured in the MCP client
  - Install: `git clone https://github.com/shuakami/mcp-ssh.git && cd mcp-ssh && npm install && npm run build`
  - Config: Add to your MCP config (Cursor/Claude Desktop `mcp.json`)
  - Docs: https://github.com/shuakami/mcp-ssh

## When to Use
- After paper-downloader has cloned source code
- User asks to "reproduce", "train", "run experiments", or "replicate results"
- User wants to execute code on a remote GPU server

## Workflow

### Phase 1: Analyze Repository (LOCAL)

Run `analyze_repo.py` to understand the codebase:
```bash
python skills/code-reproducer/analyze_repo.py workspace/<paper>/code/<repo>/ -o workspace/<paper>/repo_analysis.json
```

This produces a JSON report containing:
- **Framework**: PyTorch, TensorFlow, JAX, etc.
- **Training scripts**: Ranked by confidence
- **Configs**: Hyperparameters extracted
- **Dependencies**: packages, CUDA requirements
- **README instructions**: Install/train/eval commands parsed
- **Reproduction plan**: Step-by-step commands

### Phase 2: Setup Server (via mcp-ssh)

**First-time setup — ask the user these questions:**
1. "What is your GPU server's SSH address and port?"
2. "What is your username?"
3. "Do you use SSH key or password authentication?"
4. "Does your server need a jump/bastion host?"

**Then use mcp-ssh to:**
1. Create SSH connection: ask mcp-ssh to connect to the server
2. Test connection: run `echo "Connected"` and `nvidia-smi`
3. Create a tmux session for persistence: `tmux new-session -d -s repro`

### Phase 3: Upload Code (via mcp-ssh)

1. Create remote workspace: `mkdir -p ~/reproduce/<project>`
2. Upload code via mcp-ssh file upload tool
3. Verify: `ls -la ~/reproduce/<project>/`

### Phase 4: Setup Environment (via mcp-ssh)

Based on `repo_analysis.json`, execute the appropriate commands IN the tmux session:

**For conda + requirements.txt:**
```bash
tmux send-keys -t repro "conda create -n repro_<project> python=3.10 -y" Enter
# Wait for completion, then:
tmux send-keys -t repro "conda activate repro_<project>" Enter
tmux send-keys -t repro "cd ~/reproduce/<project> && pip install -r requirements.txt" Enter
```

**For environment.yml:**
```bash
tmux send-keys -t repro "conda env create -f ~/reproduce/<project>/environment.yml -n repro_<project>" Enter
```

**For Docker:**
```bash
tmux send-keys -t repro "cd ~/reproduce/<project> && docker build -t repro ." Enter
```

**After setup, verify:**
```bash
# For PyTorch
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPUs: {torch.cuda.device_count()}')"

# For TensorFlow
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

### Phase 5: Run Training (via mcp-ssh + tmux)

> [!IMPORTANT]
> **Always use tmux** for training. This ensures the training continues even if the SSH session drops.

1. Start training in the tmux session:
```bash
tmux send-keys -t repro "cd ~/reproduce/<project>" Enter
tmux send-keys -t repro "python <training_script> <args> 2>&1 | tee training.log" Enter
```

2. The training command comes from `repo_analysis.json`:
   - First priority: README training commands
   - Second: detected training scripts
   - Third: ask the user

### Phase 6: Monitor Training (periodic)

> [!TIP]
> **For long training runs**: After starting training, wait/sleep for a reasonable interval (e.g., 10-30 minutes for quick tests, 1-2 hours for full training), then check progress.

**Check progress via mcp-ssh:**
```bash
# Get latest log lines
tmux capture-pane -t repro -p | tail -20

# Or check the log file
tail -20 ~/reproduce/<project>/training.log

# Check if process is still running
ps aux | grep python | grep train

# Check GPU usage
nvidia-smi
```

**What to look for:**
- Loss decreasing → training is working
- OOM errors → reduce batch size
- CUDA errors → check CUDA version compatibility
- NaN loss → check learning rate, data preprocessing
- Import errors → missing dependency, install it

**Error recovery:** If training fails:
1. Read the error message
2. Diagnose and fix (install missing package, adjust hyperparameters)
3. Restart in the same tmux session

### Phase 7: Download Results (via mcp-ssh)

After training completes:
1. Check what was generated:
```bash
find ~/reproduce/<project> -name "*.pt" -o -name "*.pth" -o -name "*.ckpt" -o -name "*.png" -o -name "*.csv" -o -name "*.log" | head -30
```

2. Download result files via mcp-ssh to local:
   - Model checkpoints
   - Training logs
   - Generated images/figures
   - Evaluation metrics

3. Save to `workspace/<paper>/results/`

### Phase 8: Report to User

Tell the user:
- ✅ Training completed (or ❌ failed with reason)
- Duration
- Final metrics (loss, accuracy, FID, etc.)
- Files downloaded
- Next steps (run result-analyzer for comparison with paper)

## Helper Script

### analyze_repo.py

Analyzes a source code repository to understand how to reproduce it.

**Input**: Path to code directory
**Output**: JSON report with:
- `framework`: Detected ML framework and confidence scores
- `training_scripts`: List of potential training scripts with confidence
- `configs`: Configuration files and extracted hyperparameters
- `dependencies`: Package list, CUDA requirements
- `readme`: Parsed installation and training commands
- `reproduction_plan`: Ordered steps with shell commands

**Usage:**
```bash
python analyze_repo.py <code_dir> [-o output.json]
```

## Dependencies
- Python 3.10+ (for analyze_repo.py)
- No Python packages required (stdlib only)
- **mcp-ssh** for SSH operations (https://github.com/shuakami/mcp-ssh)

## Common Pitfalls and Solutions

| Problem | Solution |
|---------|----------|
| CUDA version mismatch | Check `nvcc --version` and install matching PyTorch |
| OOM (Out of Memory) | Reduce batch size, enable gradient checkpointing |
| Missing data | Check README for dataset download instructions |
| Deprecated API calls | Check the paper's publication year, install matching lib versions |
| Training too slow | Verify GPU is being used: `nvidia-smi` during training |
| tmux session lost | `tmux ls` to list sessions, `tmux attach -t repro` to reattach |
| Permission denied | `chmod +x <script>` or check directory permissions |
