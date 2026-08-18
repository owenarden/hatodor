#!/usr/bin/env python3
"""
Proxy Home Assistant to Super Productivity's loopback-only Local REST API.

Super Productivity 18.19+ requires a Bearer token for API requests other than
GET /health.  The current ha-super-productivity integration does not send that
header, so this proxy injects the token configured in the HA App options.
"""

import asyncio
import json
from pathlib import Path

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 3877
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 3876
MAX_HEADER = 64 * 1024
MAX_BODY = 2 * 1024 * 1024


def load_access_token():
    # /config/options.json is expected when the App's persistent data mapping
    # is remapped to /config. /data/options.json is retained as a fallback.
    for path in (Path("/config/options.json"), Path("/data/options.json")):
        try:
            data = json.loads(path.read_text())
            token = str(data.get("sp_access_token", "")).strip()
            if token:
                return token
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
    return ""


ACCESS_TOKEN = load_access_token()


async def read_request(reader):
    header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)
    if len(header) > MAX_HEADER:
        raise ValueError("request headers too large")

    lines = header.split(b"\r\n")
    rewritten = []
    content_length = 0
    saw_authorization = False

    for line in lines:
        lower = line.lower()
        if lower.startswith(b"host:"):
            line = f"Host: {TARGET_HOST}:{TARGET_PORT}".encode()
        elif lower.startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
        elif lower.startswith(b"authorization:"):
            saw_authorization = True
        rewritten.append(line)

    if ACCESS_TOKEN and not saw_authorization:
        # Insert before the final blank line produced by the header terminator.
        insert_at = max(0, len(rewritten) - 2)
        rewritten.insert(
            insert_at,
            f"Authorization: Bearer {ACCESS_TOKEN}".encode(),
        )

    if content_length > MAX_BODY:
        raise ValueError("request body too large")

    body = b""
    if content_length:
        body = await asyncio.wait_for(reader.readexactly(content_length), timeout=30)

    return b"\r\n".join(rewritten) + body


async def handle_client(reader, writer):
    target_writer = None
    try:
        request = await read_request(reader)
        target_reader, target_writer = await asyncio.wait_for(
            asyncio.open_connection(TARGET_HOST, TARGET_PORT), timeout=10
        )
        target_writer.write(request)
        await target_writer.drain()

        while True:
            chunk = await asyncio.wait_for(target_reader.read(65536), timeout=60)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()

    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        pass
    except Exception as exc:
        try:
            body = f"Super Productivity REST proxy error: {exc}\n".encode()
            writer.write(
                b"HTTP/1.1 502 Bad Gateway\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Content-Type: text/plain\r\n"
                + b"Connection: close\r\n\r\n"
                + body
            )
            await writer.drain()
        except Exception:
            pass
    finally:
        if target_writer is not None:
            target_writer.close()
            try:
                await target_writer.wait_closed()
            except Exception:
                pass
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def main():
    auth_state = "configured" if ACCESS_TOKEN else "NOT configured"
    print(
        f"SP REST proxy listening on {LISTEN_HOST}:{LISTEN_PORT}; "
        f"forwarding to {TARGET_HOST}:{TARGET_PORT}; access token {auth_state}",
        flush=True,
    )
    async with await asyncio.start_server(
        handle_client, LISTEN_HOST, LISTEN_PORT, limit=MAX_HEADER
    ) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
