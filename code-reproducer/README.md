# 🖥️ Code Reproducer

Automated code reproduction on remote GPU servers via SSH.

**Full pipeline**: Connect → Upload → Setup Env → Train → Monitor → Download Results

## 🚀 Quick Start

```bash
# First-time: setup your server config
python reproduce.py --setup

# Run reproduction
python reproduce.py path/to/code/ --config server_config.json
```

## 🏗️ How It Works

```
Local Machine                       Remote GPU Server
─────────────                       ─────────────────
                    SSH
├── code/       ──────────▶  ~/reproduce/project/
│   ├── train.py               ├── train.py
│   └── ...                    ├── requirements.txt
│                              │
├── server_config.json         ├── (conda env created)
│                              ├── (pip install -r ...)
│                              │
│                              ├── 🚀 python train.py
│                              │     (nohup, background)
│                              │
│   ◀── periodic checks ──────┤     📊 training.log
│   (every 60s: tail log)      │     (epoch 1/100...)
│                              │
│                              ├── ✅ Training done!
│                              │
├── results/    ◀──────────── ├── output/
│   ├── model.pt               │   ├── model.pt
│   ├── training.log           │   ├── figures/
│   └── figures/               │   └── ...
│                              │
└── reproduce_report.json
```

## ⚙️ Configuration

Run `--setup` for interactive config, or create `server_config.json`:

```json
{
  "host": "192.168.1.100",
  "port": 22,
  "user": "researcher",
  "key_file": "~/.ssh/id_rsa",
  "env_manager": "conda",
  "conda_path": "conda",
  "remote_workspace": "~/reproduce"
}
```

### Auth Options

| Method | Config |
|--------|--------|
| SSH Key | `"key_file": "~/.ssh/id_rsa"` |
| Password | `"password": "your_password"` |
| Jump Host | `"jump_host": "bastion.example.com"` |

### Environment Options

| Manager | How It Works |
|---------|-------------|
| `conda` | Creates `repro_<project>` env, installs from `requirements.txt` / `environment.yml` |
| `venv` | Creates `.venv/`, installs from `requirements.txt` |
| `docker` | Assumes pre-configured container |
| `none` | Uses system Python |

## 🔧 CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `server_config.json` | Server configuration file |
| `--run-script` | auto-detect | Training script to run |
| `--run-args` | (empty) | Extra arguments for training |
| `--monitor-interval` | 60s | Training check interval |
| `--timeout` | 24h | Max training time |
| `--no-download` | false | Skip result download |
| `--output-dir` | `<code>_results/` | Local result directory |

## 🔍 Auto-Detection

- **Training script**: `train.py` → `main.py` → `run.py` → README parsing
- **GPU info**: `nvidia-smi`
- **CUDA**: `nvcc --version`
- **Dependencies**: `requirements.txt`, `environment.yml`, `setup.py`, `pyproject.toml`

## 📦 Zero Dependencies

Uses only system commands (`ssh`, `scp`, `rsync`). No Python packages needed.

## 📄 License

MIT — see [LICENSE](../LICENSE)
