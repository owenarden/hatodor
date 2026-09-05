#!/usr/bin/env python3
"""Render a daily cat saying from a dynamic CATAAS image endpoint."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageOps


WIDTH = 800
HEIGHT = 480
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 20
SAYINGS_PATH = Path("/config/hatodor/cat_sayings.json")
OUTPUT_DIR = Path("/config/www/hatodor/motd-cache")
PUBLIC_PREFIX = "/local/hatodor/motd-cache"
KEEP_RENDERED_IMAGES = 20


def decode_argument(value: str) -> str:
    return base64.b64decode(value, validate=True).decode("utf-8")


def load_sayings(path: Path = SAYINGS_PATH) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8") as handle:
        pools = json.load(handle)

    if not isinstance(pools, dict) or not pools:
        raise ValueError("cat sayings file must contain at least one tone")

    cleaned: dict[str, list[str]] = {}
    for raw_tone, raw_sayings in pools.items():
        tone = str(raw_tone).strip().lower()
        if not tone or not isinstance(raw_sayings, list):
            continue
        sayings = [str(item).strip() for item in raw_sayings if str(item).strip()]
        if sayings:
            cleaned[tone] = sayings

    if not cleaned:
        raise ValueError("cat sayings file does not contain any usable sayings")
    return cleaned


def select_saying(pools: dict[str, list[str]], tone: str, day: str) -> str:
    normalized_tone = tone.strip().lower().replace(" ", "_")
    if normalized_tone == "mixed":
        pool = [saying for values in pools.values() for saying in values]
    else:
        if normalized_tone not in pools:
            available = ", ".join(sorted(pools))
            raise ValueError(f"unknown cat-saying tone {tone!r}; choose {available} or Mixed")
        pool = pools[normalized_tone]

    digest = hashlib.sha256(f"{day}:{normalized_tone}".encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % len(pool)
    return pool[index]


def build_cataas_says_url(source_url: str, saying: str, revision: str) -> str:
    parsed = urlsplit(source_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("image URL must start with http:// or https://")
    if not parsed.hostname or parsed.hostname.lower() not in {"cataas.com", "www.cataas.com"}:
        raise ValueError("cat MOTD source must be a cataas.com URL")

    path = parsed.path.rstrip("/")
    if path in {"", "/cat"}:
        path = "/cat"
    elif not path.startswith("/cat/") or "/says/" in path or path.endswith("/gif"):
        raise ValueError("use a CATAAS random image endpoint such as https://cataas.com/cat")

    path = f"{path}/says/{quote(saying, safe='')}"
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "width": str(WIDTH),
            "height": str(HEIGHT),
            "fit": "cover",
            "position": "center",
            "filter": "mono",
            "fontSize": "36",
            "fontColor": "white",
            "fontBackground": "black",
            "hatodor": revision,
        }
    )
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query), ""))


def download_image(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "Hatodor-MOTD/0.7",
            "Accept": "image/jpeg,image/png,image/webp,image/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise ValueError(f"CATAAS returned {content_type}, not an image")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
            raise ValueError("CATAAS image is larger than 10 MiB")
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError("CATAAS image is larger than 10 MiB")
    return payload


def render_image(payload: bytes, destination: Path) -> None:
    with Image.open(io.BytesIO(payload)) as source:
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
        image = ImageOps.fit(
            image,
            (WIDTH, HEIGHT),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        image = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=1)
        image = image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp.png")
        image.save(temporary, format="PNG", optimize=True)
        os.replace(temporary, destination)


def prune_old_images(directory: Path = OUTPUT_DIR) -> None:
    images = sorted(
        directory.glob("cat-*.png"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_image in images[KEEP_RENDERED_IMAGES:]:
        old_image.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        raise ValueError("expected base64 URL, tone, and dashboard-day arguments")

    source_url = decode_argument(argv[1])
    tone = decode_argument(argv[2])
    day = decode_argument(argv[3])
    pools = load_sayings()
    saying = select_saying(pools, tone, day)
    revision = str(time.time_ns())
    request_url = build_cataas_says_url(source_url, saying, revision)
    payload = download_image(request_url)

    filename = f"cat-{revision}.png"
    destination = OUTPUT_DIR / filename
    render_image(payload, destination)
    prune_old_images()

    print(
        json.dumps(
            {
                "local_url": f"{PUBLIC_PREFIX}/{filename}",
                "saying": saying,
                "tone": tone,
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as error:
        print(f"Could not render cat MOTD: {error}", file=sys.stderr)
        raise SystemExit(1)
