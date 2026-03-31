# 🔬 Code Analyzer

Comprehensive deep analysis of ML source code repositories for paper reproduction.

## Features

| Module | What It Does |
|--------|-------------|
| `framework.py` | Detect ML framework (PyTorch, TF, JAX, HF) with confidence scores |
| `ast_analyzer.py` | AST-based call graph, class hierarchy, model layer extraction |
| `training_loop.py` | Training loop dissection (optimizer, loss, scheduler, logging) |
| `config_extractor.py` | Config system detection (argparse/Hydra/YAML) + hyperparameter extraction |
| `reproducibility.py` | ML Code Completeness scoring (0-100, A-F grade) |
| `structure.py` | File structure and training script detection |
| `readme_parser.py` | README install/train/eval command extraction |
| `dependency.py` | Package dependency and CUDA/GPU requirement analysis |

## Quick Start

```bash
# Run full analysis (core: zero external dependencies)
python analyze.py path/to/repo/ -o analysis.json

# With optional flowchart (requires: pip install code2flow)
python analyze.py path/to/repo/ -o analysis.json --flowchart
```

## Example Output

```
════════════════════════════════════════════════════════════
  📊 Code Analysis Report: diffusion
════════════════════════════════════════════════════════════
  🔧 Framework     : tensorflow
  📁 Files          : 22 (17 .py)
  🏗️  Classes        : 15 (4 model)
  📐 Functions      : 154
  🔗 Call edges     : 868
  🔄 Training loops : 3 (high-conf: 1)
  ⚡ Optimizers     : Adam
  📉 Loss functions : custom_loss, tf.losses
  📦 Packages       : 115
  🎯 Reproducibility: 45/100 = D (45.0%)

  🧠 Model classes:
     → Model [scripts.run_cifar]
     → Model [scripts.run_celebahq]

  💡 Recommendations:
     • Provide pre-trained model weights or download links
     • Add training command examples to README
```

## Architecture

```
code-analyzer/
├── analyze.py              # Main CLI entry (orchestrates all 7 modules)
├── analyzers/
│   ├── ast_analyzer.py     # 🧠 AST call graph + class extraction
│   ├── training_loop.py    # 🔄 Training loop dissection
│   ├── reproducibility.py  # 📊 ML Completeness scoring
│   ├── config_extractor.py # ⚙️  Config system + hyperparameters
│   ├── framework.py        # 🔧 Framework detection
│   ├── structure.py        # 📁 File structure analysis
│   ├── readme_parser.py    # 📖 README parsing
│   └── dependency.py       # 📦 Dependency analysis
└── requirements.txt        # Optional: code2flow
```

## Credits

- **AST analysis**: Inspired by [PyCG](https://github.com/vitsalis/PyCG) (ICSE'21)
- **Reproducibility scoring**: Based on [ML Code Completeness Checklist](https://medium.com/paperswithcode/ml-code-completeness-checklist-e9127b168501) (Papers With Code)
- **Flowchart**: Optional [code2flow](https://github.com/scottrogowski/code2flow) integration

## License

MIT — see [LICENSE](../LICENSE)
