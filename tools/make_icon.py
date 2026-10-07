"""Genera assets/icon.png, icon.ico e icon.icns (este último solo en macOS). Requiere Pillow."""
import os, shutil, subprocess, sys
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
S = 1024

def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # fondo: cuadrado redondeado con degradado azul → violeta
    grad = Image.new("RGBA", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = (int(37 + 90 * t), int(99 - 40 * t), int(235 - 20 * t), 255)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((60, 60, S - 60, S - 60), radius=210, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # triángulo de reproducción
    d.polygon([(400, 290), (400, 734), (790, 512)], fill=(255, 255, 255, 255))
    # perforaciones de cinta de película
    for i in range(5):
        y = 250 + i * 128
        d.rounded_rectangle((200, y, 252, y + 64), radius=12, fill=(255, 255, 255, 190))
    return img

def main():
    os.makedirs(OUT, exist_ok=True)
    img = draw()
    img.save(os.path.join(OUT, "icon.png"))
    img.save(os.path.join(OUT, "icon.ico"), sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])
    if sys.platform == "darwin" and shutil.which("iconutil"):
        iset = os.path.join(OUT, "icon.iconset")
        os.makedirs(iset, exist_ok=True)
        for s in (16, 32, 128, 256, 512):
            img.resize((s, s), Image.LANCZOS).save(os.path.join(iset, "icon_%dx%d.png" % (s, s)))
            img.resize((s * 2, s * 2), Image.LANCZOS).save(os.path.join(iset, "icon_%dx%d@2x.png" % (s, s)))
        subprocess.run(["iconutil", "-c", "icns", iset, "-o", os.path.join(OUT, "icon.icns")], check=True)
        shutil.rmtree(iset)

if __name__ == "__main__":
    main()
