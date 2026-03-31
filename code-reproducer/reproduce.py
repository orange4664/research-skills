#!/usr/bin/env python3
"""
reproduce.py — Automated code reproduction on remote GPU servers via SSH.

Usage:
    python reproduce.py <code_dir> [options]

First-time setup:
    python reproduce.py --setup              # Interactive config generator

Options:
    --config <path>         Server config file (default: server_config.json)
    --run-script <path>     Custom training script to run (auto-detected if not set)
    --remote-dir <path>     Remote working directory (default: ~/reproduce/<project>)
    --monitor-interval <s>  Training check interval in seconds (default: 60)
    --timeout <hours>       Max training time in hours (default: 24)
    --download-results      Download results after training (default: true)
    --setup                 Run interactive config setup

Workflow:
    1. Connect to server via SSH
    2. Upload source code
    3. Setup environment (conda/pip)
    4. Run training script
    5. Monitor progress (periodic log checks)
    6. Download results (models, logs, figures)
"""

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MONITOR_INTERVAL = 60  # seconds
DEFAULT_TIMEOUT_HOURS = 24
CONFIG_FILENAME = "server_config.json"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class ReproLog:
    """Collects log entries."""

    def __init__(self):
        self.entries: list[str] = []

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.entries.append(entry)
        print(f"  {entry}")


# ---------------------------------------------------------------------------
# SSH Wrapper (uses system ssh/scp for zero-dependency)
# ---------------------------------------------------------------------------
class SSHClient:
    """Wrapper around system ssh/scp commands."""

    def __init__(self, config: dict, log: ReproLog):
        self.host = config["host"]
        self.port = config.get("port", 22)
        self.user = config["user"]
        self.key_file = config.get("key_file")
        self.password = config.get("password")
        self.jump_host = config.get("jump_host")
        self.log = log

        # Build common SSH args
        self.ssh_args = self._build_ssh_args()

    def _build_ssh_args(self) -> list[str]:
        """Build common SSH arguments."""
        args = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=30"]
        if self.port != 22:
            args.extend(["-p", str(self.port)])
        if self.key_file:
            args.extend(["-i", self.key_file])
        if self.jump_host:
            args.extend(["-J", self.jump_host])
        return args

    def test_connection(self) -> bool:
        """Test SSH connection."""
        self.log.log(f"Testing SSH connection to {self.user}@{self.host}:{self.port}")
        try:
            result = self.run_command("echo 'SSH_OK'", timeout=15)
            if result and "SSH_OK" in result:
                self.log.log("SSH connection successful ✅")
                return True
            else:
                self.log.log("SSH connection failed ❌")
                return False
        except Exception as e:
            self.log.log(f"SSH connection error: {e}")
            return False

    def run_command(self, command: str, timeout: int = 300) -> str | None:
        """Run a command on the remote server."""
        cmd = ["ssh"] + self.ssh_args + [f"{self.user}@{self.host}", command]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode != 0 and result.stderr.strip():
                self.log.log(f"SSH stderr: {result.stderr.strip()[:200]}")
            return result.stdout
        except subprocess.TimeoutExpired:
            self.log.log(f"Command timed out ({timeout}s): {command[:80]}")
            return None
        except FileNotFoundError:
            self.log.log("Error: 'ssh' command not found. Please install OpenSSH.")
            return None

    def run_command_background(self, command: str, log_file: str) -> bool:
        """Run a command in the background on the remote server, output to log file."""
        bg_cmd = f"nohup bash -c '{command}' > {log_file} 2>&1 & echo $!"
        result = self.run_command(bg_cmd)
        if result:
            pid = result.strip()
            self.log.log(f"Background process started, PID: {pid}")
            return True
        return False

    def upload_dir(self, local_dir: str, remote_dir: str) -> bool:
        """Upload a local directory to the remote server using scp/rsync."""
        self.log.log(f"Uploading {local_dir} → {self.user}@{self.host}:{remote_dir}")

        # Try rsync first (faster for subsequent syncs)
        rsync_args = [
            "rsync", "-avz", "--progress",
            "-e", f"ssh {' '.join(self.ssh_args)}",
            f"{local_dir}/",
            f"{self.user}@{self.host}:{remote_dir}/"
        ]
        try:
            result = subprocess.run(rsync_args, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                self.log.log("Upload complete (rsync)")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback to scp
        scp_args = ["scp", "-r"]
        if self.port != 22:
            scp_args.extend(["-P", str(self.port)])
        if self.key_file:
            scp_args.extend(["-i", self.key_file])
        scp_args.extend([
            "-o", "StrictHostKeyChecking=no",
            local_dir,
            f"{self.user}@{self.host}:{remote_dir}"
        ])
        try:
            result = subprocess.run(scp_args, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                self.log.log("Upload complete (scp)")
                return True
            else:
                self.log.log(f"Upload failed: {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            self.log.log("Upload timed out (>10 min)")
            return False
        except FileNotFoundError:
            self.log.log("Error: 'scp' not found. Please install OpenSSH.")
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from the remote server."""
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        scp_args = ["scp"]
        if self.port != 22:
            scp_args.extend(["-P", str(self.port)])
        if self.key_file:
            scp_args.extend(["-i", self.key_file])
        scp_args.extend([
            "-o", "StrictHostKeyChecking=no",
            f"{self.user}@{self.host}:{remote_path}",
            local_path
        ])
        try:
            result = subprocess.run(scp_args, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def download_dir(self, remote_dir: str, local_dir: str) -> bool:
        """Download a remote directory."""
        os.makedirs(local_dir, exist_ok=True)
        scp_args = ["scp", "-r"]
        if self.port != 22:
            scp_args.extend(["-P", str(self.port)])
        if self.key_file:
            scp_args.extend(["-i", self.key_file])
        scp_args.extend([
            "-o", "StrictHostKeyChecking=no",
            f"{self.user}@{self.host}:{remote_dir}",
            local_dir
        ])
        try:
            result = subprocess.run(scp_args, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                self.log.log(f"Download complete → {local_dir}")
                return True
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


# ---------------------------------------------------------------------------
# Interactive Setup
# ---------------------------------------------------------------------------
def interactive_setup(config_path: str) -> dict:
    """Run interactive setup to collect server configuration."""
    print("\n🖥️  Code Reproducer — Server Setup\n")
    print("This will create a configuration file for your GPU server.\n")

    config = {}

    # Basic connection
    config["host"] = input("SSH Host (IP or hostname): ").strip()
    port = input("SSH Port [22]: ").strip()
    config["port"] = int(port) if port else 22
    config["user"] = input("SSH Username: ").strip()

    # Authentication
    print("\nAuthentication method:")
    print("  1. SSH Key (recommended)")
    print("  2. Password")
    auth = input("Choice [1]: ").strip() or "1"
    if auth == "1":
        default_key = os.path.expanduser("~/.ssh/id_rsa")
        key = input(f"SSH Key path [{default_key}]: ").strip() or default_key
        config["key_file"] = key
    else:
        config["password"] = getpass.getpass("SSH Password: ")

    # Jump host
    jump = input("Jump/Bastion host (leave empty if none): ").strip()
    if jump:
        config["jump_host"] = jump

    # Environment
    print("\nServer environment:")
    print("  1. conda")
    print("  2. venv")
    print("  3. docker")
    print("  4. none (system Python)")
    env = input("Environment manager [1]: ").strip() or "1"
    env_map = {"1": "conda", "2": "venv", "3": "docker", "4": "none"}
    config["env_manager"] = env_map.get(env, "conda")

    if config["env_manager"] == "conda":
        conda_path = input("Conda executable path [conda]: ").strip() or "conda"
        config["conda_path"] = conda_path

    # CUDA
    cuda = input("CUDA version (e.g., 11.8, 12.1) [auto-detect]: ").strip()
    if cuda:
        config["cuda_version"] = cuda

    # GPU
    gpu = input("Number of GPUs [auto-detect]: ").strip()
    if gpu:
        config["num_gpus"] = int(gpu)

    # Remote workspace
    workspace = input("Remote workspace directory [~/reproduce]: ").strip()
    config["remote_workspace"] = workspace or "~/reproduce"

    # Save
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"\n✅ Config saved to: {config_path}")
    print("   You can edit this file manually if needed.\n")

    return config


# ---------------------------------------------------------------------------
# Environment Setup
# ---------------------------------------------------------------------------
def setup_environment(
    ssh: SSHClient,
    remote_dir: str,
    env_name: str,
    config: dict,
    log: ReproLog,
) -> bool:
    """Set up Python environment on remote server."""
    env_manager = config.get("env_manager", "conda")
    conda = config.get("conda_path", "conda")

    log.log(f"Setting up environment: {env_manager}")

    if env_manager == "conda":
        # Check if env already exists
        result = ssh.run_command(f"{conda} env list")
        if result and env_name in result:
            log.log(f"Conda env '{env_name}' already exists")
        else:
            # Check for environment.yml
            check = ssh.run_command(f"test -f {remote_dir}/environment.yml && echo YES")
            if check and "YES" in check:
                log.log("Found environment.yml, creating conda env from it...")
                ssh.run_command(
                    f"cd {remote_dir} && {conda} env create -f environment.yml -n {env_name} -y",
                    timeout=600,
                )
            else:
                # Create env with Python 3.10
                log.log(f"Creating conda env '{env_name}' with Python 3.10...")
                ssh.run_command(
                    f"{conda} create -n {env_name} python=3.10 -y",
                    timeout=300,
                )

        # Install requirements
        check_req = ssh.run_command(f"test -f {remote_dir}/requirements.txt && echo YES")
        if check_req and "YES" in check_req:
            log.log("Installing requirements.txt...")
            ssh.run_command(
                f"{conda} run -n {env_name} pip install -r {remote_dir}/requirements.txt",
                timeout=600,
            )

        # Check for setup.py / pyproject.toml
        check_setup = ssh.run_command(
            f"test -f {remote_dir}/setup.py -o -f {remote_dir}/pyproject.toml && echo YES"
        )
        if check_setup and "YES" in check_setup:
            log.log("Installing package in development mode...")
            ssh.run_command(
                f"cd {remote_dir} && {conda} run -n {env_name} pip install -e .",
                timeout=300,
            )

    elif env_manager == "venv":
        venv_path = f"{remote_dir}/.venv"
        check = ssh.run_command(f"test -d {venv_path} && echo YES")
        if not (check and "YES" in check):
            log.log("Creating venv...")
            ssh.run_command(f"python3 -m venv {venv_path}", timeout=60)

        check_req = ssh.run_command(f"test -f {remote_dir}/requirements.txt && echo YES")
        if check_req and "YES" in check_req:
            log.log("Installing requirements.txt...")
            ssh.run_command(
                f"source {venv_path}/bin/activate && pip install -r {remote_dir}/requirements.txt",
                timeout=600,
            )

    elif env_manager == "docker":
        log.log("Docker mode: assuming container is pre-configured")
        check = ssh.run_command(f"test -f {remote_dir}/Dockerfile && echo YES")
        if check and "YES" in check:
            log.log("Dockerfile found — build manually if needed")

    log.log("Environment setup complete")
    return True


# ---------------------------------------------------------------------------
# Detect Training Script
# ---------------------------------------------------------------------------
def detect_training_script(ssh: SSHClient, remote_dir: str, log: ReproLog) -> str | None:
    """Auto-detect the main training script."""
    # Common training script patterns (ordered by priority)
    candidates = [
        "train.py", "main.py", "run.py", "run_train.py",
        "scripts/train.py", "scripts/run.py", "scripts/main.py",
        "src/train.py", "tools/train.py",
    ]

    for script in candidates:
        check = ssh.run_command(f"test -f {remote_dir}/{script} && echo YES")
        if check and "YES" in check:
            log.log(f"Detected training script: {script}")
            return script

    # Fallback: search for files with "train" in the name
    result = ssh.run_command(
        f"find {remote_dir} -maxdepth 3 -name '*train*.py' -not -path '*/.git/*' | head -5"
    )
    if result and result.strip():
        scripts = result.strip().split("\n")
        if scripts:
            rel = scripts[0].replace(f"{remote_dir}/", "")
            log.log(f"Found training script via search: {rel}")
            return rel

    # If nothing found, look for README instructions
    result = ssh.run_command(f"cat {remote_dir}/README.md 2>/dev/null | head -100")
    if result:
        # Look for "python" commands in README
        for line in result.split("\n"):
            m = re.search(r"python\s+(\S+\.py)", line)
            if m:
                script = m.group(1)
                log.log(f"Found training command in README: python {script}")
                return script

    log.log("⚠️ Could not auto-detect training script")
    return None


# ---------------------------------------------------------------------------
# Training Monitor
# ---------------------------------------------------------------------------
def monitor_training(
    ssh: SSHClient,
    pid: str,
    log_file: str,
    interval: int,
    timeout_hours: float,
    log: ReproLog,
) -> dict:
    """Monitor training progress, checking periodically."""
    start_time = time.time()
    timeout_secs = timeout_hours * 3600
    last_lines = ""
    check_count = 0

    log.log(f"Monitoring training (PID: {pid}, interval: {interval}s, timeout: {timeout_hours}h)")

    while True:
        elapsed = time.time() - start_time
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        check_count += 1

        # Check if process is still running
        check = ssh.run_command(f"kill -0 {pid} 2>/dev/null && echo RUNNING || echo DONE")
        is_running = check and "RUNNING" in check

        # Get last N lines of log
        tail = ssh.run_command(f"tail -20 {log_file} 2>/dev/null")
        if tail and tail != last_lines:
            last_lines = tail
            # Extract interesting metrics from log
            lines = tail.strip().split("\n")
            latest = lines[-1] if lines else ""
            log.log(f"[{elapsed_str}] Check #{check_count}: {latest[:120]}")
        else:
            log.log(f"[{elapsed_str}] Check #{check_count}: still running... (no new output)")

        if not is_running:
            log.log(f"Training process completed after {elapsed_str}")
            # Get exit code
            exit_info = ssh.run_command(f"wait {pid} 2>/dev/null; echo $?")
            return {
                "status": "completed",
                "duration": elapsed_str,
                "checks": check_count,
            }

        if elapsed > timeout_secs:
            log.log(f"⚠️ Timeout reached ({timeout_hours}h). Killing process...")
            ssh.run_command(f"kill {pid} 2>/dev/null")
            return {
                "status": "timeout",
                "duration": elapsed_str,
                "checks": check_count,
            }

        # Sleep between checks
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Download Results
# ---------------------------------------------------------------------------
def download_results(
    ssh: SSHClient,
    remote_dir: str,
    local_output: str,
    log: ReproLog,
) -> list[str]:
    """Download training results from remote server."""
    log.log("Scanning for result files...")

    downloaded = []
    os.makedirs(local_output, exist_ok=True)

    # Common result directories
    result_dirs = [
        "output", "outputs", "results", "checkpoints", "logs",
        "figures", "plots", "images", "saved_models", "runs",
        "experiments", "exp", "work_dirs",
    ]

    for d in result_dirs:
        check = ssh.run_command(f"test -d {remote_dir}/{d} && echo YES")
        if check and "YES" in check:
            local_d = os.path.join(local_output, d)
            log.log(f"Downloading {d}/...")
            if ssh.download_dir(f"{remote_dir}/{d}", local_d):
                downloaded.append(d)

    # Download specific result files
    result_files = [
        "*.log", "*.csv", "*.json", "*.png", "*.jpg", "*.pdf",
        "*.pt", "*.pth", "*.ckpt",
    ]
    for pattern in result_files:
        find = ssh.run_command(
            f"find {remote_dir} -maxdepth 2 -name '{pattern}' -not -path '*/.git/*' | head -20"
        )
        if find and find.strip():
            for remote_file in find.strip().split("\n"):
                rel = remote_file.replace(f"{remote_dir}/", "")
                local_file = os.path.join(local_output, rel)
                if ssh.download_file(remote_file, local_file):
                    downloaded.append(rel)

    # Download the training log
    log_file = f"{remote_dir}/training.log"
    local_log = os.path.join(local_output, "training.log")
    ssh.download_file(log_file, local_log)
    downloaded.append("training.log")

    log.log(f"Downloaded {len(downloaded)} items → {local_output}")
    return downloaded


# ---------------------------------------------------------------------------
# Main Reproduce Pipeline
# ---------------------------------------------------------------------------
def reproduce(
    code_dir: str,
    config_path: str = CONFIG_FILENAME,
    run_script: str | None = None,
    run_args: str = "",
    remote_dir: str | None = None,
    monitor_interval: int = DEFAULT_MONITOR_INTERVAL,
    timeout_hours: float = DEFAULT_TIMEOUT_HOURS,
    do_download: bool = True,
    output_dir: str | None = None,
) -> dict:
    """Main reproduce pipeline."""
    log = ReproLog()
    log.log("=== Code Reproducer started ===")

    # Load config
    if not os.path.exists(config_path):
        log.log(f"Config not found: {config_path}")
        log.log("Run with --setup to create configuration")
        return {"success": False, "error": "Config not found", "log": log.entries}

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Validate code directory
    if not os.path.isdir(code_dir):
        log.log(f"Code directory not found: {code_dir}")
        return {"success": False, "error": "Code dir not found", "log": log.entries}

    project_name = os.path.basename(os.path.abspath(code_dir))
    workspace = config.get("remote_workspace", "~/reproduce")
    if not remote_dir:
        remote_dir = f"{workspace}/{project_name}"

    if not output_dir:
        output_dir = os.path.join(os.path.dirname(code_dir), f"{project_name}_results")

    log.log(f"Project: {project_name}")
    log.log(f"Remote dir: {remote_dir}")

    report = {
        "success": False,
        "project": project_name,
        "remote_dir": remote_dir,
        "config_host": config["host"],
        "training": {},
        "results": [],
        "log": [],
    }

    # ------------------------------------------------------------------
    # Step 1: Connect
    # ------------------------------------------------------------------
    ssh = SSHClient(config, log)
    if not ssh.test_connection():
        report["error"] = "SSH connection failed"
        report["log"] = log.entries
        return report

    # Detect server info
    gpu_info = ssh.run_command("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null")
    if gpu_info and gpu_info.strip():
        log.log(f"GPUs detected: {gpu_info.strip()}")
    else:
        log.log("⚠️ No NVIDIA GPUs detected (nvidia-smi failed)")

    cuda_info = ssh.run_command("nvcc --version 2>/dev/null | grep 'release'")
    if cuda_info:
        log.log(f"CUDA: {cuda_info.strip()}")

    # ------------------------------------------------------------------
    # Step 2: Upload code
    # ------------------------------------------------------------------
    ssh.run_command(f"mkdir -p {remote_dir}")
    if not ssh.upload_dir(code_dir, remote_dir):
        report["error"] = "Code upload failed"
        report["log"] = log.entries
        return report

    # ------------------------------------------------------------------
    # Step 3: Setup environment
    # ------------------------------------------------------------------
    env_name = f"repro_{project_name}"
    setup_environment(ssh, remote_dir, env_name, config, log)

    # ------------------------------------------------------------------
    # Step 4: Detect and run training
    # ------------------------------------------------------------------
    if not run_script:
        run_script = detect_training_script(ssh, remote_dir, log)

    if not run_script:
        log.log("❌ No training script found. Please specify with --run-script")
        report["error"] = "No training script found"
        report["log"] = log.entries
        return report

    # Build training command
    env_manager = config.get("env_manager", "conda")
    conda = config.get("conda_path", "conda")

    if env_manager == "conda":
        train_cmd = f"cd {remote_dir} && {conda} run -n {env_name} python {run_script} {run_args}"
    elif env_manager == "venv":
        train_cmd = f"cd {remote_dir} && source .venv/bin/activate && python {run_script} {run_args}"
    else:
        train_cmd = f"cd {remote_dir} && python {run_script} {run_args}"

    log.log(f"Training command: {train_cmd}")

    # Run training in background
    train_log = f"{remote_dir}/training.log"
    bg_cmd = f"nohup bash -c '{train_cmd}' > {train_log} 2>&1 & echo $!"
    pid_result = ssh.run_command(bg_cmd)

    if not pid_result or not pid_result.strip():
        log.log("❌ Failed to start training process")
        report["error"] = "Training start failed"
        report["log"] = log.entries
        return report

    pid = pid_result.strip().split("\n")[-1]
    log.log(f"Training started! PID: {pid}")

    # ------------------------------------------------------------------
    # Step 5: Monitor training
    # ------------------------------------------------------------------
    training_result = monitor_training(
        ssh, pid, train_log, monitor_interval, timeout_hours, log
    )
    report["training"] = training_result

    # Get final training log
    final_log = ssh.run_command(f"tail -50 {train_log} 2>/dev/null")
    if final_log:
        report["final_log_tail"] = final_log.strip()

    # ------------------------------------------------------------------
    # Step 6: Download results
    # ------------------------------------------------------------------
    if do_download:
        downloaded = download_results(ssh, remote_dir, output_dir, log)
        report["results"] = downloaded
        report["output_dir"] = output_dir

    report["success"] = training_result.get("status") == "completed"
    report["log"] = log.entries

    # Save report
    report_path = os.path.join(output_dir, "reproduce_report.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.log(f"Report saved → {report_path}")

    log.log("=== Reproduction complete ===")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Automated code reproduction on remote GPU servers via SSH.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "code_dir",
        nargs="?",
        default=None,
        help="Path to source code directory to reproduce",
    )
    parser.add_argument("--setup", action="store_true", help="Run interactive config setup")
    parser.add_argument("--config", "-c", default=CONFIG_FILENAME, help="Server config path")
    parser.add_argument("--run-script", "-r", default=None, help="Training script to run")
    parser.add_argument("--run-args", default="", help="Extra arguments for training script")
    parser.add_argument("--remote-dir", default=None, help="Remote working directory")
    parser.add_argument("--monitor-interval", type=int, default=DEFAULT_MONITOR_INTERVAL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_HOURS, help="Timeout in hours")
    parser.add_argument("--no-download", action="store_true", help="Skip downloading results")
    parser.add_argument("--output-dir", "-o", default=None, help="Local output directory for results")

    args = parser.parse_args()

    if args.setup:
        interactive_setup(args.config)
        return 0

    if not args.code_dir:
        parser.error("code_dir is required (or use --setup)")
        return 1

    report = reproduce(
        code_dir=args.code_dir,
        config_path=args.config,
        run_script=args.run_script,
        run_args=args.run_args,
        remote_dir=args.remote_dir,
        monitor_interval=args.monitor_interval,
        timeout_hours=args.timeout,
        do_download=not args.no_download,
        output_dir=args.output_dir,
    )

    # Print summary
    print()
    if report["success"]:
        training = report.get("training", {})
        print(f"✅ Reproduction complete!")
        print(f"⏱️  Duration: {training.get('duration', 'N/A')}")
        print(f"📊 Checks: {training.get('checks', 0)}")
        print(f"📁 Results: {report.get('output_dir', 'N/A')}")
        print(f"📄 Files: {len(report.get('results', []))}")
    else:
        print(f"❌ Reproduction failed: {report.get('error', 'unknown')}")
        if report.get("final_log_tail"):
            print(f"\n--- Last training output ---")
            print(report["final_log_tail"][-500:])

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
