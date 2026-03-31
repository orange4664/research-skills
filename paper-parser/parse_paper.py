#!/usr/bin/env python3
"""
parse_paper.py - Parse PDF papers into structured JSON using MinerU API.

Usage:
    python parse_paper.py <pdf_path_or_dir> [options]

Options:
    --output-dir <dir>     Output directory (default: same dir as PDF)
    --model <name>         Model version: vlm (default) or pipeline
    --token <token>        MinerU API token (or set MINERU_TOKEN env var)
    --timeout <seconds>    Polling timeout in seconds (default: 600)
    --language <lang>      OCR language hint: ch, en, etc. (default: en)

Workflow:
    1. Upload PDF via presigned URL to MinerU OSS
    2. Submit extraction task with vlm model
    3. Poll for completion
    4. Download result zip (contains markdown, images, structured JSON)
    5. Extract and organize outputs

Requires: MinerU API token from https://mineru.net/apiManage
"""

import argparse
import io
import json
import os
import re
import sys
import time
import zipfile

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MINERU_API_BASE = "https://mineru.net/api"
MINERU_V4_EXTRACT = f"{MINERU_API_BASE}/v4/extract/task"
MINERU_V4_BATCH_URLS = f"{MINERU_API_BASE}/v4/file-urls/batch"

DEFAULT_MODEL = "vlm"
DEFAULT_TIMEOUT = 600
DEFAULT_POLL_INTERVAL = 5
DEFAULT_LANGUAGE = "en"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class ParseLog:
    """Collects log entries during parsing."""

    def __init__(self):
        self.entries: list[str] = []

    def log(self, msg: str):
        self.entries.append(msg)
        print(f"  [log] {msg}")


# ---------------------------------------------------------------------------
# MinerU API Client
# ---------------------------------------------------------------------------
class MinerUClient:
    """Client for MinerU's precision extraction API (v4)."""

    def __init__(self, token: str, log: ParseLog):
        self.token = token
        self.log = log
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def _check_response(self, res: requests.Response, action: str) -> dict | None:
        """Check API response and return data or None on error."""
        try:
            data = res.json()
        except json.JSONDecodeError:
            self.log.log(f"{action}: invalid JSON response (HTTP {res.status_code})")
            return None

        if data.get("code") != 0:
            self.log.log(f"{action}: API error — {data.get('msg', 'unknown')}")
            return None

        return data

    # --- Method A: Upload file via presigned URL, then auto-parse ---
    def upload_and_parse(
        self,
        pdf_path: str,
        model: str = DEFAULT_MODEL,
        language: str = DEFAULT_LANGUAGE,
    ) -> str | None:
        """
        Upload a local PDF file to MinerU via presigned URL.
        Returns batch_id for polling.

        Flow:
        1. POST /api/v4/file-urls/batch → get presigned upload URL + batch_id
        2. PUT file to the presigned URL
        3. MinerU auto-starts parsing after upload
        """
        filename = os.path.basename(pdf_path)
        file_size = os.path.getsize(pdf_path)
        size_mb = file_size / (1024 * 1024)
        self.log.log(f"Uploading {filename} ({size_mb:.1f} MB) via presigned URL")

        # Step 1: Request presigned upload URL
        payload = {
            "files": [{"name": filename, "data_id": filename}],
            "model_version": model,
        }
        if language:
            payload["language"] = language

        try:
            res = requests.post(
                MINERU_V4_BATCH_URLS,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
        except requests.RequestException as e:
            self.log.log(f"Failed to request upload URL: {e}")
            return None

        data = self._check_response(res, "Request upload URL")
        if not data:
            return None

        batch_id = data["data"]["batch_id"]
        file_urls = data["data"]["file_urls"]

        if not file_urls:
            self.log.log("No upload URL returned")
            return None

        upload_url = file_urls[0]
        self.log.log(f"Got presigned URL, batch_id: {batch_id}")

        # Step 2: PUT file to presigned URL
        try:
            with open(pdf_path, "rb") as f:
                put_res = requests.put(upload_url, data=f, timeout=120)

            if put_res.status_code in (200, 201):
                self.log.log("File uploaded successfully")
            else:
                self.log.log(f"File upload failed: HTTP {put_res.status_code}")
                return None
        except requests.RequestException as e:
            self.log.log(f"File upload error: {e}")
            return None

        return batch_id

    # --- Method B: Submit URL for parsing (for non-blocked URLs) ---
    def submit_url(
        self,
        pdf_url: str,
        model: str = DEFAULT_MODEL,
    ) -> str | None:
        """
        Submit a PDF URL for extraction.
        Returns task_id for polling.
        NOTE: github/aws URLs will timeout due to China network restrictions.
        """
        self.log.log(f"Submitting URL for extraction: {pdf_url}")

        payload = {
            "url": pdf_url,
            "model_version": model,
        }

        try:
            res = requests.post(
                MINERU_V4_EXTRACT,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
        except requests.RequestException as e:
            self.log.log(f"Failed to submit URL: {e}")
            return None

        data = self._check_response(res, "Submit URL")
        if not data:
            return None

        task_id = data["data"]["task_id"]
        self.log.log(f"Task submitted, task_id: {task_id}")
        return task_id

    # --- Poll for task completion ---
    def poll_task(
        self,
        task_id: str,
        timeout: int = DEFAULT_TIMEOUT,
        interval: int = DEFAULT_POLL_INTERVAL,
    ) -> dict | None:
        """
        Poll a single task (from URL submission) until done.
        Returns result dict with full_zip_url on success.
        """
        url = f"{MINERU_V4_EXTRACT}/{task_id}"
        return self._poll(url, "task", timeout, interval)

    def poll_batch(
        self,
        batch_id: str,
        timeout: int = DEFAULT_TIMEOUT,
        interval: int = DEFAULT_POLL_INTERVAL,
    ) -> dict | None:
        """
        Poll a batch (from file upload) until all files are done.
        Returns first result dict with full_zip_url on success.
        """
        url = f"{MINERU_API_BASE}/v4/extract-results/batch/{batch_id}"
        return self._poll_batch(url, timeout, interval)

    def _poll(
        self, url: str, label: str, timeout: int, interval: int
    ) -> dict | None:
        """Generic poll for single task."""
        start = time.time()
        state_names = {
            "pending": "Queued",
            "running": "Parsing",
            "uploading": "Downloading file",
        }
        while time.time() - start < timeout:
            try:
                res = requests.get(url, headers=self.headers, timeout=30)
                data = res.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                self.log.log(f"Poll error: {e}")
                time.sleep(interval)
                continue

            if data.get("code") != 0:
                self.log.log(f"Poll error: {data.get('msg')}")
                time.sleep(interval)
                continue

            task_data = data["data"]
            state = task_data.get("state", "unknown")
            elapsed = int(time.time() - start)

            if state == "done":
                zip_url = task_data.get("full_zip_url", "")
                self.log.log(f"[{elapsed}s] Parsing complete!")
                return task_data

            if state == "failed":
                err = task_data.get("err_msg", "unknown error")
                self.log.log(f"[{elapsed}s] Parsing failed: {err}")
                return None

            # Progress info
            progress = task_data.get("extract_progress", {})
            extracted = progress.get("extracted_pages", "?")
            total = progress.get("total_pages", "?")
            status = state_names.get(state, state)
            self.log.log(f"[{elapsed}s] {status}... ({extracted}/{total} pages)")

            time.sleep(interval)

        self.log.log(f"Polling timed out after {timeout}s")
        return None

    def _poll_batch(
        self, url: str, timeout: int, interval: int
    ) -> dict | None:
        """Poll batch result until done."""
        start = time.time()
        state_names = {
            "pending": "Queued",
            "running": "Parsing",
            "uploading": "Downloading file",
        }
        while time.time() - start < timeout:
            try:
                res = requests.get(url, headers=self.headers, timeout=30)
                data = res.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                self.log.log(f"Poll error: {e}")
                time.sleep(interval)
                continue

            if data.get("code") != 0:
                self.log.log(f"Poll error: {data.get('msg')}")
                time.sleep(interval)
                continue

            batch_data = data["data"]
            results = batch_data.get("extract_result", [])
            elapsed = int(time.time() - start)

            if not results:
                self.log.log(f"[{elapsed}s] Waiting for results...")
                time.sleep(interval)
                continue

            # Check first result (we only submit one file)
            first = results[0]
            state = first.get("state", "unknown")

            if state == "done":
                self.log.log(f"[{elapsed}s] Parsing complete!")
                return first

            if state == "failed":
                err = first.get("err_msg", "unknown error")
                self.log.log(f"[{elapsed}s] Parsing failed: {err}")
                return None

            progress = first.get("extract_progress", {})
            extracted = progress.get("extracted_pages", "?")
            total = progress.get("total_pages", "?")
            status = state_names.get(state, state)
            self.log.log(f"[{elapsed}s] {status}... ({extracted}/{total} pages)")

            time.sleep(interval)

        self.log.log(f"Polling timed out after {timeout}s")
        return None


# ---------------------------------------------------------------------------
# Download and extract zip result
# ---------------------------------------------------------------------------
def download_and_extract_zip(
    zip_url: str,
    output_dir: str,
    log: ParseLog,
) -> bool:
    """Download the result zip and extract to output_dir."""
    log.log(f"Downloading results from: {zip_url}")
    try:
        r = requests.get(zip_url, timeout=120, stream=True)
        r.raise_for_status()

        zip_data = io.BytesIO()
        for chunk in r.iter_content(chunk_size=8192):
            zip_data.write(chunk)
        zip_data.seek(0)

        size_mb = zip_data.getbuffer().nbytes / (1024 * 1024)
        log.log(f"Downloaded zip: {size_mb:.1f} MB")

        with zipfile.ZipFile(zip_data) as zf:
            zf.extractall(output_dir)
            file_list = zf.namelist()
            log.log(f"Extracted {len(file_list)} files to {output_dir}")

            # Log key files
            for f in file_list:
                if f.endswith((".md", ".json", ".txt")):
                    log.log(f"  → {f}")

        return True

    except (requests.RequestException, zipfile.BadZipFile) as e:
        log.log(f"Download/extract error: {e}")
        return False


# ---------------------------------------------------------------------------
# Main Parse Pipeline
# ---------------------------------------------------------------------------
def parse_paper(
    pdf_path: str,
    output_dir: str | None = None,
    model: str = DEFAULT_MODEL,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """
    Main entry point. Parse a PDF paper using MinerU API.
    Returns a parse report dict.
    """
    log = ParseLog()
    log.log("=== Paper Parser started ===")

    # ------------------------------------------------------------------
    # Validate inputs
    # ------------------------------------------------------------------
    if not os.path.exists(pdf_path):
        log.log(f"Error: file not found: {pdf_path}")
        return {"success": False, "error": "PDF file not found", "log": log.entries}

    # Get token
    api_token = token or os.environ.get("MINERU_TOKEN")
    if not api_token:
        log.log("Error: MinerU API token not provided.")
        log.log("Set MINERU_TOKEN environment variable or use --token flag.")
        log.log("Get your token at: https://mineru.net/apiManage")
        return {"success": False, "error": "MinerU API token required", "log": log.entries}

    # Output dir
    if not output_dir:
        pdf_dir = os.path.dirname(os.path.abspath(pdf_path))
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = os.path.join(pdf_dir, f"{pdf_name}_parsed")

    os.makedirs(output_dir, exist_ok=True)
    log.log(f"PDF: {pdf_path}")
    log.log(f"Model: {model}")
    log.log(f"Output: {output_dir}")

    report = {
        "success": False,
        "pdf_path": pdf_path,
        "output_dir": output_dir,
        "model": model,
        "files": [],
        "log": [],
    }

    # ------------------------------------------------------------------
    # Upload and parse
    # ------------------------------------------------------------------
    client = MinerUClient(api_token, log)

    # Use file upload method (presigned URL)
    batch_id = client.upload_and_parse(pdf_path, model=model, language=language)
    if not batch_id:
        report["log"] = log.entries
        report["error"] = "Failed to upload file"
        return report

    # ------------------------------------------------------------------
    # Poll for completion
    # ------------------------------------------------------------------
    result = client.poll_batch(batch_id, timeout=timeout)
    if not result:
        report["log"] = log.entries
        report["error"] = "Parsing failed or timed out"
        return report

    # ------------------------------------------------------------------
    # Download and extract results
    # ------------------------------------------------------------------
    zip_url = result.get("full_zip_url")
    if not zip_url:
        log.log("No zip URL in result")
        report["log"] = log.entries
        report["error"] = "No result zip URL"
        return report

    success = download_and_extract_zip(zip_url, output_dir, log)
    if not success:
        report["log"] = log.entries
        report["error"] = "Failed to download/extract results"
        return report

    # ------------------------------------------------------------------
    # Catalog output files
    # ------------------------------------------------------------------
    output_files = []
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, output_dir)
            size = os.path.getsize(full)
            output_files.append({"path": rel, "size": size})

    report["success"] = True
    report["files"] = output_files
    report["zip_url"] = zip_url

    # Save report
    report["log"] = log.entries
    report_path = os.path.join(output_dir, "parse_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.log(f"Parse report saved → {report_path}")

    log.log("=== Parsing complete ===")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Parse PDF papers into structured data using MinerU API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory (default: <pdf_name>_parsed/)",
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        choices=["vlm", "pipeline"],
        help="MinerU model version (default: vlm)",
    )
    parser.add_argument(
        "--token", "-t",
        default=None,
        help="MinerU API token (or set MINERU_TOKEN env var)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Polling timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--language", "-l",
        default=DEFAULT_LANGUAGE,
        help="OCR language hint: en, ch, etc. (default: en)",
    )

    args = parser.parse_args()

    report = parse_paper(
        pdf_path=args.pdf,
        output_dir=args.output_dir,
        model=args.model,
        token=args.token,
        timeout=args.timeout,
        language=args.language,
    )

    # Print summary
    print()
    if report["success"]:
        print(f"✅ Parsing complete!")
        print(f"📁 Output: {report['output_dir']}")
        print(f"📄 Files extracted: {len(report['files'])}")
        for f in report["files"]:
            size_kb = f["size"] / 1024
            print(f"   {f['path']} ({size_kb:.1f} KB)")
    else:
        print(f"❌ Parsing failed: {report.get('error', 'unknown')}")

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
