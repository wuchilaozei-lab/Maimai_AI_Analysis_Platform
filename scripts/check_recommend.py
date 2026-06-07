import json
from urllib.error import HTTPError
import urllib.request


def fetch(path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:8000{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return exc.code, body
    except Exception as exc:
        return 0, str(exc)


if __name__ == "__main__":
    status, text = fetch("/openapi.json")
    print("openapi_status:", status)
    print("has_recommend:", "/analysis/recommend" in text)
    status, text = fetch(
        "/analysis/recommend",
        method="POST",
        payload={"username": "FHGY", "b50": "1", "evaluation_model": "s4"},
    )
    print("recommend_status:", status)
    print("recommend_resp:", text[:700])
