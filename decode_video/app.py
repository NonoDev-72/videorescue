"""DECODE-VIDEO — reparación de videos dañados (MP4/MOV/AVI/H.264) con interfaz web local."""
import json, os, queue, subprocess, sys, threading, time, uuid
from flask import Flask, jsonify, request, send_file, send_from_directory, abort
from .repair import analyze as an, engine, ffmpeg_tools as ft

FROZEN = getattr(sys, "frozen", False)
PKG = os.path.dirname(os.path.abspath(__file__))
ROOT = PKG
# En la app empaquetada los datos van a la carpeta del usuario (el bundle es de solo lectura)
DATA = os.path.join(os.path.expanduser("~"), "DECODE-VIDEO") if FROZEN else os.path.dirname(PKG)
DEFAULT_OUT = os.path.join(DATA, "salida")
UPLOADS = os.path.join(DATA, "uploads")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".ts", ".mts", ".m2ts", ".h264", ".264", ".hevc", ".dav", ".webm", ".flv", ".wmv", ".mpg", ".mpeg", ".bin", ".dat"}
app = Flask(__name__, static_folder=os.path.join(ROOT, "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = None

JOBS, ORDER = {}, []
Q = queue.Queue()
LOCK = threading.Lock()

def worker():
    while True:
        jid = Q.get()
        job = JOBS.get(jid)
        if not job or job["cancel"]: 
            if job: job["status"] = "cancelled"
            continue
        job["status"] = "running"; job["started"] = time.time()
        def log(msg, pct=None):
            with LOCK:
                if pct is not None: job["pct"] = max(job["pct"], min(1.0, pct))
                else: job["log"].append(msg)
        try:
            r = engine.repair(job["path"], job["outdir"], job["opts"], log, lambda: job["cancel"])
            job["result"] = r; job["status"] = r["status"]; job["pct"] = 1.0
            log("Resultado: " + r.get("message", r["status"]))
        except engine.Cancelled:
            job["status"] = "cancelled"; log("Cancelado por el usuario")
        except Exception as e:
            job["status"] = "failed"; job["result"] = {"status": "failed", "message": str(e)}; log("ERROR: %s" % e)
        job["finished"] = time.time()
threading.Thread(target=worker, daemon=True).start()

def public(job): return {k: v for k, v in job.items() if k != "cancel"} | {"cancelled": job["cancel"]}

@app.get("/")
def index(): return send_from_directory(app.static_folder, "index.html")

@app.get("/api/info")
def info():
    return jsonify(ffmpeg=ft.FFMPEG, default_out=DEFAULT_OUT, home=os.path.expanduser("~"))

@app.get("/api/fs")
def fs():
    p = os.path.abspath(os.path.expanduser(request.args.get("path") or "~"))
    if not os.path.isdir(p): return jsonify(error="No es una carpeta"), 400
    items = []
    try:
        for e in sorted(os.scandir(p), key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())):
            if e.name.startswith("."): continue
            try:
                d = e.is_dir()
                if d: items.append({"name": e.name, "dir": True})
                else:
                    ext = os.path.splitext(e.name)[1].lower()
                    st = e.stat()
                    items.append({"name": e.name, "dir": False, "size": st.st_size, "video": ext in VIDEO_EXT or ext == "" , "mtime": st.st_mtime})
            except OSError: pass
    except PermissionError:
        return jsonify(error="Sin permiso para leer esta carpeta (macOS: concede acceso a la Terminal en Ajustes > Privacidad)"), 403
    home = os.path.expanduser("~")
    places = [{"name": n, "path": q} for n, q in (("Inicio", home), ("Escritorio", home + "/Desktop"), ("Descargas", home + "/Downloads"), ("Películas", home + "/Movies"), ("Vídeos", home + "/Videos"))
              if os.path.isdir(q)]
    if sys.platform == "darwin" and os.path.isdir("/Volumes"):
        places += [{"name": v, "path": "/Volumes/" + v} for v in sorted(os.listdir("/Volumes"))]
    return jsonify(path=p, parent=os.path.dirname(p), items=items, places=places)

@app.post("/api/upload")
def upload():
    os.makedirs(UPLOADS, exist_ok=True)
    out = []
    for f in request.files.getlist("files"):
        name = os.path.basename(f.filename) or "video"
        dst = os.path.join(UPLOADS, "%s_%s" % (uuid.uuid4().hex[:6], name))
        f.save(dst); out.append(dst)
    return jsonify(paths=out)

@app.post("/api/analyze")
def analyze_ep():
    p = (request.json or {}).get("path", "")
    if not os.path.isfile(p): return jsonify(error="Archivo no encontrado"), 404
    r = an.analyze(p)
    r["probe"] = ft.probe(p) if r["recoverable"] else None
    return jsonify(r)

@app.post("/api/jobs")
def create_jobs():
    d = request.json or {}
    outdir = os.path.expanduser(d.get("outdir") or DEFAULT_OUT)
    opts = {"fps": float(d["fps"]) if d.get("fps") else None, "reference": d.get("reference") or None,
            "force": bool(d.get("force")), "force_reencode": bool(d.get("force_reencode"))}
    made = []
    for p in d.get("paths", []):
        if not os.path.isfile(p): continue
        jid = uuid.uuid4().hex[:8]
        job = {"id": jid, "path": p, "name": os.path.basename(p), "size": os.path.getsize(p), "outdir": outdir, "opts": opts, "status": "queued",
               "pct": 0.0, "log": [], "result": None, "cancel": False, "created": time.time()}
        JOBS[jid] = job; ORDER.append(jid); Q.put(jid); made.append(jid)
    return jsonify(ids=made)

@app.get("/api/jobs")
def list_jobs():
    with LOCK: return jsonify([public(JOBS[i]) | {"log": JOBS[i]["log"][-60:]} for i in ORDER])

@app.post("/api/jobs/<jid>/cancel")
def cancel(jid):
    if jid in JOBS: JOBS[jid]["cancel"] = True
    return jsonify(ok=True)

@app.post("/api/jobs/clear")
def clear():
    for i in [i for i in ORDER if JOBS[i]["status"] not in ("queued", "running")]:
        ORDER.remove(i); JOBS.pop(i)
    return jsonify(ok=True)

@app.get("/api/media")
def media():
    p = request.args.get("path", "")
    if not os.path.isfile(p): abort(404)
    return send_file(p, conditional=True)

@app.post("/api/reveal")
def reveal():
    p = (request.json or {}).get("path", "")
    if os.path.exists(p):
        if sys.platform == "darwin": subprocess.Popen(["open", "-R", p])
        elif sys.platform == "win32": subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        else: subprocess.Popen(["xdg-open", os.path.dirname(p)])
    return jsonify(ok=True)

def main():
    port = int(os.environ.get("PORT", 5055))
    print("DECODE-VIDEO en http://127.0.0.1:%d   (ffmpeg: %s)" % (port, ft.FFMPEG))
    app.run(host="127.0.0.1", port=port, threaded=True)

if __name__ == "__main__":
    main()
