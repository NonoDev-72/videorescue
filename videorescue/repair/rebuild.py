"""Reconstrucción del índice 'moov' de un MP4 (H.264 AVCC + audio PCM intercalado) a partir del mdat crudo."""
import mmap, os, re, struct

NAL_START = re.compile(rb"\x00[\x00-\x3f][\x00-\xff]{2}[\x01\x21\x41\x61\x25\x45\x65\x06\x26\x46\x66\x67\x47\x27\x68\x48\x28\x09\x29\x49\x69]")
AUDIO_CODECS = {"alaw": (b"alaw", 1), "ulaw": (b"ulaw", 1)}

# ---------- bits / SPS ----------
class Bits:
    def __init__(s, data): s.d = data; s.p = 0
    def u(s, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((s.d[s.p >> 3] >> (7 - (s.p & 7))) & 1); s.p += 1
        return v
    def ue(s):
        z = 0
        while s.u(1) == 0:
            z += 1
            if z > 32: raise ValueError
        return (1 << z) - 1 + (s.u(z) if z else 0)
    def se(s):
        k = s.ue(); return (k + 1) // 2 if k & 1 else -(k // 2)

def unescape(b): return b.replace(b"\x00\x00\x03", b"\x00\x00")

def parse_sps(nal):
    r = Bits(unescape(nal[1:]))
    prof = r.u(8); r.u(8); r.u(8); r.ue()
    chroma = 1
    if prof in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
        chroma = r.ue()
        if chroma == 3: r.u(1)
        r.ue(); r.ue(); r.u(1)
        if r.u(1):
            for i in range(8 if chroma != 3 else 12):
                if r.u(1):
                    last = 8; nxt = 8
                    for _ in range(16 if i < 6 else 64):
                        if nxt: nxt = (last + r.se()) % 256
                        last = last if nxt == 0 else nxt
    r.ue()
    poc = r.ue()
    if poc == 0: r.ue()
    elif poc == 1:
        r.u(1); r.se(); r.se()
        for _ in range(r.ue()): r.se()
    r.ue(); r.u(1)
    w = (r.ue() + 1) * 16; mh = r.ue() + 1; fm = r.u(1)
    h = (2 - fm) * mh * 16
    if not fm: r.u(1)
    r.u(1)
    if r.u(1):
        cl, cr, ct, cb = r.ue(), r.ue(), r.ue(), r.ue()
        cx = 2 if chroma in (1, 2) else 1; cy = (2 if chroma == 1 else 1) * (2 - fm)
        w -= (cl + cr) * cx; h -= (ct + cb) * cy
    return {"profile": prof, "width": w, "height": h}

# ---------- escaneo del mdat ----------
def _valid_nal(m, pos, end):
    if pos + 5 > end: return 0
    ln = struct.unpack_from(">I", m, pos)[0]
    if ln < 2 or ln > 6_000_000 or pos + 4 + ln > end: return 0
    h = m[pos + 4]
    t = h & 0x1f
    if h & 0x80 or t not in (1, 5, 6, 7, 8, 9): return 0
    if t == 5 and not (h >> 5): return 0
    return ln

def _chain_ok(m, pos, end, depth=2, gap=0):
    """True si desde pos hay NALs válidos encadenados (admitiendo audio intercalado de tamaño `gap` o múltiplos)."""
    for i in range(depth):
        ln = _valid_nal(m, pos, end)
        if not ln: return False
        pos += 4 + ln
        if pos >= end - 4: return True
        if not _valid_nal(m, pos, end):
            if gap:
                for k in (1, 2, 3):
                    if _valid_nal(m, pos + gap * k, end): pos += gap * k; break
                else: return i >= 1
            else: return i >= 1         # sin tamaño de audio conocido: 2 NALs consecutivos
    return True

def scan(m, start, end, log=None, cancel=None):
    """Recorre [start,end) y devuelve (frames, audio_chunks, sps, pps, used_end)."""
    frames, audio = [], []
    sps = pps = None
    pos = start
    cur = None  # [offset, size, key, has_vcl]
    last_gap = 0
    total = end - start
    nxt_log = start
    def close():
        nonlocal cur
        if cur and cur[3]: frames.append((cur[0], cur[1], cur[2]))
        cur = None
    while pos < end - 4:
        if cancel and cancel(): break
        if log and pos >= nxt_log:
            log("Escaneando… %d%%" % ((pos - start) * 100 // max(1, total)), pct=(pos - start) / max(1, total)); nxt_log = pos + total // 20 + 1
        ln = _valid_nal(m, pos, end)
        if ln:
            t = m[pos + 4] & 0x1f
            if t == 7 and sps is None: sps = bytes(m[pos + 4:pos + 4 + ln])
            if t == 8 and pps is None: pps = bytes(m[pos + 4:pos + 4 + ln])
            first_slice = t in (1, 5) and ln > 1 and (m[pos + 5] & 0x80)
            starts_au = t in (9, 7, 8, 6) and (cur is None or cur[3]) or (first_slice and cur is not None and cur[3])
            if cur is not None and starts_au:
                close()
            if cur is None:
                cur = [pos, 0, False, False]
            cur[1] = pos + 4 + ln - cur[0]
            if t in (1, 5): cur[3] = True
            if t == 5: cur[2] = True
            pos += 4 + ln
            continue
        # hueco: audio u otros datos intercalados
        close()
        nxt = None
        # primero probar el tamaño de hueco anterior (los chunks de audio suelen ser constantes)
        for k in (1, 2, 3, 4):
            if last_gap and _chain_ok(m, pos + last_gap * k, end, 3, last_gap): nxt = pos + last_gap * k; break
        if nxt is None:
            for mt in NAL_START.finditer(m, pos + 1, min(end, pos + 4_000_000)):
                if _chain_ok(m, mt.start(), end, 3, last_gap): nxt = mt.start(); break
        if nxt is None:
            break
        last_gap = nxt - pos if not last_gap else min(last_gap, nxt - pos)
        audio.append((pos, nxt - pos))
        pos = nxt
    close()
    return frames, audio, sps, pps, pos

# ---------- escritura de átomos ----------
def box(t, *p): d = b"".join(p); return struct.pack(">I4s", 8 + len(d), t) + d
def full(t, v, fl, *p): return box(t, struct.pack(">I", (v << 24) | fl), *p)
MATRIX = struct.pack(">9I", 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)

def build_moov(frames, audio, sps, pps, fps, w, h, base, data_start, audio_codec="alaw", audio_rate=8000, channels=1, ctime=0):
    TS = 90000
    n = len(frames)
    delta = max(1, round(TS / fps))
    vdur = n * delta
    traks = []
    # --- video ---
    off = [base + (f[0] - data_start) for f in frames]
    co64 = off and max(off) > 0xFFFFFFFF
    stco = full(b"co64", 0, 0, struct.pack(">I", n), b"".join(struct.pack(">Q", o) for o in off)) if co64 else \
           full(b"stco", 0, 0, struct.pack(">I", n), b"".join(struct.pack(">I", o) for o in off))
    avcc = box(b"avcC", bytes([1, sps[1], sps[2], sps[3], 0xFF, 0xE1]), struct.pack(">H", len(sps)), sps, b"\x01", struct.pack(">H", len(pps)), pps)
    avc1 = box(b"avc1", b"\0" * 6, struct.pack(">H", 1), b"\0" * 16, struct.pack(">HH", w, h), struct.pack(">II", 0x480000, 0x480000), b"\0" * 4,
               struct.pack(">H", 1), b"\0" * 32, struct.pack(">H", 24), struct.pack(">h", -1), avcc)
    keys = [i + 1 for i, f in enumerate(frames) if f[2]]
    stbl = box(b"stbl", full(b"stsd", 0, 0, struct.pack(">I", 1), avc1),
               full(b"stts", 0, 0, struct.pack(">III", 1, n, delta)),
               full(b"stss", 0, 0, struct.pack(">I", len(keys)), b"".join(struct.pack(">I", k) for k in keys)),
               full(b"stsc", 0, 0, struct.pack(">IIII", 1, 1, 1, 1)),
               full(b"stsz", 0, 0, struct.pack(">II", 0, n), b"".join(struct.pack(">I", f[1]) for f in frames)),
               stco)
    traks.append(_trak(1, vdur, TS, w, h, b"vide", b"VideoHandler", full(b"vmhd", 0, 1, b"\0" * 8), stbl, ctime, vol=0))
    # --- audio ---
    adur_s = 0
    if audio:
        fourcc, bps = AUDIO_CODECS[audio_codec]
        total = sum(a[1] for a in audio)
        aoff = [base + (a[0] - data_start) for a in audio]
        aco64 = max(aoff) > 0xFFFFFFFF
        astco = full(b"co64", 0, 0, struct.pack(">I", len(aoff)), b"".join(struct.pack(">Q", o) for o in aoff)) if aco64 else \
                full(b"stco", 0, 0, struct.pack(">I", len(aoff)), b"".join(struct.pack(">I", o) for o in aoff))
        stsc_e, prev = [], None
        for i, a in enumerate(audio):
            if a[1] != prev: stsc_e.append(struct.pack(">III", i + 1, a[1], 1)); prev = a[1]
        ent = box(fourcc, b"\0" * 6, struct.pack(">H", 1), b"\0" * 8, struct.pack(">HH", channels, 8), b"\0" * 4, struct.pack(">I", audio_rate << 16))
        astbl = box(b"stbl", full(b"stsd", 0, 0, struct.pack(">I", 1), ent),
                    full(b"stts", 0, 0, struct.pack(">III", 1, total, 1)),
                    full(b"stsc", 0, 0, struct.pack(">I", len(stsc_e)), b"".join(stsc_e)),
                    full(b"stsz", 0, 0, struct.pack(">II", 1, total)), astco)
        adur_s = total / audio_rate
        traks.append(_trak(2, total, audio_rate, 0, 0, b"soun", b"SoundHandler", full(b"smhd", 0, 0, b"\0\0\0\0"), astbl, ctime, vol=0x100,
                           mvts=1000))
    mdur = max(vdur / TS, adur_s)
    mvhd = full(b"mvhd", 0, 0, struct.pack(">IIII", ctime, ctime, 1000, int(mdur * 1000)), struct.pack(">IH", 0x10000, 0x100), b"\0" * 10, MATRIX,
                b"\0" * 24, struct.pack(">I", len(traks) + 1))
    return box(b"moov", mvhd, *traks)

def _trak(tid, dur, ts, w, h, htype, hname, mhd, stbl, ctime, vol, mvts=None):
    mv = int(dur / ts * 1000)
    tkhd = full(b"tkhd", 0, 7, struct.pack(">IIIII", ctime, ctime, tid, 0, mv), b"\0" * 8, struct.pack(">hhhH", 0, 0, vol, 0), MATRIX, struct.pack(">II", w << 16, h << 16))
    mdhd = full(b"mdhd", 0, 0, struct.pack(">IIII", ctime, ctime, ts, dur), struct.pack(">HH", 0x55C4, 0))
    hdlr = full(b"hdlr", 0, 0, b"\0" * 4, htype, b"\0" * 12, hname + b"\0")
    dinf = box(b"dinf", full(b"dref", 0, 0, struct.pack(">I", 1), full(b"url ", 0, 1)))
    return box(b"trak", tkhd, box(b"mdia", mdhd, hdlr, box(b"minf", mhd, dinf, stbl)))

# ---------- API ----------
def rebuild(src, dst, fps=None, audio_codec="alaw", audio_rate=8000, log=None, cancel=None, region=None):
    """Genera dst = ftyp + mdat(copiado) + moov nuevo. Devuelve dict con estadísticas."""
    log = log or (lambda *a, **k: None)
    size = os.path.getsize(src)
    with open(src, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        ftyp = None
        if region:
            start, end = region
        else:
            start, end = None, size
            if m[4:8] == b"ftyp":
                fl = struct.unpack(">I", m[:4])[0]; ftyp = bytes(m[:fl]); p = fl
                # saltar átomos hasta mdat
                while p + 8 <= size:
                    sz, t = struct.unpack(">I4s", m[p:p + 8]); hdr = 8
                    if sz == 1: sz = struct.unpack(">Q", m[p + 8:p + 16])[0]; hdr = 16
                    if t == b"mdat":
                        start = p + hdr
                        end = size if sz == 0 or p + sz > size else p + sz
                        break
                    if sz < 8: break
                    p += sz
            if start is None:
                mt = re.search(rb"\x00\x00\x00[\x0a-\x40][\x67\x27\x47][\x42\x4d\x58\x64\x6e\xf4\x7a]", m)
                if not mt: raise RuntimeError("No se encontró ningún SPS H.264 (flujo length-prefixed) en el archivo.")
                start = mt.start(); log("Sin cabecera MP4: flujo detectado en el byte %d" % start)
        if ftyp is None:
            ftyp = box(b"ftyp", b"isom", struct.pack(">I", 512), b"isomiso2avc1mp41")
        log("Región de datos: %d–%d (%.1f MB)" % (start, end, (end - start) / 1e6))
        frames, audio, sps, pps, used = scan(m, start, end, log=log, cancel=cancel)
        if cancel and cancel(): raise RuntimeError("Cancelado")
        if not frames or not sps or not pps:
            raise RuntimeError("No se pudo reconstruir: %d frames, SPS=%s, PPS=%s" % (len(frames), bool(sps), bool(pps)))
        info = parse_sps(sps)
        asecs = sum(a[1] for a in audio) / audio_rate
        if not fps:
            fps = len(frames) / asecs if asecs > 5 and 1 <= len(frames) / asecs <= 120 else 25.0
            log("FPS estimado: %.3f (frames/audio)" % fps)
        log("Frames: %d (keyframes: %d), audio: %d chunks (%.1f s), %dx%d, %.2f fps" % (
            len(frames), sum(1 for x in frames if x[2]), len(audio), asecs, info["width"], info["height"], fps))
        # recortar a la última muestra completa
        last_end = max(frames[-1][0] + frames[-1][1], (audio[-1][0] + audio[-1][1]) if audio else 0)
        audio = [a for a in audio if a[0] + a[1] <= last_end]
        data_end = last_end
        hdr_big = (data_end - start) + 8 > 0xFFFFFFFF
        mdat_hdr = struct.pack(">I4sQ", 1, b"mdat", data_end - start + 16) if hdr_big else struct.pack(">I4s", data_end - start + 8, b"mdat")
        base = len(ftyp) + len(mdat_hdr)
        moov = build_moov(frames, audio, sps, pps, fps, info["width"], info["height"], base, start, audio_codec, audio_rate)
        with open(dst, "wb") as o:
            o.write(ftyp); o.write(mdat_hdr)
            pos = start; CH = 8 << 20
            while pos < data_end:
                if cancel and cancel(): raise RuntimeError("Cancelado")
                n = min(CH, data_end - pos); o.write(m[pos:pos + n]); pos += n
                log("Escribiendo… %d%%" % ((pos - start) * 100 // max(1, data_end - start)), pct=(pos - start) / max(1, data_end - start))
            o.write(moov)
    return {"frames": len(frames), "audio_chunks": len(audio), "fps": fps, "width": info["width"], "height": info["height"],
            "seconds": len(frames) / fps, "skipped_tail": end - data_end}
