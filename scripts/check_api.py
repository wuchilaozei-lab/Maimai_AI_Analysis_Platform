import json
import urllib.request


def main() -> None:
    payload = {"username": "FHGY", "b50": "1", "evaluation_model": "s4"}
    req = urllib.request.Request(
        "http://127.0.0.1:8000/analysis/b50",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print("evaluation_model:", body.get("evaluation_model"))
        print("w_tier:", body.get("w_tier"))
        print("stage:", body.get("stage"))
        print("skill_gaps_len:", len(body.get("skill_gaps", [])))
        print("training_strategy:", body.get("training_strategy", {}).get("strategy"))


if __name__ == "__main__":
    main()
