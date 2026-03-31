#!/usr/bin/env python3
"""
download_paper.py - Download paper PDFs and clone source code repositories.

Usage:
    python download_paper.py <paper_info.json> [options]

Options:
    --output-dir <dir>     Output directory (default: workspace/<paper-slug>)
    --allow-scihub         Enable Sci-Hub as a fallback PDF source
    --clone-depth <n>      Git clone depth (default: 1, use 0 for full clone)
    --skip-code            Skip cloning code repositories
    --skip-pdf             Skip downloading PDF

Reads the paper_info.json produced by paper-finder's search_paper.py.

PDF Download Priority:
    1. arXiv pdf_url (direct download)
    2. Open Access sources (Unpaywall)
    3. Sci-Hub (if --allow-scihub is set)

Code Clone:
    - Clones the highest-confidence official repository
    - Uses shallow clone (--depth 1) by default to save space
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Sci-Hub mirrors (tried in order; updated list)
SCIHUB_MIRRORS = [
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.ru",
    "https://sci-hub.pub",
]

UNPAYWALL_EMAIL = "paper-downloader@example.com"  # Unpaywall requires an email


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class DownloadLog:
    """Collects log entries during download."""

    def __init__(self):
        self.entries: list[str] = []

    def log(self, msg: str):
        self.entries.append(msg)
        print(f"  [log] {msg}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(title: str) -> str:
    """Convert a paper title to a filesystem-safe directory name."""
    slug = re.sub(r"[^\w\s\-]", "", title.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug[:80]  # limit length


def _session() -> requests.Session:
    """Create a requests session with browser-like headers."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return s


# ---------------------------------------------------------------------------
# PDF Download — arXiv
# ---------------------------------------------------------------------------
def download_arxiv_pdf(pdf_url: str, save_path: str, log: DownloadLog) -> bool:
    """Download PDF directly from arXiv."""
    if not pdf_url:
        return False

    log.log(f"Trying arXiv PDF: {pdf_url}")
    try:
        # arXiv courtesy: wait 3 seconds
        time.sleep(1)
        r = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=60, stream=True)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower() and not pdf_url.endswith(".pdf"):
            # Sometimes arXiv returns HTML for bad URLs
            if b"%PDF" not in r.content[:10]:
                log.log(f"arXiv: response is not PDF (Content-Type: {content_type})")
                return False

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_mb = os.path.getsize(save_path) / (1024 * 1024)
        log.log(f"arXiv PDF downloaded: {size_mb:.1f} MB → {save_path}")
        return True

    except requests.RequestException as e:
        log.log(f"arXiv PDF download failed: {e}")
        return False


# ---------------------------------------------------------------------------
# PDF Download — Unpaywall (Open Access discovery)
# ---------------------------------------------------------------------------
def download_unpaywall_pdf(doi: str, save_path: str, log: DownloadLog) -> bool:
    """Try to find an open access PDF via Unpaywall API."""
    if not doi:
        return False

    log.log(f"Trying Unpaywall for DOI: {doi}")
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        # Find best OA location
        best_url = data.get("best_oa_location", {})
        pdf_url = best_url.get("url_for_pdf") or best_url.get("url")

        if not pdf_url:
            # Check other OA locations
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break

        if not pdf_url:
            log.log("Unpaywall: no open access PDF found")
            return False

        log.log(f"Unpaywall: found OA PDF at {pdf_url}")
        r = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=60, stream=True)
        r.raise_for_status()

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_mb = os.path.getsize(save_path) / (1024 * 1024)
        log.log(f"Unpaywall PDF downloaded: {size_mb:.1f} MB → {save_path}")
        return True

    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        log.log(f"Unpaywall failed: {e}")
        return False


# ---------------------------------------------------------------------------
# PDF Download — Sci-Hub (opt-in only)
# ---------------------------------------------------------------------------
def download_scihub_pdf(doi: str, save_path: str, log: DownloadLog) -> bool:
    """
    Try to download PDF from Sci-Hub using DOI.
    Only called when --allow-scihub is explicitly set.
    """
    if not doi:
        log.log("Sci-Hub: no DOI available, skipping")
        return False

    session = _session()

    for mirror in SCIHUB_MIRRORS:
        log.log(f"Sci-Hub: trying {mirror}/{doi}")
        try:
            # Method 1: direct DOI URL
            r = session.get(f"{mirror}/{doi}", timeout=30, allow_redirects=True)
            if r.status_code != 200:
                continue

            # Look for the PDF embed/iframe URL in the page
            # Sci-Hub typically embeds PDF in an iframe or has a direct link
            pdf_url = None

            # Pattern 1: iframe src with PDF
            m = re.search(r'<iframe[^>]+src="([^"]+\.pdf[^"]*)"', r.text, re.I)
            if m:
                pdf_url = m.group(1)

            # Pattern 2: embed src
            if not pdf_url:
                m = re.search(r'<embed[^>]+src="([^"]+\.pdf[^"]*)"', r.text, re.I)
                if m:
                    pdf_url = m.group(1)

            # Pattern 3: onclick or button with PDF URL
            if not pdf_url:
                m = re.search(r'(https?://[^\s"\'<>]+\.pdf)', r.text, re.I)
                if m:
                    pdf_url = m.group(1)

            # Pattern 4: relative /downloads/ path
            if not pdf_url:
                m = re.search(r'src="(/downloads/[^"]+)"', r.text, re.I)
                if m:
                    pdf_url = mirror + m.group(1)

            if not pdf_url:
                log.log(f"Sci-Hub ({mirror}): page loaded but no PDF URL found")
                continue

            # Fix protocol-relative URLs
            if pdf_url.startswith("//"):
                pdf_url = "https:" + pdf_url

            log.log(f"Sci-Hub: found PDF URL: {pdf_url}")
            pr = session.get(pdf_url, timeout=60, stream=True)
            pr.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in pr.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_mb = os.path.getsize(save_path) / (1024 * 1024)
            if size_mb < 0.01:  # Less than 10KB probably not a real PDF
                log.log(f"Sci-Hub: downloaded file too small ({size_mb:.3f} MB), likely invalid")
                os.remove(save_path)
                continue

            log.log(f"Sci-Hub PDF downloaded: {size_mb:.1f} MB → {save_path}")
            return True

        except requests.RequestException as e:
            log.log(f"Sci-Hub ({mirror}): error — {e}")
            continue

    log.log("Sci-Hub: all mirrors failed")
    return False


# ---------------------------------------------------------------------------
# Code Repository Clone
# ---------------------------------------------------------------------------
def clone_repo(
    repo_url: str,
    clone_dir: str,
    depth: int,
    log: DownloadLog,
) -> bool:
    """Clone a git repository."""
    if not repo_url:
        return False

    log.log(f"Cloning repository: {repo_url}")

    # Build git command
    cmd = ["git", "clone"]
    if depth > 0:
        cmd.extend(["--depth", str(depth)])
    cmd.extend([repo_url, clone_dir])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
        )
        if result.returncode == 0:
            # Count files
            file_count = sum(
                len(files) for _, _, files in os.walk(clone_dir)
            )
            log.log(f"Repository cloned: {file_count} files → {clone_dir}")

            # Check for dependency files
            dep_files = []
            for name in ["requirements.txt", "environment.yml", "setup.py",
                         "pyproject.toml", "Pipfile", "package.json",
                         "Makefile", "Dockerfile"]:
                path = os.path.join(clone_dir, name)
                if os.path.exists(path):
                    dep_files.append(name)
            if dep_files:
                log.log(f"Dependency files found: {', '.join(dep_files)}")

            return True
        else:
            log.log(f"Git clone failed: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        log.log("Git clone timed out (>5 min). Try --clone-depth 1 or skip large repos.")
        return False
    except FileNotFoundError:
        log.log("Error: 'git' command not found. Please install git.")
        return False


# ---------------------------------------------------------------------------
# Main Download Pipeline
# ---------------------------------------------------------------------------
def download_paper(
    paper_info_path: str,
    output_dir: str | None = None,
    allow_scihub: bool = False,
    clone_depth: int = 1,
    skip_code: bool = False,
    skip_pdf: bool = False,
) -> dict:
    """
    Main entry point. Reads paper_info.json and downloads PDF + code.
    Returns a download report dict.
    """
    log = DownloadLog()
    log.log("=== Paper Downloader started ===")

    # ------------------------------------------------------------------
    # Load paper info
    # ------------------------------------------------------------------
    if not os.path.exists(paper_info_path):
        log.log(f"Error: file not found: {paper_info_path}")
        return {"success": False, "error": "paper_info.json not found", "log": log.entries}

    with open(paper_info_path, "r", encoding="utf-8") as f:
        paper_info = json.load(f)

    if not paper_info.get("found"):
        log.log("Error: paper_info.json indicates no paper was found")
        return {"success": False, "error": "No paper found in paper_info.json", "log": log.entries}

    paper = paper_info["paper"]
    title = paper.get("title", "unknown-paper")
    arxiv_id = paper.get("arxiv_id")
    doi = paper.get("doi")
    pdf_url = paper.get("pdf_url")

    log.log(f"Paper: {title}")
    log.log(f"arXiv ID: {arxiv_id or 'N/A'}")
    log.log(f"DOI: {doi or 'N/A'}")

    # ------------------------------------------------------------------
    # Setup output directory
    # ------------------------------------------------------------------
    if not output_dir:
        slug = slugify(title)
        output_dir = os.path.join("workspace", slug)

    paper_dir = os.path.join(output_dir, "paper")
    code_dir = os.path.join(output_dir, "code")
    os.makedirs(paper_dir, exist_ok=True)
    os.makedirs(code_dir, exist_ok=True)

    log.log(f"Output directory: {output_dir}")

    # Copy paper_info.json to output
    info_dest = os.path.join(paper_dir, "paper_info.json")
    with open(info_dest, "w", encoding="utf-8") as f:
        json.dump(paper_info, f, indent=2, ensure_ascii=False)
    log.log(f"Saved paper_info.json → {info_dest}")

    report = {
        "success": True,
        "paper_title": title,
        "output_dir": output_dir,
        "pdf": {"downloaded": False, "path": None, "source": None},
        "code": {"cloned": False, "path": None, "repo_url": None},
        "log": [],
    }

    # ------------------------------------------------------------------
    # Download PDF
    # ------------------------------------------------------------------
    if not skip_pdf:
        pdf_path = os.path.join(paper_dir, "paper.pdf")
        pdf_downloaded = False

        # Priority 1: arXiv PDF
        if not pdf_downloaded and pdf_url:
            pdf_downloaded = download_arxiv_pdf(pdf_url, pdf_path, log)
            if pdf_downloaded:
                report["pdf"] = {"downloaded": True, "path": pdf_path, "source": "arxiv"}

        # Priority 2: Unpaywall (Open Access)
        if not pdf_downloaded and doi:
            pdf_downloaded = download_unpaywall_pdf(doi, pdf_path, log)
            if pdf_downloaded:
                report["pdf"] = {"downloaded": True, "path": pdf_path, "source": "unpaywall"}

        # Priority 3: Sci-Hub (opt-in)
        if not pdf_downloaded and allow_scihub:
            # Try with DOI first
            if doi:
                pdf_downloaded = download_scihub_pdf(doi, pdf_path, log)
            # Try with arXiv ID as fallback (some Sci-Hub mirrors accept it)
            if not pdf_downloaded and arxiv_id:
                pdf_downloaded = download_scihub_pdf(arxiv_id, pdf_path, log)
            if pdf_downloaded:
                report["pdf"] = {"downloaded": True, "path": pdf_path, "source": "scihub"}

        if not pdf_downloaded:
            log.log("⚠️ PDF download failed from all sources")
            if not allow_scihub and doi:
                log.log("TIP: Try adding --allow-scihub flag to use Sci-Hub as fallback")
    else:
        log.log("PDF download skipped (--skip-pdf)")

    # ------------------------------------------------------------------
    # Clone code repository
    # ------------------------------------------------------------------
    if not skip_code:
        repos = paper_info.get("code", {}).get("repositories", [])
        if repos:
            # Take the highest confidence repo
            best_repo = repos[0]
            repo_url = best_repo.get("url", "")
            confidence = best_repo.get("confidence", 0)
            is_official = best_repo.get("is_official", False)

            official_str = "Official" if is_official else "Unofficial"
            log.log(f"Best repo: {repo_url} ({official_str}, confidence: {confidence})")

            if repo_url:
                repo_name = repo_url.rstrip("/").split("/")[-1]
                repo_clone_dir = os.path.join(code_dir, repo_name)

                if os.path.exists(repo_clone_dir):
                    log.log(f"Repository directory already exists: {repo_clone_dir}, skipping clone")
                    report["code"] = {
                        "cloned": True,
                        "path": repo_clone_dir,
                        "repo_url": repo_url,
                    }
                else:
                    cloned = clone_repo(repo_url, repo_clone_dir, clone_depth, log)
                    if cloned:
                        report["code"] = {
                            "cloned": True,
                            "path": repo_clone_dir,
                            "repo_url": repo_url,
                        }
                    else:
                        log.log("⚠️ Repository clone failed")
        else:
            log.log("No code repositories found in paper_info.json")
    else:
        log.log("Code clone skipped (--skip-code)")

    # ------------------------------------------------------------------
    # Save download report
    # ------------------------------------------------------------------
    report["log"] = log.entries
    report_path = os.path.join(output_dir, "download_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.log(f"Download report saved → {report_path}")

    log.log("=== Download complete ===")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Download paper PDFs and clone source code repositories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "paper_info",
        help="Path to paper_info.json (output of search_paper.py)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory (default: workspace/<paper-slug>)",
    )
    parser.add_argument(
        "--allow-scihub",
        action="store_true",
        help="Enable Sci-Hub as a fallback PDF source",
    )
    parser.add_argument(
        "--clone-depth",
        type=int,
        default=1,
        help="Git clone depth (default: 1 for shallow clone, 0 for full)",
    )
    parser.add_argument(
        "--skip-code",
        action="store_true",
        help="Skip cloning code repositories",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip downloading paper PDF",
    )

    args = parser.parse_args()

    report = download_paper(
        paper_info_path=args.paper_info,
        output_dir=args.output_dir,
        allow_scihub=args.allow_scihub,
        clone_depth=args.clone_depth,
        skip_code=args.skip_code,
        skip_pdf=args.skip_pdf,
    )

    # Print summary
    print()
    if report.get("pdf", {}).get("downloaded"):
        src = report["pdf"]["source"]
        print(f"📄 PDF downloaded ({src}): {report['pdf']['path']}")
    else:
        print("📄 PDF: not downloaded")

    if report.get("code", {}).get("cloned"):
        print(f"💻 Code cloned: {report['code']['path']}")
        print(f"   From: {report['code']['repo_url']}")
    else:
        print("💻 Code: not cloned")

    print(f"\n📁 Output: {report.get('output_dir', 'N/A')}")

    return 0 if report.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
