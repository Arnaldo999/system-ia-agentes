# Tabla de Compatibilidad de Rutas — Migración 2026-04-10

| Ruta antigua | Ruta nueva | Estado |
|-------------|------------|--------|
| 02_DEV_N8N_ARCHITECT/backends/ | 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/ | ✅ Migrado |
| 02_DEV_N8N_ARCHITECT/workflows/ | 01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/ | ✅ Migrado |
| 02_DEV_N8N_ARCHITECT/ai-sandbox/ | 01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/ai-sandbox/ | ✅ Migrado |
| DEMOS/ | 01_PROYECTOS/01_ARNALDO_AGENCIA/demos/ | ✅ Migrado |
| 01_VENTAS_CONSULTIVO/ | 01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/ventas-consultivo/ | ✅ Migrado |
| PROYECTO MICAELA/ | 01_PROYECTOS/02_SYSTEM_IA_MICAELA/clientes/ | ✅ Migrado |
| PROYECTO AGENCIA ROBERT-ARNALDO AYALA/ | 01_PROYECTOS/03_LOVBOT_ROBERT/clientes/ | ✅ Migrado |
| execution/ | 02_OPERACION_COMPARTIDA/execution/ | ✅ Migrado |
| handoff/ | 02_OPERACION_COMPARTIDA/handoff/ | ✅ Migrado |
| scripts/ | 02_OPERACION_COMPARTIDA/scripts/ | ✅ Migrado |
| tools/ | 02_OPERACION_COMPARTIDA/tools/ | ✅ Migrado |
| logs/ | 02_OPERACION_COMPARTIDA/logs/ | ✅ Migrado |
| archive/ | 99_ARCHIVO/archive/ | ✅ Migrado |
| LOGO/ | 00_GOBERNANZA_GLOBAL/assets/ | ✅ Migrado |
| ai/ | 00_GOBERNANZA_GLOBAL/ai/ | ✅ Migrado |
| PROYECTO PROPIO ARNALDO AUTOMATIZACION/INMOBILIARIA MAICOL/ | 01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/maicol/ | ✅ Migrado |

## Notas
- `directives/` permanece en raíz (cargado automáticamente por Claude Code)
- `memory/` permanece en raíz (cargado automáticamente por Claude Code)
- `CLAUDE.md` permanece en raíz (requerido por Claude Code) + copia en 00_GOBERNANZA_GLOBAL/
- El repo git `system-ia-agentes` fue copiado. Coolify sigue apuntando a GitHub, sin impacto en producción.
- Las referencias en documentación fueron actualizadas el 2026-04-10.
- `rootDir` en Render (si aún se usa como backup): `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`
