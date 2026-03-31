#!/usr/bin/env python3
"""
search_paper.py - Multi-source academic paper & code finder

Usage:
    python search_paper.py <query> [--output <path>]

Query formats:
    - arXiv ID:    "1706.03762" or "2301.12345"
    - arXiv URL:   "https://arxiv.org/abs/1706.03762"
    - DOI:         "10.5555/3295222.3295349"
    - Paper title: "Attention Is All You Need"
    - PDF path:    "/path/to/paper.pdf" (extracts title from filename)

Data sources (in order):
    1. arXiv API          - metadata + PDF links
    2. Semantic Scholar   - cross-references, journal DOI, citation count
    3. HuggingFace Papers - paper → GitHub repo mapping
    4. GitHub Search API  - fallback repo search

Output: paper_info.json with paper metadata, code repos, and search log.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from xml.etree import ElementTree

# ---------------------------------------------------------------------------
# Optional dependency check
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------
ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
HF_PAPERS_SEARCH = "https://huggingface.co/api/papers/search"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # optional

USER_AGENT = "paper-finder/1.0 (academic research tool)"

# Rate limiting helpers
_last_arxiv_call = 0.0
_last_s2_call = 0.0

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class SearchLog:
    """Collects human-readable log entries during a search session."""

    def __init__(self):
        self.entries: list[str] = []

    def log(self, msg: str):
        self.entries.append(msg)
        print(f"  [log] {msg}")


# ---------------------------------------------------------------------------
# Step 0 - Input Parser
# ---------------------------------------------------------------------------
def parse_input(query: str, log: SearchLog) -> dict:
    """
    Detect the input type and return a normalized dict.

    Returns dict with keys:
        type:  "arxiv_id" | "doi" | "title" | "pdf_path"
        value: the cleaned value
    """
    q = query.strip()

    # 1. arXiv URL  →  extract ID
    m = re.match(
        r"https?://(?:arxiv\.org|export\.arxiv\.org)/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)",
        q,
    )
    if m:
        arxiv_id = re.sub(r"v\d+$", "", m.group(1))  # strip version
        log.log(f"Parsed input as arXiv URL → ID: {arxiv_id}")
        return {"type": "arxiv_id", "value": arxiv_id}

    # 2. Pure arXiv ID  (e.g. 1706.03762 or 2301.12345)
    m = re.match(r"^(\d{4}\.\d{4,5})(?:v\d+)?$", q)
    if m:
        arxiv_id = m.group(1)
        log.log(f"Parsed input as arXiv ID: {arxiv_id}")
        return {"type": "arxiv_id", "value": arxiv_id}

    # 3. DOI  (starts with 10.xxxx/)
    m = re.match(r"^(10\.\d{4,}/\S+)$", q)
    if m:
        log.log(f"Parsed input as DOI: {q}")
        return {"type": "doi", "value": q}

    # 4. DOI URL
    m = re.match(r"https?://(?:dx\.)?doi\.org/(10\.\d{4,}/\S+)", q)
    if m:
        doi = m.group(1)
        log.log(f"Parsed input as DOI URL → DOI: {doi}")
        return {"type": "doi", "value": doi}

    # 5. Local PDF path (fallback – use filename as title hint)
    if q.lower().endswith(".pdf") and os.path.exists(q):
        name = os.path.splitext(os.path.basename(q))[0]
        # Very rough: replace underscores/hyphens with spaces
        title_hint = re.sub(r"[_\-]+", " ", name).strip()
        log.log(f"Parsed input as PDF path, title hint: '{title_hint}'")
        return {"type": "title", "value": title_hint}

    # 6. Default: treat as title string
    log.log(f"Parsed input as title: '{q}'")
    return {"type": "title", "value": q}


# ---------------------------------------------------------------------------
# API Helpers
# ---------------------------------------------------------------------------
def _rate_limit_arxiv():
    """Enforce ≥3 s between arXiv requests (courtesy)."""
    global _last_arxiv_call
    elapsed = time.time() - _last_arxiv_call
    if elapsed < 3.0:
        time.sleep(3.0 - elapsed)
    _last_arxiv_call = time.time()


def _rate_limit_s2():
    """Enforce ≥3 s between Semantic Scholar requests."""
    global _last_s2_call
    elapsed = time.time() - _last_s2_call
    if elapsed < 3.0:
        time.sleep(3.0 - elapsed)
    _last_s2_call = time.time()


def _github_headers() -> dict:
    h = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": USER_AGENT,
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


# ---------------------------------------------------------------------------
# arXiv API
# ---------------------------------------------------------------------------
def arxiv_search_by_id(arxiv_id: str, log: SearchLog) -> dict | None:
    """Fetch paper metadata from arXiv by ID."""
    _rate_limit_arxiv()
    log.log(f"arXiv API: querying id_list={arxiv_id}")
    try:
        r = requests.get(
            ARXIV_API,
            params={"id_list": arxiv_id, "max_results": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        log.log(f"arXiv API error: {e}")
        return None

    root = ElementTree.fromstring(r.text)
    entries = root.findall("atom:entry", ARXIV_NS)
    if not entries:
        log.log("arXiv API: no entry found")
        return None

    entry = entries[0]
    title = entry.findtext("atom:title", "", ARXIV_NS).strip().replace("\n", " ")
    # Deduplicate whitespace
    title = re.sub(r"\s+", " ", title)

    # Check for error (<title>Error</title>)
    if title.lower() == "error":
        log.log("arXiv API: returned error (invalid ID?)")
        return None

    abstract = entry.findtext("atom:summary", "", ARXIV_NS).strip()
    abstract = re.sub(r"\s+", " ", abstract)

    authors = [
        a.findtext("atom:name", "", ARXIV_NS)
        for a in entry.findall("atom:author", ARXIV_NS)
    ]

    published = entry.findtext("atom:published", "", ARXIV_NS)[:10]
    year = int(published[:4]) if published else None

    # PDF link
    pdf_url = None
    for link in entry.findall("atom:link", ARXIV_NS):
        if link.get("title") == "pdf":
            pdf_url = link.get("href")
            break
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # Comment field (may contain "code available at ...")
    comment = entry.findtext("atom:comment", "", ARXIV_NS).strip() if entry.find("atom:comment", ARXIV_NS) is not None else ""

    log.log(f"arXiv API: found '{title}' ({published})")
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "published": published,
        "comment": comment,
    }


def arxiv_search_by_title(title: str, log: SearchLog) -> dict | None:
    """Search arXiv by title (best effort, returns first match)."""
    _rate_limit_arxiv()
    query = f'ti:"{title}"'
    log.log(f"arXiv API: searching title '{title}'")
    try:
        r = requests.get(
            ARXIV_API,
            params={"search_query": query, "max_results": 3, "sortBy": "relevance"},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        log.log(f"arXiv API title search error: {e}")
        return None

    root = ElementTree.fromstring(r.text)
    entries = root.findall("atom:entry", ARXIV_NS)
    if not entries:
        log.log("arXiv API title search: no results")
        return None

    # Take best match
    for entry in entries:
        etitle = entry.findtext("atom:title", "", ARXIV_NS).strip()
        etitle = re.sub(r"\s+", " ", etitle)
        if etitle.lower() == "error":
            continue

        # Extract arXiv ID from entry id URL
        entry_url = entry.findtext("atom:id", "", ARXIV_NS)
        m = re.search(r"(\d{4}\.\d{4,5})", entry_url)
        if not m:
            continue
        aid = m.group(1)

        authors = [
            a.findtext("atom:name", "", ARXIV_NS)
            for a in entry.findall("atom:author", ARXIV_NS)
        ]
        abstract = re.sub(
            r"\s+", " ", entry.findtext("atom:summary", "", ARXIV_NS).strip()
        )
        published = entry.findtext("atom:published", "", ARXIV_NS)[:10]
        year = int(published[:4]) if published else None

        pdf_url = None
        for link in entry.findall("atom:link", ARXIV_NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{aid}.pdf"

        comment = entry.findtext("atom:comment", "", ARXIV_NS) or ""
        comment = comment.strip()

        log.log(f"arXiv API: best match '{etitle}' (ID: {aid})")
        return {
            "title": etitle,
            "authors": authors,
            "year": year,
            "abstract": abstract,
            "arxiv_id": aid,
            "pdf_url": pdf_url,
            "published": published,
            "comment": comment,
        }

    log.log("arXiv API title search: no valid entries")
    return None


# ---------------------------------------------------------------------------
# Semantic Scholar API
# ---------------------------------------------------------------------------
def s2_search_by_title(title: str, log: SearchLog) -> dict | None:
    """Search Semantic Scholar by title."""
    _rate_limit_s2()
    log.log(f"Semantic Scholar: searching title '{title}'")
    try:
        r = requests.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/search",
            params={
                "query": title,
                "limit": 5,
                "fields": "title,authors,year,externalIds,venue,citationCount,abstract,url",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.log(f"Semantic Scholar search error: {e}")
        return None

    papers = data.get("data", [])
    if not papers:
        log.log("Semantic Scholar: no results")
        return None

    # Pick best match by title similarity
    best = papers[0]
    log.log(
        f"Semantic Scholar: found '{best.get('title')}' "
        f"(citations: {best.get('citationCount', '?')})"
    )
    return best


def s2_get_paper(paper_id: str, log: SearchLog) -> dict | None:
    """
    Get paper details from Semantic Scholar by various ID formats.
    paper_id examples: "ARXIV:1706.03762", "DOI:10.xxxx/...", "CorpusID:xxx"
    """
    _rate_limit_s2()
    log.log(f"Semantic Scholar: fetching paper {paper_id}")
    try:
        r = requests.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}",
            params={
                "fields": "title,authors,year,externalIds,venue,citationCount,abstract,url",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        if r.status_code == 404:
            log.log(f"Semantic Scholar: paper not found ({paper_id})")
            return None
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.log(f"Semantic Scholar fetch error: {e}")
        return None


def s2_extract_info(s2_paper: dict, log: SearchLog) -> dict:
    """Extract normalized info from a Semantic Scholar paper object."""
    ext_ids = s2_paper.get("externalIds") or {}
    doi = ext_ids.get("DOI")
    arxiv_id = ext_ids.get("ArXiv")
    venue = s2_paper.get("venue", "")
    citation_count = s2_paper.get("citationCount")
    year = s2_paper.get("year")
    title = s2_paper.get("title", "")
    abstract = s2_paper.get("abstract", "")
    authors = [a.get("name", "") for a in (s2_paper.get("authors") or [])]
    url = s2_paper.get("url", "")

    journal_url = f"https://doi.org/{doi}" if doi else None

    if doi:
        log.log(f"Semantic Scholar: journal DOI = {doi}")
    if venue:
        log.log(f"Semantic Scholar: venue = {venue}")

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "arxiv_id": arxiv_id,
        "doi": doi,
        "venue": venue,
        "citation_count": citation_count,
        "journal_url": journal_url,
        "s2_url": url,
    }


# ---------------------------------------------------------------------------
# HuggingFace Papers API
# ---------------------------------------------------------------------------
def hf_search_paper(query: str, log: SearchLog) -> dict | None:
    """
    Search HuggingFace Papers.
    Works best with arXiv IDs as query, but also accepts titles.
    Returns the first matching paper dict (with potential githubRepo field).
    """
    log.log(f"HuggingFace Papers: searching '{query}'")
    try:
        r = requests.get(
            HF_PAPERS_SEARCH,
            params={"q": query, "limit": 5},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.log(f"HuggingFace Papers error: {e}")
        return None

    if not results:
        log.log("HuggingFace Papers: no results")
        return None

    # Each result has a nested "paper" object (for search endpoint)
    # or is flat (for other endpoints). Handle both.
    for item in results:
        paper = item.get("paper", item)
        github_repo = item.get("githubRepo") or paper.get("githubRepo")
        project_page = item.get("projectPage") or paper.get("projectPage")

        hf_id = paper.get("id", "")
        hf_title = paper.get("title", "")

        log.log(
            f"HuggingFace Papers: found '{hf_title}' "
            f"(ID: {hf_id}, repo: {github_repo or 'none'})"
        )
        return {
            "hf_id": hf_id,
            "title": hf_title,
            "githubRepo": github_repo,
            "projectPage": project_page,
        }

    return None


# ---------------------------------------------------------------------------
# GitHub Search API
# ---------------------------------------------------------------------------
def github_search_repos(
    title: str, authors: list[str], log: SearchLog
) -> list[dict]:
    """
    Search GitHub for repositories matching the paper.
    Returns a list of candidate repo dicts.
    """
    # Build search query: use paper title keywords + first author last name
    keywords = re.sub(r"[^\w\s]", "", title).strip()
    # Limit to first ~6 words to avoid too-specific queries
    words = keywords.split()[:6]
    q = " ".join(words)

    # Add first author's last name if available
    if authors:
        last_name = authors[0].split()[-1]
        q += f" {last_name}"

    log.log(f"GitHub Search: query='{q}'")
    try:
        r = requests.get(
            GITHUB_SEARCH_API,
            params={"q": q, "sort": "stars", "order": "desc", "per_page": 10},
            headers=_github_headers(),
            timeout=15,
        )
        if r.status_code == 403:
            log.log("GitHub Search: rate limited (consider setting GITHUB_TOKEN)")
            return []
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.log(f"GitHub Search error: {e}")
        return []

    items = data.get("items", [])
    log.log(f"GitHub Search: {len(items)} results")

    repos = []
    for item in items[:10]:
        repos.append(
            {
                "url": item.get("html_url", ""),
                "full_name": item.get("full_name", ""),
                "description": item.get("description") or "",
                "stars": item.get("stargazers_count", 0),
                "created_at": item.get("created_at", ""),
                "owner": item.get("owner", {}).get("login", ""),
                "language": item.get("language", ""),
            }
        )
    return repos


# ---------------------------------------------------------------------------
# Extract GitHub URLs from text (abstract, comment)
# ---------------------------------------------------------------------------
def extract_github_urls(text: str) -> list[str]:
    """Find all github.com URLs in a text string."""
    pattern = r"https?://github\.com/[\w\-\.]+/[\w\-\.]+"
    return list(set(re.findall(pattern, text)))


# ---------------------------------------------------------------------------
# Repo Confidence Scoring
# ---------------------------------------------------------------------------
def score_repo(
    repo: dict,
    paper_title: str,
    paper_authors: list[str],
    paper_year: int | None,
    source: str,
    log: SearchLog,
) -> dict:
    """
    Score a candidate repository for how likely it is the official code.

    Returns an enriched repo dict with:
        confidence: float [0, 1]
        is_official: bool
        reason: str
    """
    score = 0.0
    reasons = []

    title_lower = paper_title.lower()
    desc_lower = (repo.get("description") or "").lower()
    full_name_lower = repo.get("full_name", "").lower()

    # Source-based trust
    if source == "hf_papers":
        score += 0.45
        reasons.append("HuggingFace Papers githubRepo field")
    elif source == "abstract_url":
        score += 0.50
        reasons.append("URL found in paper abstract/comments")

    # Title match in description
    # Check for significant title keywords (>= 3 chars each) in description
    title_words = [w.lower() for w in re.findall(r"\w{3,}", paper_title)]
    if title_words:
        match_count = sum(1 for w in title_words if w in desc_lower)
        match_ratio = match_count / len(title_words)
        if match_ratio >= 0.5:
            score += 0.20
            reasons.append(f"Description matches {match_count}/{len(title_words)} title words")

    # Also check full_name (owner/repo)
    repo_name = full_name_lower.split("/")[-1] if "/" in full_name_lower else full_name_lower
    # Short title keyword match in repo name
    short_title_words = [w.lower() for w in re.findall(r"\w{4,}", paper_title)]
    if short_title_words:
        name_matches = sum(1 for w in short_title_words if w in repo_name)
        if name_matches >= 1:
            score += 0.15
            reasons.append(f"Repo name contains title keywords")

    # Author match
    if paper_authors:
        first_author_last = paper_authors[0].split()[-1].lower()
        owner_lower = repo.get("owner", "").lower()
        if first_author_last in owner_lower:
            score += 0.15
            reasons.append(f"Owner matches first author ({first_author_last})")

    # Star count as quality signal
    stars = repo.get("stars", 0)
    if stars >= 100:
        score += 0.05
        reasons.append(f"High star count ({stars})")
    elif stars >= 10:
        score += 0.02

    # Year proximity
    if paper_year and repo.get("created_at"):
        try:
            repo_year = int(repo["created_at"][:4])
            if abs(repo_year - paper_year) <= 1:
                score += 0.10
                reasons.append(f"Created {repo_year}, paper published {paper_year}")
        except (ValueError, IndexError):
            pass

    confidence = min(score, 1.0)
    is_official = confidence >= 0.50

    reason_str = "; ".join(reasons) if reasons else "Low confidence match"
    log.log(
        f"  Repo {repo.get('full_name')}: confidence={confidence:.2f}, "
        f"official={is_official} ({reason_str})"
    )

    return {
        "url": repo.get("url", ""),
        "stars": stars,
        "description": repo.get("description", ""),
        "language": repo.get("language", ""),
        "is_official": is_official,
        "source": source,
        "confidence": round(confidence, 2),
        "reason": reason_str,
    }


# ---------------------------------------------------------------------------
# Main Search Pipeline
# ---------------------------------------------------------------------------
def search_paper(query: str) -> dict:
    """
    Main entry point. Accepts any supported query format.
    Returns a structured result dict.
    """
    log = SearchLog()
    log.log(f"=== Paper Finder started ===")
    log.log(f"Query: {query}")

    # ------------------------------------------------------------------
    # Step 0 – Parse input
    # ------------------------------------------------------------------
    parsed = parse_input(query, log)
    input_type = parsed["type"]
    input_value = parsed["value"]

    # We'll accumulate paper metadata from multiple sources
    paper_info = {
        "title": "",
        "authors": [],
        "year": None,
        "abstract": "",
        "arxiv_id": None,
        "doi": None,
        "pdf_url": None,
        "venue": "",
        "citation_count": None,
        "journal_url": None,
    }
    all_repos: list[dict] = []

    # ------------------------------------------------------------------
    # Step 1 – Get paper metadata
    # ------------------------------------------------------------------
    s2_paper = None

    if input_type == "arxiv_id":
        # Try arXiv first
        arxiv_data = arxiv_search_by_id(input_value, log)
        if arxiv_data:
            paper_info.update(
                {k: v for k, v in arxiv_data.items() if v and k in paper_info}
            )
            paper_info["arxiv_id"] = input_value

        # Enrich with Semantic Scholar
        s2_paper = s2_get_paper(f"ARXIV:{input_value}", log)

    elif input_type == "doi":
        # Semantic Scholar by DOI
        s2_paper = s2_get_paper(f"DOI:{input_value}", log)
        if not s2_paper:
            # fallback: Semantic Scholar title search
            s2_paper = s2_search_by_title(input_value, log)

    elif input_type == "title":
        # Try Semantic Scholar first (faster, richer)
        s2_paper = s2_search_by_title(input_value, log)

        # If we found an arXiv ID from S2, fetch arXiv data too
        if s2_paper:
            ext_ids = (s2_paper.get("externalIds") or {})
            arxiv_id_from_s2 = ext_ids.get("ArXiv")
            if arxiv_id_from_s2:
                arxiv_data = arxiv_search_by_id(arxiv_id_from_s2, log)
                if arxiv_data:
                    paper_info.update(
                        {k: v for k, v in arxiv_data.items() if v and k in paper_info}
                    )
        else:
            # Fallback: direct arXiv title search
            arxiv_data = arxiv_search_by_title(input_value, log)
            if arxiv_data:
                paper_info.update(
                    {k: v for k, v in arxiv_data.items() if v and k in paper_info}
                )
                # Try S2 again with the arXiv ID we found
                if arxiv_data.get("arxiv_id"):
                    s2_paper = s2_get_paper(
                        f"ARXIV:{arxiv_data['arxiv_id']}", log
                    )

    # Merge Semantic Scholar data
    if s2_paper:
        s2_info = s2_extract_info(s2_paper, log)
        # Only fill in missing fields
        for k, v in s2_info.items():
            if k in paper_info and v and not paper_info.get(k):
                paper_info[k] = v

    # ------------------------------------------------------------------
    # Step 2 – Search for code repositories
    # ------------------------------------------------------------------
    title = paper_info.get("title", "")
    authors = paper_info.get("authors", [])
    arxiv_id = paper_info.get("arxiv_id")
    year = paper_info.get("year")

    if not title and not arxiv_id:
        log.log("WARNING: Could not find paper metadata. Cannot search for code.")
        return _build_result(query, paper_info, [], log)

    # --- 2a. Check abstract / comments for GitHub URLs ---
    abstract = paper_info.get("abstract", "")
    comment = paper_info.get("comment", "")
    text_to_scan = f"{abstract} {comment}"
    github_urls_in_text = extract_github_urls(text_to_scan)
    if github_urls_in_text:
        log.log(f"Found {len(github_urls_in_text)} GitHub URL(s) in abstract/comments")
        for url in github_urls_in_text:
            all_repos.append(
                score_repo(
                    {"url": url, "description": "", "owner": "", "stars": 0, "full_name": url.replace("https://github.com/", "")},
                    title,
                    authors,
                    year,
                    "abstract_url",
                    log,
                )
            )

    # --- 2b. HuggingFace Papers ---
    hf_query = arxiv_id if arxiv_id else title
    hf_result = hf_search_paper(hf_query, log)
    if hf_result and hf_result.get("githubRepo"):
        repo_url = hf_result["githubRepo"]
        # Check if already found from abstract
        existing_urls = {r["url"] for r in all_repos}
        if repo_url not in existing_urls:
            full_name = repo_url.replace("https://github.com/", "")
            all_repos.append(
                score_repo(
                    {"url": repo_url, "description": "", "owner": full_name.split("/")[0] if "/" in full_name else "", "stars": 0, "full_name": full_name},
                    title,
                    authors,
                    year,
                    "hf_papers",
                    log,
                )
            )

    # --- 2c. GitHub Search (fallback if no repos yet, or supplement) ---
    if title:
        gh_repos = github_search_repos(title, authors, log)
        existing_urls = {r["url"] for r in all_repos}
        for repo in gh_repos:
            if repo["url"] not in existing_urls:
                scored = score_repo(repo, title, authors, year, "github_search", log)
                # Only include repos with some relevance
                if scored["confidence"] >= 0.15:
                    all_repos.append(scored)

    # ------------------------------------------------------------------
    # Step 3 – Sort repos by confidence and build output
    # ------------------------------------------------------------------
    all_repos.sort(key=lambda r: r["confidence"], reverse=True)

    # Limit to top 5
    all_repos = all_repos[:5]

    log.log(f"=== Search complete. {len(all_repos)} repos found ===")
    return _build_result(query, paper_info, all_repos, log)


def _build_result(
    query: str, paper_info: dict, repos: list[dict], log: SearchLog
) -> dict:
    """Assemble the final output dict."""
    # Clean up: remove internal-only fields
    paper_out = {
        "title": paper_info.get("title", ""),
        "authors": paper_info.get("authors", []),
        "year": paper_info.get("year"),
        "abstract": paper_info.get("abstract", ""),
        "arxiv_id": paper_info.get("arxiv_id"),
        "doi": paper_info.get("doi"),
        "pdf_url": paper_info.get("pdf_url"),
        "venue": paper_info.get("venue", ""),
        "citation_count": paper_info.get("citation_count"),
        "journal_url": paper_info.get("journal_url"),
    }

    return {
        "query": query,
        "found": bool(paper_out["title"]),
        "paper": paper_out,
        "code": {
            "found": len(repos) > 0,
            "repositories": repos,
        },
        "search_log": log.entries,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Search for academic papers and their source code repositories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", help="arXiv ID, DOI, URL, or paper title")
    parser.add_argument(
        "--output",
        "-o",
        default="paper_info.json",
        help="Output JSON file path (default: paper_info.json)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )

    args = parser.parse_args()

    result = search_paper(args.query)

    # Write output
    indent = 2 if args.pretty else None
    output_path = args.output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=indent, ensure_ascii=False)

    print(f"\n✅ Results saved to: {output_path}")

    # Print summary
    p = result["paper"]
    if result["found"]:
        print(f"📄 Paper: {p['title']}")
        if p.get("arxiv_id"):
            print(f"   arXiv: {p['arxiv_id']}")
        if p.get("doi"):
            print(f"   DOI:   {p['doi']}")
        if p.get("venue"):
            print(f"   Venue: {p['venue']}")
        if p.get("citation_count"):
            print(f"   Citations: {p['citation_count']}")
    else:
        print("❌ Paper not found")

    if result["code"]["found"]:
        print(f"\n💻 Found {len(result['code']['repositories'])} code repo(s):")
        for repo in result["code"]["repositories"]:
            official = "✅ Official" if repo["is_official"] else "⚠️  Unofficial"
            print(
                f"   {official} [{repo['confidence']:.0%}] {repo['url']} "
                f"(⭐ {repo['stars']}) [{repo['source']}]"
            )
    else:
        print("\n💻 No code repositories found")

    return 0 if result["found"] else 1


if __name__ == "__main__":
    sys.exit(main())
