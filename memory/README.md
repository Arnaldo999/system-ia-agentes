# memory/ — Silo 3 (estado operativo efímero)

Esta carpeta es el **Silo 3** de la arquitectura de silos (ver `CLAUDE.md` REGLA #0bis). Contiene estado que cambia frecuentemente, NO conocimiento duradero.

## Qué vive acá

Solo información efímera:
- `ESTADO_ACTUAL.md` — qué se hizo hoy / qué falta / producción status
- `debug-log.md` — bugs operativos del día / fix recipes
- Logs de sesión puntuales si quedan a medias

## Qué NO vive acá (se migró a wiki — Silo 2)

Todo lo siguiente está ahora en `PROYECTO ARNALDO OBSIDIAN/wiki/` (base de conocimiento permanente):

| Tema viejo en `memory/` | Ubicación actual |
|------------------------|-------------------|
| Infraestructura | `wiki/conceptos/matriz-infraestructura.md` + `wiki/entidades/vps-*`, `coolify-*`, `easypanel-mica.md` |
| Robert Bazán / alianza | `wiki/entidades/robert-bazan.md` + `wiki/entidades/lovbot-ai.md` |
| CRM Apóstoles mapa | `wiki/` (pendiente ingestar desde `raw/arnaldo/crm-apostoles-mapa.md`) |
| Gastronomía subnichos | `raw/compartido/gastronomia-subnichos.md` (pendiente ingestar) |
| Restaurante gastronómico | `raw/compartido/restaurante-gastronomico.md` (pendiente ingestar) |
| Guía ventas Micaela | `raw/mica/guia-ventas-micaela.md` (pendiente ingestar) |
| Onboarding redes sociales | `raw/compartido/onboarding-redes-sociales.md` (pendiente ingestar) |
| MembresIA app | `raw/compartido/membresia-app.md` (pendiente ingestar) |
| RAG Google Embeddings | `raw/compartido/rag-sistema-google-embeddings.md` (pendiente ingestar) |
| WordPress Elementor | `raw/compartido/wordpress-elementor-sitios-web.md` (pendiente ingestar) |
| Historial CrewAI | `raw/compartido/historial-crewai-saas-agencias.md` (pendiente ingestar) |

## Regla de promoción (efímero → duradero)

Si algo en `memory/` (silo 3) estabiliza como conocimiento estructural (ej: un bug recurrente que requiere cambio arquitectónico):
1. Moverlo a `wiki/` (silo 2) como entidad/concepto/síntesis.
2. Eliminar de `memory/` — la info queda en un solo silo.

## Comando de uso

Si el usuario escribe `MEMORIA`: leer primero este README, después `ESTADO_ACTUAL.md` y `debug-log.md` para enterarse del estado operativo. Para conocimiento estructural → consultar la wiki Obsidian.

Actualizado: 2026-04-17 (reorganización de silos).
