import os, random, subprocess
import pytest
from videorescue.repair import ffmpeg_tools as ft


def _make_sample(path, seconds=3, audio=False, bframes=0):
    """MP4 H.264 con el moov al final y el SPS/PPS solo en el avcC (como casi cualquier MP4 real)."""
    cmd = [ft.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=%d" % seconds]
    if audio: cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=%d" % seconds, "-c:a", "aac", "-shortest"]
    subprocess.run(cmd + ["-c:v", "libx264", "-g", "30", "-bf", str(bframes), "-pix_fmt", "yuv420p", path], check=True)


@pytest.fixture(scope="session")
def sample(tmp_path_factory):
    p = str(tmp_path_factory.mktemp("media") / "sample.mp4")
    _make_sample(p)
    return p


@pytest.fixture(scope="session")
def sample_av(tmp_path_factory):
    """Con audio AAC intercalado por paquetes (el muxado por defecto de ffmpeg)."""
    p = str(tmp_path_factory.mktemp("media_av") / "sample_av.mp4")
    _make_sample(p, audio=True)
    return p


@pytest.fixture(scope="session")
def sample_bframes(tmp_path_factory):
    p = str(tmp_path_factory.mktemp("media_b") / "sample_b.mp4")
    _make_sample(p, bframes=2)
    return p


@pytest.fixture(scope="session")
def reference(tmp_path_factory):
    """Otro video sano con los mismos ajustes y distinta duración."""
    p = str(tmp_path_factory.mktemp("ref") / "reference.mp4")
    _make_sample(p, seconds=1)
    return p


@pytest.fixture
def damaged(sample, tmp_path):
    """Devuelve funciones que crean copias dañadas de `sample`."""
    data = open(sample, "rb").read()

    def truncated():
        p = tmp_path / "truncated.mp4"; p.write_bytes(data[: len(data) // 2]); return str(p)

    def no_index():  # se corta el final, donde está el moov
        p = tmp_path / "no_index.mp4"; p.write_bytes(data[: len(data) - 4000]); return str(p)

    def broken_header():
        b = bytearray(data); rnd = random.Random(1)
        b[:4096] = bytes(rnd.randrange(256) for _ in range(4096))
        p = tmp_path / "broken_header.mp4"; p.write_bytes(bytes(b)); return str(p)

    return {"truncated": truncated, "no_index": no_index, "broken_header": broken_header}


@pytest.fixture
def log():
    return lambda msg=None, pct=None: None


@pytest.fixture
def never_cancel():
    return lambda: False
