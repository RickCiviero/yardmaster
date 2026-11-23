import json

from make_fixture import anonymise_file


def test_anonymise_jsonl_keeps_structure_and_numbers_drops_text(tmp_path):
    src, dst = tmp_path / "s.jsonl", tmp_path / "out" / "s.jsonl"
    rows = [
        {"kind": 0, "v": {"sessionId": "real-session-id", "requests": []}},
        {"kind": 2, "k": ["requests"], "v": [{
            "timestamp": 1790000000000, "modelId": "copilot/gpt-5", "copilotCredits": 1.25,
            "message": {"text": "my secret project plan"}, "response": [{"value": "private reply"}],
        }]},
    ]
    src.write_text("".join(json.dumps(r) + "\n" for r in rows))
    anonymise_file(src, dst)
    text = dst.read_text()
    for gone in ("secret project", "private reply", "real-session-id"):
        assert gone not in text
    out = [json.loads(line) for line in text.splitlines()]
    assert out[1]["k"] == ["requests"] and out[1]["kind"] == 2
    req = out[1]["v"][0]
    assert req["timestamp"] == 1790000000000 and req["copilotCredits"] == 1.25
    assert req["modelId"] == "copilot/gpt-5"
    assert req["message"]["text"].startswith("lorem-") and out[0]["v"]["sessionId"].startswith("fx-")


def test_anonymise_json_workspace_paths(tmp_path):
    src, dst = tmp_path / "workspace.json", tmp_path / "o.json"
    src.write_text(json.dumps({"folder": "file:///c%3A/Users/real/proj", "cwd": "C:\\Users\\real\\x"}))
    anonymise_file(src, dst)
    out = json.loads(dst.read_text())
    assert "real" not in json.dumps(out) and out["folder"].startswith("file:///c%3A/ws/")
