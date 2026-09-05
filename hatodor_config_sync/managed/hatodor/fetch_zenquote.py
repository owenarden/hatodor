#!/usr/bin/env python3
"""Fetch and cache one ZenQuotes message for the current dashboard day."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen


API_URL = "https://zenquotes.io/api/today"
CACHE_PATH = Path("/config/hatodor/zenquote_cache.json")
DOWNLOAD_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 256 * 1024
MAX_MESSAGE_CHARACTERS = 255


def decode_argument(value: str) -> str:
    return base64.b64decode(value, validate=True).decode("utf-8")


def parse_quote(payload: bytes) -> tuple[str, str]:
    result = json.loads(payload)
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        raise ValueError("ZenQuotes did not return a quote")
    quote = str(result[0].get("q", "")).strip()
    author = str(result[0].get("a", "")).strip()
    if not quote or not author:
        raise ValueError("ZenQuotes returned an incomplete quote")
    return quote, author


def fetch_quote() -> tuple[str, str]:
    request = Request(
        API_URL,
        headers={
            "User-Agent": "Hatodor-MOTD/0.9",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type != "application/json":
            raise ValueError(f"ZenQuotes returned {content_type}, not JSON")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("ZenQuotes response is larger than 256 KiB")
    return parse_quote(payload)


def read_cache(path: Path = CACHE_PATH) -> dict[str, str] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(value, dict):
        return None
    day = str(value.get("day", "")).strip()
    quote = str(value.get("quote", "")).strip()
    author = str(value.get("author", "")).strip()
    if not day or not quote or not author:
        return None
    return {"day": day, "quote": quote, "author": author}


def write_cache(day: str, quote: str, author: str, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(
        json.dumps(
            {"day": day, "quote": quote, "author": author},
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def get_daily_quote(day: str, path: Path = CACHE_PATH) -> tuple[str, str]:
    cached = read_cache(path)
    if cached is not None and cached["day"] == day:
        return cached["quote"], cached["author"]
    try:
        quote, author = fetch_quote()
    except Exception:
        if cached is not None:
            return cached["quote"], cached["author"]
        raise
    write_cache(day, quote, author, path)
    return quote, author


def format_message(
    quote: str,
    author: str,
    name: str = "Maggie",
    max_characters: int = MAX_MESSAGE_CHARACTERS,
) -> str:
    author = author[:60].strip()
    prefix = f"Good morning, {name}!\n\n\""
    suffix = f"\"\n- {author}\n\nzenquotes.io"
    available = max_characters - len(prefix) - len(suffix)
    if available < 4:
        raise ValueError("morning-message limit is too small")
    if len(quote) > available:
        shortened = quote[: available - 3].rsplit(" ", 1)[0].rstrip(" ,;:-")
        quote = (shortened or quote[: available - 3]).rstrip() + "..."
    return prefix + quote + suffix


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise ValueError("expected one base64 dashboard-day argument")
    day = decode_argument(argv[1]).strip()
    if len(day) != 10:
        raise ValueError("dashboard day must use YYYY-MM-DD")
    quote, author = get_daily_quote(day)
    print(
        json.dumps(
            {"text": format_message(quote, author), "quote": quote, "author": author},
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as error:
        print(f"Could not prepare morning ZenQuote: {error}", file=sys.stderr)
        raise SystemExit(1)
