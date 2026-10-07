import time
import pytest
from videorescue import app as appmod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "UPLOADS", str(tmp_path / "uploads"))
    appmod.app.config["TESTING"] = True
    with appmod.app.test_client() as c:
        yield c
    c.post("/api/jobs/clear")


def wait_job(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        job = next(j for j in client.get("/api/jobs").get_json() if j["id"] == jid)
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise TimeoutError


def test_index_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and b"videorescue" in r.data


def test_info_reports_ffmpeg(client):
    assert client.get("/api/info").get_json()["ffmpeg"]


def test_server_binds_only_to_loopback():
    import inspect
    assert 'host="127.0.0.1"' in inspect.getsource(appmod.main)


def test_analyze_missing_file_is_404(client):
    assert client.post("/api/analyze", json={"path": "/no/existe.mp4"}).status_code == 404


def test_fs_lists_a_folder(client, tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    r = client.get("/api/fs?path=%s" % tmp_path)
    names = [i["name"] for i in r.get_json()["items"]]
    assert "a.mp4" in names


def test_fs_rejects_non_folder(client, tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x")
    assert client.get("/api/fs?path=%s" % f).status_code == 400


def test_repair_job_end_to_end(client, damaged, reference, tmp_path):
    out = tmp_path / "salida"
    r = client.post("/api/jobs", json={"paths": [damaged["truncated"]()], "outdir": str(out), "reference": reference})
    job = wait_job(client, r.get_json()["ids"][0])
    assert job["status"] == "ok", job["result"]
    assert (out / "truncated_reparado.mp4").is_file()


def test_job_without_reference_reports_failure(client, damaged, tmp_path):
    r = client.post("/api/jobs", json={"paths": [damaged["truncated"]()], "outdir": str(tmp_path / "salida")})
    job = wait_job(client, r.get_json()["ids"][0])
    assert job["status"] == "failed" and "referencia" in job["result"]["message"]


def test_missing_paths_are_ignored(client):
    assert client.post("/api/jobs", json={"paths": ["/no/existe.mp4"]}).get_json()["ids"] == []
