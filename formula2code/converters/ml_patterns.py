"""
ML Formula Pattern Matcher.
Recognizes well-known ML formulas and maps them directly to PyTorch API calls,
bypassing the SymPy pipeline for better accuracy.
"""
import re
import json
import os
from typing import Optional, Dict, List

# ── Built-in pattern library ────────────────────────────────────────────────
# Each pattern has:
#   - name: human-readable identifier
#   - latex_patterns: list of regex patterns to match against input LaTeX
#   - pytorch_code: ready-to-use PyTorch code
#   - pytorch_functional: using torch.nn.functional
#   - pytorch_class: using torch.nn module
#   - numpy_code: NumPy equivalent
#   - description: what this formula does
#   - category: loss | activation | attention | normalization | distribution | optimizer

BUILTIN_PATTERNS = [
    # ── Loss Functions ──
    {
        "name": "mse_loss",
        "category": "loss",
        "description": "Mean Squared Error Loss",
        "latex_patterns": [
            r"\\frac\{1\}\{[Nn]\}\\sum.*?\(.*?-.*?\)\^2",
            r"\\frac\{1\}\{[Nn]\}\\sum.*?\|.*?-.*?\|\^2",
            r"\\mathbb\{E\}.*?\[.*?\(.*?-.*?\)\^2\]",
        ],
        "pytorch_functional": "F.mse_loss(predictions, targets)",
        "pytorch_class": "nn.MSELoss()",
        "numpy_code": "np.mean((predictions - targets) ** 2)",
    },
    {
        "name": "cross_entropy",
        "category": "loss",
        "description": "Cross Entropy Loss",
        "latex_patterns": [
            r"-\\sum.*?[py].*?\\log.*?[qp]",
            r"-\\frac\{1\}\{[Nn]\}\\sum.*?\\log",
            r"\\mathcal\{L\}.*?=.*?-.*?\\log",
        ],
        "pytorch_functional": "F.cross_entropy(logits, targets)",
        "pytorch_class": "nn.CrossEntropyLoss()",
        "numpy_code": "-np.sum(targets * np.log(predictions + 1e-8))",
    },
    {
        "name": "binary_cross_entropy",
        "category": "loss",
        "description": "Binary Cross Entropy Loss",
        "latex_patterns": [
            r"-.*?[yt].*?\\log.*?[yp].*?-.*?\(1-[yt]\).*?\\log.*?\(1-[yp]\)",
        ],
        "pytorch_functional": "F.binary_cross_entropy_with_logits(logits, targets)",
        "pytorch_class": "nn.BCEWithLogitsLoss()",
        "numpy_code": "-(targets * np.log(pred + 1e-8) + (1-targets) * np.log(1-pred + 1e-8)).mean()",
    },
    {
        "name": "kl_divergence",
        "category": "loss",
        "description": "KL Divergence",
        "latex_patterns": [
            r"D_\{KL\}",
            r"\\sum.*?[pq].*?\\log\\frac\{[pq]\}\{[pq]\}",
            r"D_\{\\mathrm\{KL\}\}",
        ],
        "pytorch_functional": "F.kl_div(q_log_prob, p_prob, reduction='batchmean')",
        "pytorch_class": "nn.KLDivLoss(reduction='batchmean')",
        "numpy_code": "np.sum(p * np.log(p / (q + 1e-8) + 1e-8))",
    },
    {
        "name": "l1_loss",
        "category": "loss",
        "description": "L1 / Mean Absolute Error Loss",
        "latex_patterns": [
            r"\\frac\{1\}\{[Nn]\}\\sum.*?\\lVert.*?-.*?\\rVert",
            r"\\text\{MAE\}|\\text\{L1\}|\\operatorname\{MAE\}",
        ],
        "pytorch_functional": "F.l1_loss(predictions, targets)",
        "pytorch_class": "nn.L1Loss()",
        "numpy_code": "np.mean(np.abs(predictions - targets))",
    },
    {
        "name": "huber_loss",
        "category": "loss",
        "description": "Huber / Smooth L1 Loss",
        "latex_patterns": [
            r"\\begin\{cases\}.*?\\frac\{1\}\{2\}.*?\^2.*?\\delta",
        ],
        "pytorch_functional": "F.smooth_l1_loss(predictions, targets)",
        "pytorch_class": "nn.SmoothL1Loss()",
        "numpy_code": "np.where(np.abs(d) < delta, 0.5*d**2, delta*(np.abs(d)-0.5*delta))",
    },

    # ── Activation Functions ──
    {
        "name": "softmax",
        "category": "activation",
        "description": "Softmax activation",
        "latex_patterns": [
            r"(?:softmax|\\text\{softmax\}|\\operatorname\{softmax\})",
            r"\\frac\{e\^\{.*?\}\}\{\\sum.*?e\^\{",
            r"\\frac\{\\exp\(.*?\)\}\{\\sum.*?\\exp\(",
        ],
        "pytorch_functional": "F.softmax(x, dim=-1)",
        "pytorch_class": "nn.Softmax(dim=-1)",
        "numpy_code": "np.exp(x - np.max(x)) / np.sum(np.exp(x - np.max(x)))",
    },
    {
        "name": "sigmoid",
        "category": "activation",
        "description": "Sigmoid activation",
        "latex_patterns": [
            r"\\frac\{1\}\{1\+e\^\{-",
            r"\\frac\{1\}\{1\+\\exp\(-",
            r"\\sigma\(",
        ],
        "pytorch_functional": "torch.sigmoid(x)",
        "pytorch_class": "nn.Sigmoid()",
        "numpy_code": "1 / (1 + np.exp(-x))",
    },
    {
        "name": "relu",
        "category": "activation",
        "description": "ReLU activation",
        "latex_patterns": [
            r"\\max\(0,\s*",
            r"(?:ReLU|\\text\{ReLU\}|\\operatorname\{ReLU\})",
        ],
        "pytorch_functional": "F.relu(x)",
        "pytorch_class": "nn.ReLU()",
        "numpy_code": "np.maximum(0, x)",
    },
    {
        "name": "gelu",
        "category": "activation",
        "description": "GELU activation",
        "latex_patterns": [
            r"(?:GELU|\\text\{GELU\}|\\operatorname\{GELU\})",
            r"x.*?\\Phi\(x\)",
        ],
        "pytorch_functional": "F.gelu(x)",
        "pytorch_class": "nn.GELU()",
        "numpy_code": "0.5 * x * (1 + np.tanh(np.sqrt(2/np.pi) * (x + 0.044715 * x**3)))",
    },
    {
        "name": "tanh",
        "category": "activation",
        "description": "Tanh activation",
        "latex_patterns": [
            r"\\tanh\(",
            r"\\frac\{e\^\{.*?\}-e\^\{-.*?\}\}\{e\^\{.*?\}\+e\^\{-.*?\}\}",
        ],
        "pytorch_functional": "torch.tanh(x)",
        "pytorch_class": "nn.Tanh()",
        "numpy_code": "np.tanh(x)",
    },

    # ── Attention ──
    {
        "name": "scaled_dot_product_attention",
        "category": "attention",
        "description": "Scaled Dot-Product Attention (Vaswani et al., 2017)",
        "latex_patterns": [
            r"(?:softmax|\\text\{softmax\}).*?\\frac\{.*?K.*?T\}\{\\sqrt\{d",
            r"\\text\{Attention\}\(Q,\s*K,\s*V\)",
            r"Attention.*?=.*?softmax.*?QK",
        ],
        "pytorch_functional": "F.scaled_dot_product_attention(Q, K, V)",
        "pytorch_class": "nn.MultiheadAttention(embed_dim, num_heads)",
        "numpy_code": (
            "scores = Q @ K.T / np.sqrt(d_k)\n"
            "weights = np.exp(scores - scores.max()) / np.exp(scores - scores.max()).sum(-1, keepdims=True)\n"
            "output = weights @ V"
        ),
    },

    # ── Normalization ──
    {
        "name": "layer_norm",
        "category": "normalization",
        "description": "Layer Normalization",
        "latex_patterns": [
            r"\\frac\{x.*?-.*?\\mu\}\{.*?\\sigma.*?\\epsilon\}",
            r"(?:LayerNorm|\\text\{LayerNorm\})",
        ],
        "pytorch_functional": "F.layer_norm(x, normalized_shape)",
        "pytorch_class": "nn.LayerNorm(normalized_shape)",
        "numpy_code": "(x - np.mean(x, axis=-1, keepdims=True)) / (np.std(x, axis=-1, keepdims=True) + eps)",
    },
    {
        "name": "batch_norm",
        "category": "normalization",
        "description": "Batch Normalization",
        "latex_patterns": [
            r"(?:BatchNorm|\\text\{BatchNorm\}|\\text\{BN\})",
            r"\\gamma.*?\\frac\{x-\\mu_B\}\{\\sqrt\{\\sigma_B\^2",
        ],
        "pytorch_functional": "F.batch_norm(x, running_mean, running_var)",
        "pytorch_class": "nn.BatchNorm2d(num_features)",
        "numpy_code": "gamma * (x - mean) / np.sqrt(var + eps) + beta",
    },

    # ── Distributions ──
    {
        "name": "gaussian",
        "category": "distribution",
        "description": "Gaussian / Normal Distribution PDF",
        "latex_patterns": [
            r"\\frac\{1\}\{\\sqrt\{2\\pi.*?\\sigma",
            r"\\mathcal\{N\}\(",
        ],
        "pytorch_functional": "torch.distributions.Normal(mu, sigma).log_prob(x).exp()",
        "pytorch_class": "torch.distributions.Normal(mu, sigma)",
        "numpy_code": "(1 / (sigma * np.sqrt(2*np.pi))) * np.exp(-0.5 * ((x-mu)/sigma)**2)",
    },
]


def match_ml_pattern(latex: str) -> Optional[Dict]:
    """
    Try to match a LaTeX string against known ML formula patterns.

    Args:
        latex: Raw LaTeX math string

    Returns:
        Pattern dict if matched, None otherwise.
        Dict contains: name, category, description, pytorch_functional,
                      pytorch_class, numpy_code
    """
    for pattern in BUILTIN_PATTERNS:
        for regex in pattern['latex_patterns']:
            try:
                if re.search(regex, latex, re.IGNORECASE):
                    return {
                        'name': pattern['name'],
                        'category': pattern['category'],
                        'description': pattern['description'],
                        'pytorch_functional': pattern.get('pytorch_functional', ''),
                        'pytorch_class': pattern.get('pytorch_class', ''),
                        'numpy_code': pattern.get('numpy_code', ''),
                        'matched_by': regex,
                    }
            except re.error:
                continue
    return None


def match_all_patterns(latex: str) -> List[Dict]:
    """Return ALL matching patterns (some formulas may match multiple)."""
    matches = []
    for pattern in BUILTIN_PATTERNS:
        for regex in pattern['latex_patterns']:
            try:
                if re.search(regex, latex, re.IGNORECASE):
                    matches.append({
                        'name': pattern['name'],
                        'category': pattern['category'],
                        'description': pattern['description'],
                        'pytorch_functional': pattern.get('pytorch_functional', ''),
                        'matched_by': regex,
                    })
                    break  # only one match per pattern
            except re.error:
                continue
    return matches


def load_custom_patterns(json_path: str) -> List[Dict]:
    """Load additional patterns from a JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('patterns', [])


def get_all_pattern_names() -> List[str]:
    """Return list of all built-in pattern names."""
    return [p['name'] for p in BUILTIN_PATTERNS]


def get_patterns_by_category(category: str) -> List[Dict]:
    """Return patterns filtered by category."""
    return [p for p in BUILTIN_PATTERNS if p['category'] == category]
