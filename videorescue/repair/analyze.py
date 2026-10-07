"""Análisis estructural de un archivo de video potencialmente dañado."""
import mmap, os, re, struct

CONTAINER_BOXES = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"udta"}
KNOWN = {b"ftyp", b"mdat", b"moov", b"free", b"skip", b"wide", b"moof", b"mfra", b"pnot", b"uuid", b"styp", b"sidx", b"meta"}

def read_top_boxes(path, limit=200):
    size = os.path.getsize(path)
    boxes, off = [], 0
    with open(path, "rb") as f:
        while off < size and len(boxes) < limit:
            f.seek(off)
            h = f.read(16)
            if len(h) < 8: break
            sz, typ = struct.unpack(">I4s", h[:8])
            hdr = 8
            if sz == 1 and len(h) >= 16:
                sz = struct.unpack(">Q", h[8:16])[0]; hdr = 16
            elif sz == 0:
                sz = size - off
            valid = typ in KNOWN and sz >= hdr
            boxes.append({"type": typ.decode("latin1"), "offset": off, "size": sz, "hdr": hdr,
                          "valid": valid, "truncated": off + sz > size})
            if not valid or sz < 8 or off + sz > size:
                break
            off += sz
    return boxes

def blank_profile(path, samples=64, window=65536):
    """Muestrea el archivo y mide qué parte es relleno (0xFF / 0x00 / uniforme)."""
    size = os.path.getsize(path)
    if size == 0:
        return {"blank_ratio": 1.0, "ff_ratio": 0.0, "zero_ratio": 1.0, "sampled": 0}
    n = min(samples, max(1, size // window))
    pts = [int(i * (size - min(window, size)) / max(1, n - 1)) for i in range(n)] if n > 1 else [0]
    blank = ff = zero = 0
    with open(path, "rb") as f:
        for p in pts:
            f.seek(p); b = f.read(window)
            if not b: continue
            c = max(b.count(255), b.count(0))
            if b.count(255) >= 0.995 * len(b): ff += 1
            if b.count(0) >= 0.995 * len(b): zero += 1
            if c >= 0.995 * len(b): blank += 1
    return {"blank_ratio": blank / len(pts), "ff_ratio": ff / len(pts), "zero_ratio": zero / len(pts), "sampled": len(pts)}

def find_signatures(path, limit=20):
    """Busca SPS H.264 (length-prefixed y Annex B) y marcas ftyp/moov dentro del archivo."""
    out = {"avcc_sps": [], "annexb_sps": [], "ftyp": [], "moov": [], "hevc_vps": []}
    size = os.path.getsize(path)
    if size == 0: return out
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        for key, pat in (("ftyp", rb"ftyp(?:isom|iso2|mp42|mp41|avc1|M4V |qt  |3gp)"),
                         ("moov", rb"moov\x00\x00\x00.mvhd"),
                         ("avcc_sps", rb"\x00\x00\x00[\x0a-\x40][\x67\x27\x47](?=[\x42\x4d\x58\x64\x6e\xf4\x7a])"),
                         ("annexb_sps", rb"\x00\x00\x01[\x67\x27\x47](?=[\x42\x4d\x58\x64\x6e\xf4\x7a])"),
                         ("hevc_vps", rb"\x00\x00\x01\x40\x01")):
            for mt in re.finditer(pat, m):
                out[key].append(mt.start())
                if len(out[key]) >= limit: break
    return out

def analyze(path):
    size = os.path.getsize(path)
    boxes = read_top_boxes(path)
    prof = blank_profile(path)
    sig = find_signatures(path) if prof["blank_ratio"] < 0.99 else {k: [] for k in ("avcc_sps", "annexb_sps", "ftyp", "moov", "hevc_vps")}
    types = [b["type"] for b in boxes if b["valid"]]
    issues = []
    if prof["blank_ratio"] >= 0.99:
        kind = "ff" if prof["ff_ratio"] >= prof["zero_ratio"] else "00"
        issues.append({"code": "blank", "level": "fatal",
                       "msg": ("El archivo está 100%% relleno de bytes 0x%s: no contiene datos de video. "
                               "Suele ocurrir al recuperar de memoria flash/disco borrado (TRIM) o sectores nunca escritos. "
                               "Ningún programa puede repararlo: hay que recuperar los datos desde el origen (otro volcado del disco/SD).") % ("FF" if kind == "ff" else "00")})
    else:
        if not boxes or not boxes[0]["valid"] or boxes[0]["type"] not in ("ftyp", "styp", "moov", "mdat", "free", "wide"):
            issues.append({"code": "bad_header", "level": "error", "msg": "Cabecera MP4 ausente o corrupta (no empieza con ftyp)."})
        if "moov" not in types and "moof" not in types:
            issues.append({"code": "no_moov", "level": "error", "msg": "Falta el átomo 'moov' (índice de video): el archivo se grabó pero nunca se cerró."})
        if any(b["truncated"] for b in boxes):
            issues.append({"code": "truncated", "level": "warn", "msg": "El archivo está truncado: un átomo declara más bytes de los que existen."})
        if prof["blank_ratio"] > 0.2:
            issues.append({"code": "partial_blank", "level": "warn", "msg": "%d%% del archivo es relleno vacío (datos perdidos)." % round(prof["blank_ratio"] * 100)})
        if not issues:
            issues.append({"code": "none", "level": "info", "msg": "La estructura parece correcta; se verificará la decodificación."})
    return {"path": path, "name": os.path.basename(path), "size": size, "boxes": boxes, "blank": prof,
            "signatures": {k: v[:5] for k, v in sig.items()}, "issues": issues,
            "recoverable": prof["blank_ratio"] < 0.99}
