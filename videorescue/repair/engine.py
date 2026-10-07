"""Orquesta las estrategias de reparación y valida cada resultado decodificándolo."""
import mmap, os, re, shutil, tempfile, time
from . import analyze as an, ffmpeg_tools as ft, rebuild as rb

class Cancelled(Exception): pass

def _good(chk):
    return chk["frames"] > 0 and chk["errors"] <= max(2, chk["frames"] * 0.0005)

def _ref_params(reference, log):
    """Lee fps / audio de un video sano de la misma cámara."""
    out = {}
    if not reference or not os.path.isfile(reference): return out
    info = ft.probe(reference)
    for s in info["streams"]:
        if s["kind"] == "video":
            m = re.search(r"([\d.]+) fps", s["desc"])
            if m: out["fps"] = float(m[1])
        elif s["kind"] == "audio":
            out["audio_codec"] = "ulaw" if "pcm_mulaw" in s["desc"] else "alaw" if "pcm_alaw" in s["desc"] else "none"
            m = re.search(r"(\d+) Hz", s["desc"])
            if m: out["audio_rate"] = int(m[1])
    if "audio_codec" not in out: out["audio_codec"] = "none"  # la referencia no tiene audio PCM
    if out: log("Parámetros tomados del video de referencia: %s" % out)
    return out

def repair(src, outdir, opts, log, cancel):
    """Devuelve dict: status (ok|partial|healthy|unrecoverable|failed), output, details."""
    t0 = time.time()
    def chk_cancel():
        if cancel(): raise Cancelled()
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    final = os.path.join(outdir, stem + "_reparado.mp4")
    tmpdir = tempfile.mkdtemp(prefix="decode_", dir=outdir)
    res = {"status": "failed", "output": None, "attempts": [], "analysis": None}
    try:
        log("Analizando estructura…", pct=0.02)
        a = an.analyze(src); res["analysis"] = a
        for i in a["issues"]: log("[%s] %s" % (i["level"].upper(), i["msg"]))
        if not a["recoverable"]:
            res["status"] = "unrecoverable"
            res["message"] = a["issues"][0]["msg"]
            return res
        ref = _ref_params(opts.get("reference"), log)
        fps = opts.get("fps") or ref.get("fps")
        a_codec, a_rate = ref.get("audio_codec", "alaw"), ref.get("audio_rate", 8000)
        refinfo = None
        if opts.get("reference") and os.path.isfile(opts["reference"]):
            try: refinfo = rb.read_reference(opts["reference"])
            except Exception as e: log("No se pudo leer el índice del video de referencia: %s" % e)
        has_moov = any(b["type"] == "moov" and b["valid"] and not b["truncated"] for b in a["boxes"])
        candidates = []  # (frames, errors, path, name)

        if has_moov and not opts.get("force"):
            log("Comprobando si el archivo ya es reproducible…", pct=0.05)
            c = ft.check_decode(src, cancel=cancel); chk_cancel()
            res["attempts"].append({"name": "Verificación original", **c})
            if _good(c):
                res["status"] = "healthy"; res["message"] = "El archivo no tiene daños detectables (%d frames, %.0f s)." % (c["frames"], c["duration"])
                return res

        def attempt(name, fn, pct):
            chk_cancel(); log("▶ Estrategia: %s" % name, pct=pct)
            out = os.path.join(tmpdir, "cand_%d.mp4" % (len(res["attempts"]) + 1))
            try:
                extra = fn(out) or {}
            except Cancelled: raise
            except Exception as e:
                log("   ✗ falló: %s" % e); res["attempts"].append({"name": name, "error": str(e)}); return None
            if not os.path.isfile(out) or os.path.getsize(out) < 1000:
                log("   ✗ sin salida"); res["attempts"].append({"name": name, "error": "sin salida"}); return None
            log("   Validando decodificación…", pct=pct + 0.08)
            c = ft.check_decode(out, cancel=cancel); chk_cancel()
            c.update({"name": name, **extra}); res["attempts"].append(c)
            log("   → %d frames, %.0f s, %d errores" % (c["frames"], c["duration"], c["errors"]))
            if c["frames"] > 0: candidates.append((c["frames"] - 5 * c["errors"], c, out, name))
            return c

        def s_rebuild(out):
            def lg(m, pct=None):
                if pct is None: log("   " + m)
            return rb.rebuild(src, out, fps=fps, audio_codec=a_codec, audio_rate=a_rate, log=lg, cancel=cancel, ref=refinfo)
        def s_remux(out):
            rc, err = ft.run(["-err_detect", "ignore_err", "-fflags", "+genpts+discardcorrupt+igndts", "-i", src, "-map", "0", "-c", "copy",
                              "-ignore_unknown", "-movflags", "+faststart", out], log=log, cancel=cancel)
            if rc != 0: raise RuntimeError((err.strip().splitlines() or ["ffmpeg error"])[-1])
        def s_carve(out):
            sig = a["signatures"]
            codec, off = None, None
            for k, c in (("annexb_sps", "h264"), ("hevc_vps", "hevc")):
                if sig.get(k): codec, off = c, min(sig[k]); break
            if codec is None:  # todas las firmas (la lista de analyze está recortada): intentar con la primera ocurrencia completa
                raise RuntimeError("No hay flujo Annex-B (00 00 01 + SPS/VPS)")
            raw = os.path.join(tmpdir, "carved." + codec)
            with open(src, "rb") as f, open(raw, "wb") as o:
                f.seek(off); shutil.copyfileobj(f, o, 8 << 20)
            rc, err = ft.run(["-err_detect", "ignore_err", "-fflags", "+genpts", "-f", codec, "-r", str(fps or 25), "-i", raw, "-c", "copy", out], log=log, cancel=cancel)
            os.remove(raw)
            if rc != 0: raise RuntimeError((err.strip().splitlines() or ["ffmpeg error"])[-1])
        def s_reencode(out):
            base = best()[2] if candidates else src
            rc, err = ft.run(["-err_detect", "ignore_err", "-fflags", "+genpts+discardcorrupt", "-i", base, "-map", "0:v:0", "-map", "0:a?",
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                              "-movflags", "+faststart", out], log=log, cancel=cancel)
            if rc != 0: raise RuntimeError((err.strip().splitlines() or ["ffmpeg error"])[-1])

        def best(): return max(candidates, key=lambda c: c[0])
        order = [("Remux tolerante a errores (ffmpeg)", s_remux), ("Reconstrucción del índice moov (H.264)", s_rebuild)] if has_moov else \
                [("Reconstrucción del índice moov (H.264)", s_rebuild), ("Remux tolerante a errores (ffmpeg)", s_remux)]
        order.append(("Extracción de flujo Annex-B", s_carve))
        for n, (name, fn) in enumerate(order):
            c = attempt(name, fn, 0.1 + 0.2 * n)
            if c and _good(c):
                break
        if opts.get("force_reencode") or (not candidates or not _good(best()[1])):
            if opts.get("force_reencode") or candidates:
                attempt("Re-codificación de rescate (libx264)", s_reencode, 0.8)
        if not candidates:
            res["status"] = "failed"; res["message"] = "Ninguna estrategia pudo extraer video decodificable del archivo."
            if any("video de referencia" in (a.get("error") or "") for a in res["attempts"]):
                res["message"] += " Prueba de nuevo indicando un video sano grabado con el mismo dispositivo y ajustes (opción «Video de referencia»)."
            return res
        _, c, path, name = best()
        shutil.move(path, final)
        res.update(status="ok" if _good(c) else "partial", output=final, strategy=name, frames=c["frames"], duration=c["duration"],
                   errors=c["errors"], out_size=os.path.getsize(final), elapsed=time.time() - t0)
        res["message"] = ("Reparado con «%s»: %d frames, %.0f s." % (name, c["frames"], c["duration"])) if res["status"] == "ok" else \
                         ("Recuperación parcial con «%s»: %d frames, %d errores de decodificación." % (name, c["frames"], c["errors"]))
        return res
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
