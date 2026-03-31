"""
Extract model architecture description from paper content.
Identifies model components, layers, and structure.
"""
import re
from typing import Dict, List


# Keywords that indicate architecture components
ARCH_KEYWORDS = {
    'encoder': ['encoder', 'encoding'],
    'decoder': ['decoder', 'decoding'],
    'attention': ['attention', 'self-attention', 'multi-head', 'cross-attention'],
    'transformer': ['transformer'],
    'convolution': ['convolution', 'conv2d', 'conv1d', 'cnn', 'convolutional'],
    'residual': ['residual', 'resnet', 'skip connection', 'shortcut'],
    'recurrent': ['rnn', 'lstm', 'gru', 'recurrent'],
    'normalization': ['batch norm', 'layer norm', 'group norm', 'instance norm'],
    'pooling': ['pooling', 'max pool', 'avg pool', 'global average'],
    'dropout': ['dropout'],
    'embedding': ['embedding', 'positional encoding'],
    'linear': ['linear', 'fully connected', 'dense', 'mlp'],
    'unet': ['u-net', 'unet'],
    'gan': ['generator', 'discriminator', 'adversarial'],
    'vae': ['variational', 'vae', 'latent'],
    'diffusion': ['diffusion', 'denoise', 'ddpm', 'score-based'],
}


def extract_architecture(sections: List[Dict], full_text: str = '') -> Dict:
    """
    Extract model architecture information from paper sections.

    Args:
        sections: List of paper sections from paper_info extractor
        full_text: Full paper text for fallback search

    Returns:
        Dict with: model_name, components, architecture_type, layer_descriptions
    """
    arch = {
        'model_name': '',
        'architecture_type': '',
        'components': [],
        'layer_descriptions': [],
        'input_description': '',
        'output_description': '',
    }

    # Find architecture/method sections
    method_sections = []
    for sec in sections:
        title = sec.get('title', '').lower()
        if any(kw in title for kw in ['method', 'model', 'architecture', 'approach',
                                       'framework', 'network', 'proposed']):
            method_sections.append(sec)

    search_text = ' '.join(s.get('content', '') for s in method_sections)
    if not search_text:
        search_text = full_text

    # Detect architecture type
    detected_types = []
    for arch_type, keywords in ARCH_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', search_text, re.IGNORECASE):
                detected_types.append(arch_type)
                break

    arch['components'] = detected_types
    if detected_types:
        arch['architecture_type'] = detected_types[0]  # Primary

    # Extract model name (often in title or method section heading)
    name_patterns = [
        r'(?:we\s+propose|we\s+present|we\s+introduce)\s+(\w+(?:\s+\w+){0,2})',
        r'(?:our\s+model|our\s+method|our\s+approach),?\s+(?:called|named|dubbed)\s+(\w+)',
    ]
    for pattern in name_patterns:
        m = re.search(pattern, search_text, re.IGNORECASE)
        if m:
            arch['model_name'] = m.group(1).strip()
            break

    # Extract layer descriptions
    layer_patterns = [
        r'(\d+)\s+(?:layer|block)s?\s+(?:of\s+)?(\w+)',
        r'(\w+)\s+layer\s+with\s+(\d+)\s+(?:unit|neuron|channel|head)',
        r'hidden\s+(?:size|dimension|dim)\s+(?:of\s+)?(\d+)',
    ]
    for pattern in layer_patterns:
        for m in re.finditer(pattern, search_text, re.IGNORECASE):
            arch['layer_descriptions'].append(m.group(0))

    return arch
