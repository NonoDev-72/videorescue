# Contribuir a videorescue

Gracias por el interés. Este proyecto es de **código abierto pero no acepta contribuciones sin permiso previo** del autor.

## Reglas

1. **No abras una Pull Request sin haber hablado antes.** Abre primero un *issue* describiendo el cambio. Solo si el autor lo aprueba por escrito en ese issue, se puede preparar una PR.
2. Las PRs no solicitadas se cerrarán sin revisión.
3. Las PRs de *forks* **no ejecutan compilaciones automáticas** (GitHub Actions). El autor decide cuándo y si se ejecutan.
4. Al enviar una contribución aprobada aceptas que se publique bajo la [licencia Apache 2.0](LICENSE) del proyecto.

## Si tu cambio ha sido aprobado

- Crea una rama desde `main` con un nombre descriptivo (`fix/...`, `feat/...`, `docs/...`).
- Haz commits pequeños con mensajes en formato [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`...).
- Mantén el proyecto 100 % local: sin telemetría, sin CDN ni llamadas a internet.
- Prueba tu cambio en local: `./scripts/run.sh`.
- Enlaza el issue aprobado en la descripción de la PR.

## Cosas que no se aceptarán

- Dependencias que envíen datos fuera del equipo del usuario.
- Cambios en la licencia, el `NOTICE` o la atribución del autor.
