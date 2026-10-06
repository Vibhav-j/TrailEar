"""Verify all live API endpoints and WebSocket connection."""

import asyncio
import json
import urllib.request


def test_http_get(url: str) -> dict | str:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        content_type = resp.headers.get("content-type", "")
        data = resp.read().decode("utf-8")
        if "application/json" in content_type:
            return json.loads(data)
        return data


def test_http_post(url: str, payload: dict | None = None) -> dict:
    data_bytes = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def test_websocket():
    # Test websocket connection using websockets or httpx/asyncio if available
    import socket

    # Basic HTTP upgrade check
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 8000))
    req = (
        "GET /ws/live HTTP/1.1\r\n"
        "Host: 127.0.0.1:8000\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode())
    res = s.recv(1024).decode(errors="ignore")
    s.close()
    return "101 Switching Protocols" in res


def main():
    base = "http://127.0.0.1:8000"
    print("Testing live API endpoints:")

    # 1. Health
    health = test_http_get(f"{base}/api/health")
    print(
        f"  [OK] GET  /api/health -> {health['status']} (classifier: {health['classifier']['backend']}, llm: {health['llm']['backend']})"
    )

    # 2. List walks
    walks = test_http_get(f"{base}/api/walks")
    print(f"  [OK] GET  /api/walks -> {len(walks)} existing walks found")

    # 3. Start walk
    start_res = test_http_post(f"{base}/api/walks/start")
    walk_id = start_res["walk_id"]
    print(f"  [OK] POST /api/walks/start -> Walk #{walk_id} ({start_res['status']})")

    # 4. Get walk detail
    detail = test_http_get(f"{base}/api/walks/{walk_id}")
    print(f"  [OK] GET  /api/walks/{walk_id} -> started at {detail['started_at']}")

    # 5. Stop walk
    stop_res = test_http_post(f"{base}/api/walks/{walk_id}/stop")
    print(
        f"  [OK] POST /api/walks/{walk_id}/stop -> ended at {stop_res['ended_at']}, journal length {len(stop_res.get('journal') or '')}"
    )

    # 6. Life list
    lifelist = test_http_get(f"{base}/api/lifelist")
    print(f"  [OK] GET  /api/lifelist -> {len(lifelist)} unique species recorded in life list")

    # 7. Static HTML
    html = test_http_get(f"{base}/")
    assert "TrailEar" in html
    print("  [OK] GET  / -> static PWA index.html served (contains 'TrailEar')")

    # 8. Service Worker
    sw = test_http_get(f"{base}/sw.js")
    assert "trailear-v1" in sw
    print("  [OK] GET  /sw.js -> static service worker served (cache name 'trailear-v1')")

    # 9. WebSocket upgrade
    ws_ok = asyncio.run(test_websocket())
    assert ws_ok
    print("  [OK] WS   /ws/live -> 101 Switching Protocols upgrade successful")

    print("\nAll endpoints verified successfully!")


if __name__ == "__main__":
    main()
