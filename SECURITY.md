# Política de seguridad

## Versiones con soporte

Solo recibe correcciones de seguridad la **última versión publicada** en [Releases](../../releases).

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usa el reporte privado de GitHub:
[Security → Report a vulnerability](../../security/advisories/new).

Incluye, si puedes: versión, sistema operativo, pasos para reproducirlo y el impacto que ves. Responderé lo antes posible; este es un proyecto personal, así que no hay plazos garantizados.

## Alcance y modelo de amenazas

videorescue es una herramienta **local**: el servidor escucha solo en `127.0.0.1`, no envía datos a internet y procesa los archivos en el equipo del usuario. Son de interés, por ejemplo:

- Acceso al servidor local desde la red u otro origen.
- Lectura o escritura de archivos fuera de lo que el usuario indica.
- Fallos al procesar archivos de video malformados (desbordamientos, ejecución de código).
