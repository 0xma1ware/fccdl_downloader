#!/usr/bin/env python3
"""
Standalone fccdl.in scraper/downloader.

Usage:
    python3 /tmp/fccdl_scraper.py "https://fccdl.in/..."
    python3 /tmp/fccdl_scraper.py "https://fccdl.in/..." --output-dir /tmp/downloads
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx


TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def sanitize_filename(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(" .") or "download"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


async def resolve_mp3_url(page_url: str) -> tuple[str, Optional[str]]:
    """
    Given an fccdl.in page URL, return (direct_mp3_url, page_title_if_available).
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(page_url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        final_url = str(response.url)
        html = response.text

    qs = parse_qs(urlparse(final_url).query)
    storage_url = (qs.get("audioRecordingUrl") or qs.get("v") or [None])[0]
    if not storage_url:
        raise ValueError("Could not find audio storage URL on page. Check the URL.")

    mp3_url = unquote(storage_url) + ".mp3"

    title = None
    match = TITLE_RE.search(html)
    if match:
        title = match.group(1).strip()
        title = re.sub(
            r"\s*[-|]\s*(fccdl|freeconferencecall).*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip() or None

    return mp3_url, title


async def download_mp3(mp3_url: str, dest_path: Path) -> int:
    """Stream-download an mp3 file. Returns bytes written."""
    written = 0
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
        async with client.stream("GET", mp3_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))

            with dest_path.open("wb") as handle:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    handle.write(chunk)
                    written += len(chunk)
                    if total:
                        pct = written * 100 / total
                        msg = f"\rDownloading... {pct:5.1f}% ({written // 1024 // 1024} MB)"
                    else:
                        msg = f"\rDownloading... {written // 1024 // 1024} MB"
                    print(msg, end="", file=sys.stderr, flush=True)

    print(file=sys.stderr)
    return written


def choose_output_path(mp3_url: str, title: Optional[str], output_dir: Path) -> Path:
    if title:
        filename = sanitize_filename(title)
        if not filename.lower().endswith(".mp3"):
            filename += ".mp3"
    else:
        parsed_name = Path(urlparse(mp3_url).path).name or "download.mp3"
        filename = sanitize_filename(parsed_name)
        if not filename.lower().endswith(".mp3"):
            filename += ".mp3"

    return unique_path(output_dir / filename)


async def main_async(url: str, output_dir: Path) -> int:
    host = (urlparse(url).hostname or "").lower()
    if host != "fccdl.in" and not host.endswith(".fccdl.in"):
        raise ValueError("Only fccdl.in URLs are accepted.")

    mp3_url, title = await resolve_mp3_url(url)
    dest_path = choose_output_path(mp3_url, title, output_dir)

    print(f"Resolved mp3 URL: {mp3_url}", file=sys.stderr)
    print(f"Saving to: {dest_path}", file=sys.stderr)
    written = await download_mp3(mp3_url, dest_path)

    try:
        os.chmod(dest_path, 0o666)
    except OSError:
        pass

    print(dest_path)
    print(f"Downloaded {written} bytes.", file=sys.stderr)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the mp3 behind an fccdl.in URL.")
    parser.add_argument("url", help="fccdl.in page URL")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Directory to save the downloaded file into. Defaults to the current directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(main_async(args.url, Path(args.output_dir).expanduser().resolve()))
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
