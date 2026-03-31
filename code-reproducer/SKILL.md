---
name: code-reproducer
description: Automated code reproduction on remote GPU servers via SSH — upload, setup, train, monitor, download.
---

# Code Reproducer Skill

## Purpose
Automate the full reproduction pipeline on remote GPU servers: SSH connect → upload code → setup environment → run training → periodic monitoring → download results. This is the fifth step in the research reproduction pipeline.

## When to Use
- After downloading source code with paper-downloader
- User asks to "reproduce", "train", "run on GPU", or "replicate experiments"
- User wants to execute code on a remote server

## First-Time Setup (MANDATORY — ask user these questions)

Before running, you MUST collect server information from the user. Ask these questions:

### Required Questions:
1. **SSH Host**: "What is your GPU server's IP address or hostname?"
2. **SSH Port**: "What port does SSH use? (default: 22)"
3. **SSH Username**: "What is your SSH login username?"
4. **Authentication**: "Do you use SSH key or password authentication?"
   - If key: "Where is your SSH key file? (default: ~/.ssh/id_rsa)"
   - If password: "Please provide your SSH password"
5. **Jump Host**: "Does your server require a bastion/jump host? If so, what's the address?"

### Environment Questions:
6. **Environment Manager**: "How do you manage Python environments on the server?"
   - conda (most common for ML)
   - venv
   - docker
   - none (system Python)
7. **CUDA Version**: "What CUDA version is installed? (leave blank for auto-detect)"
8. **Remote Workspace**: "Where should I put code on the server? (default: ~/reproduce)"

### Running the Setup:
```bash
python skills/code-reproducer/reproduce.py --setup --config workspace/<paper>/server_config.json
```

Or create the config programmatically from user answers:
```python
config = {
    "host": "user_answer_host",
    "port": 22,
    "user": "user_answer_username",
    "key_file": "~/.ssh/id_rsa",  # or "password": "xxx"
    "env_manager": "conda",       # conda | venv | docker | none
    "conda_path": "conda",
    "remote_workspace": "~/reproduce"
}
# Save to server_config.json
```

## How to Use

### Step 1: Setup Configuration
Either run `--setup` interactively or create `server_config.json` from user answers.

### Step 2: Run Reproduction
```bash
python skills/code-reproducer/reproduce.py workspace/<paper>/code/<repo>/ \
    --config workspace/<paper>/server_config.json \
    --output-dir workspace/<paper>/results/
```

**Options:**
- `--run-script train.py` — Specify the training script (auto-detected if not set)
- `--run-args "--epochs 100 --batch-size 32"` — Extra training arguments
- `--monitor-interval 60` — Check training every N seconds (default: 60)
- `--timeout 24` — Kill training after N hours (default: 24)
- `--no-download` — Skip downloading results
- `--remote-dir /path/on/server` — Override remote directory

### Step 3: Monitor Training
The skill automatically:
1. Starts training in background (nohup)
2. Checks the log file every `--monitor-interval` seconds
3. Reports latest output at each check
4. Detects when training completes or fails
5. Can kill the process if timeout is exceeded

**For long training runs**, the agent should:
- Start the training command
- Sleep for a reasonable interval (e.g., 30-60 minutes for typical ML training)
- Wake up and check the training log
- Repeat until done or timeout

### Step 4: Download Results
After training, the skill downloads:
- `output/`, `results/`, `checkpoints/`, `logs/`, `figures/` directories
- Any `.log`, `.csv`, `.json`, `.png`, `.jpg`, `.pdf` files
- Model checkpoints (`.pt`, `.pth`, `.ckpt`)
- Full training log

### Step 5: Report to User
Tell the user:
- Training duration
- Final accuracy/loss from logs
- Files downloaded
- Any errors encountered
- Where results are saved locally

## Auto-Detection

The script auto-detects:
- **Training script**: looks for `train.py`, `main.py`, `run.py` etc.
- **GPU info**: runs `nvidia-smi` on the server
- **CUDA version**: runs `nvcc --version`
- **Dependencies**: installs from `requirements.txt`, `environment.yml`, or `setup.py`

## Error Handling
- If SSH connection fails: check host/port/credentials, ask user to verify
- If training script not found: ask user to specify with `--run-script`
- If environment setup fails: show error logs, suggest manual setup
- If training fails: show last 50 lines of training log
- If timeout: kill process, download partial results

## Dependencies
- Python 3.10+
- No Python packages required (uses system `ssh`/`scp`/`rsync` commands)
- Requires: OpenSSH client installed on the local machine
- Requires: SSH access to a remote GPU server

## Pipeline Integration
```
paper-downloader output → code-reproducer → result-analyzer
   (source code)           (train on GPU)    (compare results)
```
