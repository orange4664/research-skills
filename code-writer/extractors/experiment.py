"""
Extract experiment settings from paper content.
Identifies hyperparameters, datasets, metrics, and training details.
"""
import re
from typing import Dict, List


# Common hyperparameter names and patterns
HYPERPARAM_PATTERNS = {
    'learning_rate': [r'learning\s*rate\s*(?:of\s*)?(\d+\.?\d*(?:e-?\d+)?)', r'lr\s*=\s*(\d+\.?\d*(?:e-?\d+)?)'],
    'batch_size': [r'batch\s*size\s*(?:of\s*)?(\d+)', r'mini-?batch\s*(?:of\s*)?(\d+)'],
    'epochs': [r'(\d+)\s*epochs?', r'train(?:ed)?\s+for\s+(\d+)'],
    'optimizer': [r'(Adam|SGD|AdamW|RMSprop|Adagrad)\s+optimizer', r'optimiz\w+\s+(?:using|with)\s+(Adam|SGD|AdamW)'],
    'weight_decay': [r'weight\s*decay\s*(?:of\s*)?(\d+\.?\d*(?:e-?\d+)?)'],
    'dropout': [r'dropout\s*(?:rate\s*)?(?:of\s*)?(\d+\.?\d*)'],
    'hidden_dim': [r'hidden\s*(?:dimension|size|dim)\s*(?:of\s*)?(\d+)'],
    'num_layers': [r'(\d+)\s*(?:layer|block)s?'],
    'num_heads': [r'(\d+)\s*(?:attention\s*)?heads?'],
    'warmup': [r'warmup\s*(?:of\s*)?(\d+)\s*(?:steps?|epochs?)'],
    'scheduler': [r'(cosine|linear|step|exponential)\s*(?:learning\s*rate\s*)?(?:decay|schedule|annealing)'],
    'gradient_clip': [r'gradient\s*clip(?:ping)?\s*(?:of\s*)?(\d+\.?\d*)'],
    'seed': [r'(?:random\s*)?seed\s*(?:of\s*)?(\d+)'],
}

# Common dataset names
KNOWN_DATASETS = [
    'CIFAR-10', 'CIFAR-100', 'ImageNet', 'MNIST', 'Fashion-MNIST',
    'COCO', 'VOC', 'CelebA', 'LSUN', 'FFHQ', 'SVHN',
    'WikiText', 'Penn Treebank', 'PTB', 'SQuAD', 'GLUE', 'SuperGLUE',
    'WMT', 'IWSLT', 'CommonCrawl', 'OpenWebText', 'The Pile',
    'LibriSpeech', 'AudioSet', 'LJSpeech',
    'ModelNet', 'ShapeNet', 'ScanNet',
]

# Common evaluation metrics
KNOWN_METRICS = [
    'accuracy', 'top-1', 'top-5', 'precision', 'recall', 'F1',
    'BLEU', 'ROUGE', 'perplexity', 'PPL',
    'FID', 'IS', 'Inception Score', 'LPIPS', 'SSIM', 'PSNR',
    'mAP', 'IoU', 'mIoU', 'AUC', 'ROC',
    'MSE', 'RMSE', 'MAE', 'R²',
]


def extract_experiment(sections: List[Dict], full_text: str = '') -> Dict:
    """
    Extract experiment settings from paper sections.

    Returns:
        Dict with: hyperparameters, datasets, metrics, hardware, training_details
    """
    result = {
        'hyperparameters': {},
        'datasets': [],
        'metrics': [],
        'hardware': '',
        'training_details': '',
    }

    # Find experiment/implementation sections
    exp_text = ''
    for sec in sections:
        title = sec.get('title', '').lower()
        if any(kw in title for kw in ['experiment', 'implementation', 'training',
                                       'setup', 'detail', 'setting', 'hyperparameter']):
            exp_text += sec.get('content', '') + '\n'

    if not exp_text:
        exp_text = full_text

    # Extract hyperparameters
    for param_name, patterns in HYPERPARAM_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, exp_text, re.IGNORECASE)
            if m:
                result['hyperparameters'][param_name] = m.group(1)
                break

    # Detect datasets
    for ds in KNOWN_DATASETS:
        if re.search(r'\b' + re.escape(ds) + r'\b', exp_text, re.IGNORECASE):
            result['datasets'].append(ds)

    # Detect metrics
    for metric in KNOWN_METRICS:
        if re.search(r'\b' + re.escape(metric) + r'\b', exp_text, re.IGNORECASE):
            result['metrics'].append(metric)

    # Detect hardware
    hw_match = re.search(
        r'(\d+)\s*(?:×|x)\s*(NVIDIA|Tesla|A100|V100|RTX|GPU|TPU)[\w\s-]*',
        exp_text, re.IGNORECASE
    )
    if hw_match:
        result['hardware'] = hw_match.group(0).strip()
    else:
        hw_match = re.search(r'(NVIDIA|Tesla|A100|V100|RTX|4090|3090|H100)[\w\s-]*', exp_text)
        if hw_match:
            result['hardware'] = hw_match.group(0).strip()

    return result
