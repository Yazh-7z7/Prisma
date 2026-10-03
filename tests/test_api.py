"""API smoke test with a STUB LLM: upload -> analyze -> results, and the G1/G2 prompt checks."""
import io
import json
import os

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from tests.test_end_to_end import GEMMA_PIMA  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StubLLM:
    def __init__(self, reply=GEMMA_PIMA):
        self.reply, self.prompts = reply, []

    def generate(self, prompt, provider=None, model=None, **_):
        self.prompts.append(prompt)
        return self.reply

    def update_key(self, *a, **k):
        pass


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                       # reports go to tmp, not the repo
    import backend.api_server as api
    stub = StubLLM()
    monkeypatch.setattr(api, "_llm_client", stub)
    api._SESSIONS.clear()
    return TestClient(api.app), stub


def upload(c, name="pima_diabetes.csv"):
    raw = open(os.path.join(ROOT, "Datasets", name), "rb").read()
    r = c.post("/upload", files={"file": (name, io.BytesIO(raw), "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


@pytest.mark.parametrize("use_csvl", [False, True])
def test_full_pipeline_pima(client, use_csvl):
    c, stub = client
    sid = upload(c)
    r = c.post("/analyze", json={"session_id": sid, "model_provider": "ollama", "use_csvl": use_csvl})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "complete"
    statuses = [v["status"] for v in body["validation_results"]]
    assert statuses == ["VALID", "VALID", "HALLUCINATION_RELATIONSHIP", "VALID", "VALID",
                        "HALLUCINATION_DIRECTION", "VALID", "HALLUCINATION_VARIABLE",
                        "HALLUCINATION_MAGNITUDE", "VALID"]
    m = body["metrics"]
    assert m["hallucination_rate"] == round(4 / 9 * 100, 1)           # legacy: percent
    assert m["hallucination_rate_frac"] == round(4 / 9, 4)            # explicit fraction (B7)
    assert m["descriptive"]["valid"] == 1 and m["config_hash"]
    for v in body["validation_results"]:                              # what the frontend dereferences
        assert isinstance(v["claim"]["confidence_score"], (int, float))
        assert isinstance(v["extracted_vars"], list)
    assert body["ground_truth"]["n_tests"] == 36


def test_G1_generation_prompt_contains_full_ranked_store(client):
    c, stub = client
    sid = upload(c)
    c.post("/analyze", json={"session_id": sid, "use_csvl": False})
    prompt = stub.prompts[0]
    assert "SUPPORTED RELATIONSHIPS" in prompt and "TESTED BUT NOT SUPPORTED" in prompt
    assert prompt.count("\n  - ") > 15                                 # not just the top 5
    assert "missing=374" in prompt                                     # cleaned data (G5)


def test_G2_critique_and_refine_see_the_same_store(client):
    c, stub = client
    sid = upload(c)
    c.post("/analyze", json={"session_id": sid, "use_csvl": True})
    assert len(stub.prompts) == 3                                      # generate, critique, refine
    for p in stub.prompts[1:]:
        assert "SUPPORTED RELATIONSHIPS" in p and "TESTED BUT NOT SUPPORTED" in p
        assert "differs by" in p                                       # group differences incl. direction info


def test_results_endpoint_roundtrip_and_json_safe(client):
    c, _ = client
    sid = upload(c)
    c.post("/analyze", json={"session_id": sid, "use_csvl": False})
    r = c.get("/results", params={"session_id": sid})
    assert r.status_code == 200 and r.json()["status"] == "complete"
    json.dumps(r.json())


def test_kidney_dataset_through_api(client):
    c, stub = client
    stub.reply = "1. Hemoglobin is strongly positively correlated with packed cell volume.\n" \
                 "2. Patients with CKD have higher hemoglobin levels."
    sid = upload(c, "kidney_disease.csv")
    body = c.post("/analyze", json={"session_id": sid, "use_csvl": False}).json()
    assert [v["status"] for v in body["validation_results"]] == ["VALID", "HALLUCINATION_DIRECTION"]


def test_error_paths(client):
    c, stub = client
    assert c.post("/analyze", json={"session_id": "nope"}).status_code == 404
    sid = upload(c)
    stub.reply = ""
    r = c.post("/analyze", json={"session_id": sid, "use_csvl": False})
    assert r.status_code == 500 and "empty response" in r.json()["detail"]
    stub.reply = "I cannot help with that."
    r = c.post("/analyze", json={"session_id": sid, "use_csvl": False})
    assert r.status_code == 500 and "could not parse" in r.json()["detail"]
    bad = c.post("/upload", files={"file": ("x.csv", io.BytesIO(b"a\n"), "text/csv")})
    assert bad.status_code == 422
