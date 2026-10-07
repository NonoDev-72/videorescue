"""Utilidades para localizar y ejecutar ffmpeg."""
import os, re, shutil, subprocess

def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

FFMPEG = ffmpeg_path()

def run(args, log=None, cancel=None, timeout=None):
    """Ejecuta ffmpeg; devuelve (returncode, stderr)."""
    cmd = [FFMPEG, "-hide_banner", "-nostdin", *args]
    if log: log("$ " + " ".join(cmd[1:]))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    import threading
    err = []
    t = threading.Thread(target=lambda: err.append(p.stderr.read()), daemon=True); t.start()
    try:
        while p.poll() is None:
            if cancel and cancel():
                p.kill(); break
            try: p.wait(0.3)
            except subprocess.TimeoutExpired: pass
    finally:
        t.join(2)
    return p.returncode, (err[0] if err else "")

def probe(path):
    """Información básica del archivo vía ffmpeg -i."""
    rc, txt = run(["-i", path])
    info = {"duration": None, "streams": [], "ok": False}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m:
        info["duration"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for m in re.finditer(r"Stream #\S+.*?: (Video|Audio): (.*)", txt):
        info["streams"].append({"kind": m[1].lower(), "desc": m[2].strip()})
    info["ok"] = bool(info["streams"])
    return info

def check_decode(path, cancel=None, max_seconds=None):
    """Decodifica entero (o parte) y cuenta errores. Devuelve dict con frames, errores, duración."""
    args = ["-v", "error", "-i", path]
    if max_seconds: args += ["-t", str(max_seconds)]
    args += ["-f", "null", "-"]
    # -progress no es necesario: se parsean los 'frame='
    rc, txt = run(["-stats", *args], cancel=cancel)
    frames = re.findall(r"frame=\s*(\d+)", txt)
    errors = [l for l in txt.splitlines() if l.strip() and not l.startswith("frame=") and "frame=" not in l]
    t = re.findall(r"time=(\d+):(\d+):([\d.]+)", txt)
    dur = int(t[-1][0]) * 3600 + int(t[-1][1]) * 60 + float(t[-1][2]) if t else 0
    return {"rc": rc, "frames": int(frames[-1]) if frames else 0, "errors": len(errors), "duration": dur, "sample": errors[:5]}
