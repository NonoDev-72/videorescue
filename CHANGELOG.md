# Changelog

Todos los cambios relevantes del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones siguen [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido
- Suite de tests con pytest (motor de reparación y API local), ejecutada en Linux, macOS y Windows.
- Captura de la aplicación en el README y sección de tests con las limitaciones conocidas.

### Cambiado
- Los workflows ya no se ejecutan en cambios que solo tocan documentación o imágenes.

## [1.1.1] - 2026-10-07

### Corregido
- **Reparación de MP4 sin índice.** Un MP4 truncado, sin `moov` o con la cabecera destruida (por ejemplo, una grabación de pantalla H.264 + AAC) no se podía reparar: el motor encontraba los frames pero no podía reconstruirlos. Ahora, con un **video de referencia sano** del mismo dispositivo, se leen de él los parámetros del códec (SPS/PPS) y los fps.
- La reconstrucción empieza siempre en un keyframe, incluso cuando la cabecera está dañada.
- Mensaje de error claro cuando falta el video de referencia.

### Cambiado
- Si el audio es AAC (no se puede reindexar sin el índice original), se recupera solo el video y se avisa. El audio PCM A-law/µ-law de DVR sigue recuperándose.
- La etiqueta del campo «Video de referencia» y el README explican para qué sirve.

### Añadido
- `CONTRIBUTING.md`, `SECURITY.md` y `CODEOWNERS`.
- Instrucciones en el README para abrir la app sin firmar en macOS y Windows.

## [1.1.0] - 2026-10-07

### Cambiado
- El proyecto pasa a llamarse **videorescue** (paquete, aplicación, instaladores y carpeta de datos `~/videorescue`).

### Añadido
- Compilación automática de los instaladores y publicación de releases con GitHub Actions.

## [1.0.0] - 2026-10-07

### Añadido
- Primera versión: motor de reparación con cuatro estrategias (reconstrucción del `moov`, remux tolerante, extracción Annex-B y re-codificación de rescate), validadas decodificando cada resultado.
- Interfaz web local, solo en `127.0.0.1`.
- Aplicación de escritorio con ventana nativa (pywebview).
- Icono de la aplicación e instaladores para macOS (`.dmg`) y Windows (`.exe`).
- Licencia Apache 2.0 y `NOTICE`.

[Sin publicar]: https://github.com/NonoDev-72/videorescue/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/NonoDev-72/videorescue/releases/tag/v1.1.1
