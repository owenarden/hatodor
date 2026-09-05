#!/usr/bin/env python3
"""Render a daily cat saying from The Cat API or a CATAAS image endpoint."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


WIDTH = 800
HEIGHT = 480
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_API_BYTES = 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 20
SAYINGS_PATH = Path("/config/hatodor/cat_sayings.json")
CAT_API_KEY_PATH = Path("/config/hatodor/thecatapi_key")
OUTPUT_DIR = Path("/config/www/hatodor/motd-cache")
PUBLIC_PREFIX = "/local/hatodor/motd-cache"
KEEP_RENDERED_IMAGES = 20
DEFAULT_CAT_PATH = "/cat/closeup"
PHOTO_BLUR_RADIUS = 0.6
PHOTO_CONTRAST = 1.4
CAPTION_MAX_WIDTH = 752
THE_CAT_API_HOST = "api.thecatapi.com"


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


def build_cataas_image_url(source_url: str, revision: str) -> str:
    parsed = urlsplit(source_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("image URL must start with http:// or https://")
    if not parsed.hostname or parsed.hostname.lower() not in {"cataas.com", "www.cataas.com"}:
        raise ValueError("cat MOTD source must be a cataas.com URL")

    path = parsed.path.rstrip("/")
    if path in {"", "/cat"}:
        # The untagged feed often contains wide scenes whose backgrounds turn
        # into e-paper noise. Prefer CATAAS's closeup pool for the simple URL;
        # callers can still choose any explicit tag they want.
        path = DEFAULT_CAT_PATH
    elif not path.startswith("/cat/") or "/says/" in path or path.endswith("/gif"):
        raise ValueError("use a CATAAS random image endpoint such as https://cataas.com/cat")

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "width": str(WIDTH),
            "height": str(HEIGHT),
            "fit": "cover",
            "position": "center",
            "filter": "mono",
            "hatodor": revision,
        }
    )
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query), ""))


def load_cat_api_key(path: Path = CAT_API_KEY_PATH) -> str:
    try:
        key = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise ValueError(
            "The Cat API key is not configured in Hatodor Config Sync"
        ) from error
    if not key:
        raise ValueError("The Cat API key is empty in Hatodor Config Sync")
    return key


def parse_cat_api_response(payload: bytes) -> str:
    result = json.loads(payload)
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        raise ValueError("The Cat API did not return an image")
    image_url = str(result[0].get("url", "")).strip()
    parsed = urlsplit(image_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "thecatapi.com" or hostname.endswith(".thecatapi.com")
    ):
        raise ValueError("The Cat API returned an unexpected image URL")
    return image_url


def resolve_image_url(source_url: str, revision: str) -> str:
    parsed = urlsplit(source_url.strip())
    hostname = (parsed.hostname or "").lower()
    if hostname in {"cataas.com", "www.cataas.com"}:
        return build_cataas_image_url(source_url, revision)
    if parsed.scheme != "https" or hostname != THE_CAT_API_HOST:
        raise ValueError("cat MOTD source must use The Cat API or cataas.com")

    request = Request(
        source_url,
        headers={
            "User-Agent": "Hatodor-MOTD/0.9",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "x-api-key": load_cat_api_key(),
        },
    )
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type != "application/json":
            raise ValueError(f"The Cat API returned {content_type}, not JSON")
        payload = response.read(MAX_API_BYTES + 1)
    if len(payload) > MAX_API_BYTES:
        raise ValueError("The Cat API response is larger than 1 MiB")
    return parse_cat_api_response(payload)


def download_image(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "Hatodor-MOTD/0.9",
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


def wrap_caption(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont
) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if current and width > CAPTION_MAX_WIDTH:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_caption(image: Image.Image, saying: str) -> None:
    draw = ImageDraw.Draw(image)
    lines: list[str] = []
    font: ImageFont.ImageFont | None = None
    for font_size in (40, 36, 32, 28, 24):
        candidate_font = ImageFont.load_default(size=font_size)
        candidate_lines = wrap_caption(draw, saying, candidate_font)
        font = candidate_font
        lines = candidate_lines
        if len(lines) <= 3:
            break
    if font is None or not lines:
        return

    sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = sample_bbox[3] - sample_bbox[1]
    line_spacing = 5
    vertical_padding = 15
    band_height = (
        vertical_padding * 2
        + line_height * len(lines)
        + line_spacing * (len(lines) - 1)
    )
    band_top = HEIGHT - band_height
    draw.rectangle((0, band_top, WIDTH, HEIGHT), fill=0)
    y = band_top + vertical_padding - sample_bbox[1]
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, fill=255, font=font)
        y += line_height + line_spacing


def render_image(payload: bytes, destination: Path, saying: str) -> None:
    with Image.open(io.BytesIO(payload)) as source:
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
        image = ImageOps.fit(
            image,
            (WIDTH, HEIGHT),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        image = ImageOps.grayscale(image)
        # Suppress tiny background texture before dithering, then widen the
        # tonal separation so faces and fur read cleanly on a 1-bit panel.
        image = image.filter(ImageFilter.GaussianBlur(radius=PHOTO_BLUR_RADIUS))
        image = ImageOps.autocontrast(image, cutoff=2)
        image = ImageEnhance.Contrast(image).enhance(PHOTO_CONTRAST)
        draw_caption(image, saying)
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
    request_url = resolve_image_url(source_url, revision)
    payload = download_image(request_url)

    filename = f"cat-{revision}.png"
    destination = OUTPUT_DIR / filename
    render_image(payload, destination, saying)
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
