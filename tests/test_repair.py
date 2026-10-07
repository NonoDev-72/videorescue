import pytest
from videorescue.repair import engine, ffmpeg_tools as ft, rebuild as rb

OPTS = {"fps": None, "reference": None, "force": False, "force_reencode": False}


def decodes_cleanly(path):
    c = ft.check_decode(path)
    return c["frames"] > 0 and c["errors"] == 0


def test_ffmpeg_available():
    assert ft.FFMPEG


def test_read_reference_extracts_codec_parameters(reference):
    r = rb.read_reference(reference)
    assert r["sps"] and r["pps"] and r["avcc_box"].startswith(b"\x00\x00")
    assert r["nal_len"] == 4
    assert r["fps"] == pytest.approx(30, rel=0.02)
    assert "audio" not in r


def test_read_reference_detects_aac_audio(sample_av):
    assert rb.read_reference(sample_av)["audio"] == "mp4a"


def test_read_reference_without_moov_returns_none(damaged):
    assert rb.read_reference(damaged["truncated"]()) is None


@pytest.mark.parametrize("fixture", ["sample", "sample_av"])
def test_healthy_file_is_not_touched(fixture, request, tmp_path, log, never_cancel):
    r = engine.repair(request.getfixturevalue(fixture), str(tmp_path / "out"), OPTS, log, never_cancel)
    assert r["status"] == "healthy"
    assert r["output"] is None


@pytest.mark.parametrize("kind", ["truncated", "no_index", "broken_header"])
def test_repair_with_reference(kind, damaged, reference, tmp_path, log, never_cancel):
    src = damaged[kind]()
    r = engine.repair(src, str(tmp_path / "out"), {**OPTS, "reference": reference}, log, never_cancel)
    assert r["status"] == "ok", r.get("message")
    assert r["frames"] > 20
    assert decodes_cleanly(r["output"])


def test_truncated_recovers_about_half_the_video(damaged, reference, tmp_path, log, never_cancel):
    r = engine.repair(damaged["truncated"](), str(tmp_path / "out"), {**OPTS, "reference": reference}, log, never_cancel)
    assert 0.3 * 90 < r["frames"] < 0.7 * 90  # 3 s a 30 fps = 90 frames


def test_repair_without_reference_fails_and_asks_for_one(damaged, tmp_path, log, never_cancel):
    r = engine.repair(damaged["truncated"](), str(tmp_path / "out"), OPTS, log, never_cancel)
    assert r["status"] == "failed"
    assert "referencia" in r["message"]


def test_original_is_never_modified(damaged, reference, tmp_path, log, never_cancel):
    src = damaged["truncated"]()
    before = open(src, "rb").read()
    engine.repair(src, str(tmp_path / "out"), {**OPTS, "reference": reference}, log, never_cancel)
    assert open(src, "rb").read() == before


def test_cancel_raises(damaged, reference, tmp_path, log):
    with pytest.raises(engine.Cancelled):
        engine.repair(damaged["truncated"](), str(tmp_path / "out"), {**OPTS, "reference": reference}, log, lambda: True)


@pytest.mark.xfail(strict=True, reason="Limitación conocida: con audio AAC intercalado paquete a paquete (muxado por defecto de "
                                       "ffmpeg) el escáner no encuentra frames sueltos entre trozos de audio. Con audio en bloques "
                                       "(grabaciones de pantalla, DVR) sí funciona.")
def test_per_packet_interleaved_audio_is_recovered(sample_av, reference, tmp_path, log, never_cancel):
    data = open(sample_av, "rb").read()
    src = tmp_path / "av_truncated.mp4"; src.write_bytes(data[: len(data) // 2])
    r = engine.repair(str(src), str(tmp_path / "out"), {**OPTS, "reference": reference}, log, never_cancel)
    assert r["status"] == "ok" and r["frames"] > 20


@pytest.mark.xfail(strict=True, reason="Limitación conocida: no se reconstruyen los desfases de reordenación (ctts) de los fotogramas B; "
                                       "el resultado se reproduce pero ffmpeg avisa de marcas de tiempo no monótonas.")
def test_bframes_video_decodes_without_errors(sample_bframes, reference, tmp_path, log, never_cancel):
    data = open(sample_bframes, "rb").read()
    src = tmp_path / "b_truncated.mp4"; src.write_bytes(data[: len(data) // 2])
    r = engine.repair(str(src), str(tmp_path / "out"), {**OPTS, "reference": reference}, log, never_cancel)
    assert r["status"] == "ok" and decodes_cleanly(r["output"])
