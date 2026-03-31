"""
training_loop.py — Detect and dissect training loops in ML code.

Extracts:
- Training loop location (file, line range)
- Optimizer type and parameters
- Loss function type
- Learning rate scheduler
- Checkpoint saving logic
- Logging framework (WandB, TensorBoard, etc.)
- Batch/epoch structure
"""

import ast
import re
from pathlib import Path


# Common ML patterns to detect
OPTIMIZER_PATTERNS = {
    "Adam": r"(?:optim\.)?Adam\b",
    "AdamW": r"(?:optim\.)?AdamW\b",
    "SGD": r"(?:optim\.)?SGD\b",
    "RMSprop": r"(?:optim\.)?RMSprop\b",
    "LBFGS": r"(?:optim\.)?LBFGS\b",
    "Adagrad": r"(?:optim\.)?Adagrad\b",
    "Adadelta": r"(?:optim\.)?Adadelta\b",
}

LOSS_PATTERNS = {
    "CrossEntropyLoss": r"(?:nn\.)?CrossEntropyLoss",
    "MSELoss": r"(?:nn\.)?MSELoss",
    "BCELoss": r"(?:nn\.)?BCELoss",
    "BCEWithLogitsLoss": r"(?:nn\.)?BCEWithLogitsLoss",
    "L1Loss": r"(?:nn\.)?L1Loss",
    "NLLLoss": r"(?:nn\.)?NLLLoss",
    "KLDivLoss": r"(?:nn\.)?KLDivLoss",
    "HuberLoss": r"(?:nn\.)?HuberLoss",
    "SmoothL1Loss": r"(?:nn\.)?SmoothL1Loss",
    "custom_loss": r"def\s+\w*loss\w*\s*\(",
    "F.cross_entropy": r"F\.cross_entropy",
    "F.mse_loss": r"F\.mse_loss",
    "tf.losses": r"tf\.(?:losses|keras\.losses)\.\w+",
}

SCHEDULER_PATTERNS = {
    "StepLR": r"StepLR",
    "MultiStepLR": r"MultiStepLR",
    "ExponentialLR": r"ExponentialLR",
    "CosineAnnealingLR": r"CosineAnnealingLR",
    "CosineAnnealingWarmRestarts": r"CosineAnnealingWarmRestarts",
    "ReduceLROnPlateau": r"ReduceLROnPlateau",
    "LinearLR": r"LinearLR",
    "OneCycleLR": r"OneCycleLR",
    "WarmupCosine": r"(?:warmup|WarmUp).*(?:cosine|Cosine)",
    "LinearWarmup": r"(?:linear|Linear).*(?:warmup|WarmUp)",
}

LOGGING_PATTERNS = {
    "wandb": r"(?:import wandb|wandb\.init|wandb\.log)",
    "tensorboard": r"(?:SummaryWriter|tf\.summary|TensorBoard)",
    "mlflow": r"(?:import mlflow|mlflow\.log)",
    "comet": r"(?:comet_ml|Experiment\()",
    "neptune": r"(?:import neptune|neptune\.init)",
    "aim": r"(?:from aim|aim\.Run)",
    "clearml": r"(?:from clearml|Task\.init)",
    "print": r"print\(.*(?:loss|acc|epoch|step)",
    "tqdm": r"(?:from tqdm|tqdm\()",
}


class TrainingLoopDetector(ast.NodeVisitor):
    """AST-based training loop detection."""

    def __init__(self, source_lines: list[str]):
        self.loops: list[dict] = []
        self.source_lines = source_lines
        self._in_func: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old = self._in_func
        self._in_func = node.name
        self.generic_visit(node)
        self._in_func = old

    def visit_For(self, node: ast.For):
        """Detect for loops that look like training loops."""
        is_epoch_loop = False
        is_batch_loop = False

        # Check iterator
        try:
            iter_str = ast.unparse(node.iter)
            target_str = ast.unparse(node.target)
        except Exception:
            iter_str = ""
            target_str = ""

        # Epoch loop detection
        if any(kw in target_str.lower() for kw in ["epoch", "e"]):
            is_epoch_loop = True
        if any(kw in iter_str.lower() for kw in ["range", "epoch", "num_epoch"]):
            if "epoch" in target_str.lower():
                is_epoch_loop = True

        # Batch/step loop detection
        if any(kw in target_str.lower() for kw in ["batch", "step", "i", "idx", "data"]):
            # Check if iterating over a dataloader-like object
            if any(kw in iter_str.lower() for kw in [
                "dataloader", "train_loader", "data_loader", "loader",
                "iterator", "dataset", "enumerate", "train_data",
            ]):
                is_batch_loop = True

        # Check body for training patterns
        body_text = ""
        if node.end_lineno and node.lineno:
            body_lines = self.source_lines[node.lineno - 1:node.end_lineno]
            body_text = "\n".join(body_lines)

        has_backward = "backward()" in body_text or ".backward(" in body_text
        has_step = "optimizer.step()" in body_text or ".step()" in body_text
        has_zero_grad = "zero_grad()" in body_text
        has_loss = "loss" in body_text.lower()
        has_gradient = "gradient" in body_text.lower() or "grad" in body_text.lower()

        # TF-style training detection
        has_tf_train = "train_step" in body_text or "GradientTape" in body_text
        has_apply_grad = "apply_gradients" in body_text

        is_training = (
            (has_backward and has_step) or  # PyTorch
            (has_tf_train or has_apply_grad) or  # TF
            (has_loss and (has_gradient or has_backward)) or  # General
            (is_epoch_loop and has_loss)
        )

        if is_training or is_epoch_loop or is_batch_loop:
            self.loops.append({
                "type": "epoch" if is_epoch_loop else ("batch" if is_batch_loop else "training"),
                "function": self._in_func,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", None),
                "iterator": iter_str[:80],
                "target": target_str,
                "has_backward": has_backward,
                "has_optimizer_step": has_step,
                "has_loss": has_loss,
                "confidence": "high" if (is_epoch_loop and has_loss) or (has_backward and has_step) else "medium",
            })

        self.generic_visit(node)


def _search_patterns(content: str, patterns: dict[str, str]) -> list[str]:
    """Search for regex patterns in content."""
    found = []
    for name, pattern in patterns.items():
        if re.search(pattern, content):
            found.append(name)
    return found


def _extract_hyperparams_from_source(content: str) -> dict:
    """Extract hyperparameter values from source code."""
    params = {}
    hp_patterns = {
        "learning_rate": [
            r"lr\s*=\s*([\d.e-]+)",
            r"learning_rate\s*=\s*([\d.e-]+)",
        ],
        "batch_size": [
            r"batch_size\s*=\s*(\d+)",
        ],
        "epochs": [
            r"(?:num_)?epochs?\s*=\s*(\d+)",
            r"range\((\d+)\).*#.*epoch",
        ],
        "weight_decay": [
            r"weight_decay\s*=\s*([\d.e-]+)",
        ],
        "seed": [
            r"(?:random_)?seed\s*=\s*(\d+)",
        ],
        "gradient_clip": [
            r"(?:grad_clip|clip_grad|max_grad_norm)\s*=\s*([\d.e-]+)",
        ],
        "warmup_steps": [
            r"warmup_steps?\s*=\s*(\d+)",
        ],
        "dropout": [
            r"dropout\s*=\s*([\d.]+)",
        ],
    }

    for param, pats in hp_patterns.items():
        for pat in pats:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                params[param] = m.group(1)
                break

    return params


def analyze_training_loop(code_dir: str) -> dict:
    """Analyze training loops across all Python files.

    Returns:
        dict with:
        - training_loops: detected training loops with details
        - optimizers: optimizer types found
        - loss_functions: loss function types found
        - lr_schedulers: learning rate schedulers found
        - logging: logging frameworks detected
        - hyperparameters: extracted hyperparameter values
        - checkpoint_saving: whether checkpoint saving is detected
        - distributed_training: whether distributed training patterns exist
    """
    code_path = Path(code_dir)
    all_loops = []
    all_optimizers = []
    all_losses = []
    all_schedulers = []
    all_logging = []
    all_hyperparams = {}
    has_checkpoint = False
    has_distributed = False
    has_amp = False  # automatic mixed precision

    for pyfile in sorted(code_path.rglob("*.py")):
        if ".git" in pyfile.parts or "__pycache__" in pyfile.parts:
            continue

        try:
            content = pyfile.read_text(encoding="utf-8", errors="replace")
            source_lines = content.split("\n")
        except Exception:
            continue

        rel = str(pyfile.relative_to(code_path))

        # AST-based loop detection
        try:
            tree = ast.parse(content, filename=str(pyfile))
            detector = TrainingLoopDetector(source_lines)
            detector.visit(tree)
            for loop in detector.loops:
                loop["file"] = rel
                all_loops.append(loop)
        except SyntaxError:
            pass

        # Pattern-based detection
        optimizers = _search_patterns(content, OPTIMIZER_PATTERNS)
        losses = _search_patterns(content, LOSS_PATTERNS)
        schedulers = _search_patterns(content, SCHEDULER_PATTERNS)
        logging = _search_patterns(content, LOGGING_PATTERNS)

        for o in optimizers:
            if o not in all_optimizers:
                all_optimizers.append(o)
        for l in losses:
            if l not in all_losses:
                all_losses.append(l)
        for s in schedulers:
            if s not in all_schedulers:
                all_schedulers.append(s)
        for lg in logging:
            if lg not in all_logging:
                all_logging.append(lg)

        # Hyperparameters
        hp = _extract_hyperparams_from_source(content)
        all_hyperparams.update(hp)

        # Checkpoint detection
        if any(kw in content for kw in [
            "save_checkpoint", "torch.save", "save_pretrained",
            "model.save", "tf.train.Checkpoint", "saver.save",
        ]):
            has_checkpoint = True

        # Distributed training detection
        if any(kw in content for kw in [
            "DistributedDataParallel", "DataParallel", "torch.distributed",
            "accelerate", "deepspeed", "horovod", "tf.distribute",
        ]):
            has_distributed = True

        # AMP detection
        if any(kw in content for kw in [
            "autocast", "GradScaler", "mixed_precision", "amp",
        ]):
            has_amp = True

    # Sort loops by confidence
    all_loops.sort(key=lambda x: (0 if x["confidence"] == "high" else 1, x["lineno"]))

    return {
        "training_loops": all_loops,
        "optimizers": all_optimizers,
        "loss_functions": all_losses,
        "lr_schedulers": all_schedulers,
        "logging_frameworks": all_logging,
        "hyperparameters": all_hyperparams,
        "checkpoint_saving": has_checkpoint,
        "distributed_training": has_distributed,
        "mixed_precision": has_amp,
        "stats": {
            "loops_found": len(all_loops),
            "high_confidence_loops": len([l for l in all_loops if l["confidence"] == "high"]),
        },
    }
