#!/usr/bin/env python3
"""
Image Comparator — Compare generated images against paper figures.
SSIM + PSNR (core), FID (optional).
"""
import os
from typing import Dict, List, Optional, Tuple


def compute_ssim(img_path1: str, img_path2: str) -> float:
    """
    Compute SSIM between two images.
    Uses scikit-image.
    """
    try:
        from skimage.metrics import structural_similarity as ssim
        from skimage.io import imread
        from skimage.transform import resize
        from skimage.color import rgb2gray
    except ImportError:
        raise ImportError("Install scikit-image: pip install scikit-image")

    img1 = imread(img_path1)
    img2 = imread(img_path2)

    # Resize to match
    if img1.shape != img2.shape:
        target_shape = (min(img1.shape[0], img2.shape[0]),
                        min(img1.shape[1], img2.shape[1]))
        img1 = resize(img1, target_shape, anti_aliasing=True)
        img2 = resize(img2, target_shape, anti_aliasing=True)

    # Convert to grayscale if needed
    if len(img1.shape) == 3:
        img1 = rgb2gray(img1)
    if len(img2.shape) == 3:
        img2 = rgb2gray(img2)

    score = ssim(img1, img2, data_range=img1.max() - img1.min())
    return float(score)


def compute_psnr(img_path1: str, img_path2: str) -> float:
    """
    Compute PSNR between two images.
    """
    try:
        from skimage.metrics import peak_signal_noise_ratio as psnr
        from skimage.io import imread
        from skimage.transform import resize
    except ImportError:
        raise ImportError("Install scikit-image: pip install scikit-image")

    img1 = imread(img_path1)
    img2 = imread(img_path2)

    # Resize to match
    if img1.shape != img2.shape:
        target_shape = (min(img1.shape[0], img2.shape[0]),
                        min(img1.shape[1], img2.shape[1]))
        img1 = resize(img1, target_shape, anti_aliasing=True)
        img2 = resize(img2, target_shape, anti_aliasing=True)

    score = psnr(img1, img2, data_range=img1.max() - img1.min())
    return float(score)


def compute_fid(real_dir: str, generated_dir: str) -> Optional[float]:
    """
    Compute FID score between two directories of images.
    OPTIONAL — requires pytorch-fid.

    Returns None if pytorch-fid is not installed.
    """
    try:
        from pytorch_fid import fid_score
        score = fid_score.calculate_fid_given_paths(
            [real_dir, generated_dir],
            batch_size=50,
            device='cuda' if _has_cuda() else 'cpu',
            dims=2048,
        )
        return float(score)
    except ImportError:
        return None
    except Exception as e:
        print(f"FID computation failed: {e}")
        return None


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def compare_images(
    reproduced_path: str,
    paper_path: str,
    compute_fid_flag: bool = False,
) -> Dict:
    """
    Compare a reproduced image against a paper figure.

    Args:
        reproduced_path: Path to reproduced image or directory
        paper_path: Path to paper figure or directory
        compute_fid_flag: Whether to compute FID (optional, slow)

    Returns dict with SSIM, PSNR, and optionally FID.
    """
    result = {
        'reproduced': reproduced_path,
        'paper': paper_path,
        'ssim': None,
        'psnr': None,
        'fid': None,
    }

    # Single image comparison
    if os.path.isfile(reproduced_path) and os.path.isfile(paper_path):
        try:
            result['ssim'] = compute_ssim(reproduced_path, paper_path)
            result['psnr'] = compute_psnr(reproduced_path, paper_path)
        except Exception as e:
            result['error'] = str(e)

        # SSIM interpretation
        if result['ssim'] is not None:
            if result['ssim'] > 0.9:
                result['ssim_grade'] = 'Excellent'
                result['status'] = 'PASS'
                result['emoji'] = '✅'
            elif result['ssim'] > 0.7:
                result['ssim_grade'] = 'Good'
                result['status'] = 'WARN'
                result['emoji'] = '⚠️'
            elif result['ssim'] > 0.5:
                result['ssim_grade'] = 'Fair'
                result['status'] = 'WARN'
                result['emoji'] = '⚠️'
            else:
                result['ssim_grade'] = 'Poor'
                result['status'] = 'FAIL'
                result['emoji'] = '❌'

    # Directory comparison (for FID)
    elif os.path.isdir(reproduced_path) and os.path.isdir(paper_path):
        if compute_fid_flag:
            result['fid'] = compute_fid(paper_path, reproduced_path)
            if result['fid'] is not None:
                if result['fid'] < 10:
                    result['status'] = 'PASS'
                    result['emoji'] = '✅'
                elif result['fid'] < 50:
                    result['status'] = 'WARN'
                    result['emoji'] = '⚠️'
                else:
                    result['status'] = 'FAIL'
                    result['emoji'] = '❌'

    return result


def generate_side_by_side(
    reproduced_path: str,
    paper_path: str,
    output_path: str = 'figures/sample_comparison.png',
    title: str = 'Sample Comparison',
) -> str:
    """Generate a side-by-side comparison image."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    try:
        from skimage.io import imread
        if os.path.isfile(paper_path):
            img_paper = imread(paper_path)
            ax1.imshow(img_paper)
        ax1.set_title('Paper Figure', fontsize=12, fontweight='bold')
        ax1.axis('off')

        if os.path.isfile(reproduced_path):
            img_repro = imread(reproduced_path)
            ax2.imshow(img_repro)
        ax2.set_title('Reproduced', fontsize=12, fontweight='bold')
        ax2.axis('off')
    except ImportError:
        ax1.text(0.5, 0.5, 'skimage not installed', ha='center', va='center')
        ax2.text(0.5, 0.5, 'skimage not installed', ha='center', va='center')

    plt.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return output_path
