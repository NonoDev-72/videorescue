<p align="center">
  <img src="assets/icon.png" alt="DECODE-VIDEO" width="128">
</p>

<h1 align="center">DECODE-VIDEO</h1>

<p align="center">
  Reparador <b>100 % local</b> de videos dañados. Tus archivos nunca salen de tu equipo.
</p>

<p align="center">
  <img alt="Licencia Apache 2.0" src="https://img.shields.io/badge/licencia-Apache%202.0-blue">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776ab">
  <img alt="Plataformas" src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-lightgrey">
</p>

---

## ¿Qué hace?

Recupera videos que no se reproducen: grabaciones truncadas, cámaras o DVR que se apagaron a mitad de grabación, tarjetas SD corruptas, archivos sin cabecera…

Prueba varias estrategias en orden y **valida cada resultado decodificándolo** antes de darlo por bueno:

1. **Reconstrucción del `moov`** (al estilo *untrunc*): escanea el `mdat`, localiza los frames H.264 y los chunks de audio intercalados (PCM A-law/µ-law) y genera un índice nuevo. Arregla la falta de `moov`, una cabecera `ftyp` destruida o un archivo truncado.
2. **Remux tolerante** con ffmpeg (`-c copy`, ignorando errores).
3. **Extracción Annex-B** (H.264/H.265 crudo, típico de DVR).
4. **Re-codificación de rescate** (libx264) si las anteriores dejan errores.

El original **nunca se modifica**. Si un archivo está lleno de `0xFF`/`0x00` se informa como *sin datos* (irrecuperable).

Formatos: MP4, MOV, M4V, AVI, MKV, 3GP, TS/MTS, H.264/H.265 crudo, DAV, WebM, FLV, WMV, MPG…

## Instalación

### Aplicación de escritorio (recomendado)

Descarga el instalador desde [Releases](../../releases):

| Sistema | Archivo |
|---|---|
| macOS (Apple Silicon) | `DECODE-VIDEO.dmg` → arrastra la app a *Aplicaciones* |
| Windows | `DECODE-VIDEO.exe` (carpeta `DECODE-VIDEO`) |

> **macOS:** la app no está firmada. La primera vez, clic derecho → *Abrir*.

Los resultados se guardan por defecto en `~/DECODE-VIDEO/salida`.

### Desde el código fuente

```bash
git clone https://github.com/NonoDev-72/DECODE-VIDEO.git
cd DECODE-VIDEO
./scripts/run.sh          # crea .venv, instala dependencias y abre http://127.0.0.1:5055
```

O manualmente:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m decode_video              # interfaz en el navegador
pip install pywebview
python -m decode_video --desktop    # ventana nativa
```

No hace falta instalar ffmpeg: se incluye a través de [`imageio-ffmpeg`](https://github.com/imageio/imageio-ffmpeg) (si ya tienes uno en el `PATH`, se usa ese).

## Privacidad

- El servidor escucha **solo en `127.0.0.1`**: no es accesible desde la red.
- No hay telemetría, CDN, fuentes externas ni llamadas a internet.
- La reparación se hace en tu equipo.

## Compilar los instaladores

```bash
./packaging/build_mac.sh          # → dist/DECODE-VIDEO.dmg   (en macOS)
packaging\build_windows.bat       # → dist\DECODE-VIDEO\DECODE-VIDEO.exe   (en Windows)
python tools/make_icon.py         # regenera assets/icon.{png,ico,icns}
```

PyInstaller no compila entre sistemas, así que cada instalador se genera en su propio sistema operativo.

## Estructura

```
decode_video/
├── app.py            # servidor Flask + API de trabajos
├── desktop.py        # ventana nativa (pywebview)
├── repair/           # motor de reparación (analyze, rebuild, engine, ffmpeg_tools)
└── static/           # interfaz web (HTML/CSS/JS)
assets/               # icono de la aplicación
packaging/            # scripts de empaquetado (PyInstaller)
scripts/              # utilidades de desarrollo
tools/                # generador del icono
```

## Licencia y atribución

Distribuido bajo [Apache License 2.0](LICENSE). Puedes usar, modificar y redistribuir el software, pero debes **conservar el aviso de copyright y el archivo [`NOTICE`](NOTICE)** que atribuyen la autoría a Juan Antonio Bedmar González, e indicar los cambios que hagas.

Copyright 2026 Juan Antonio Bedmar González
