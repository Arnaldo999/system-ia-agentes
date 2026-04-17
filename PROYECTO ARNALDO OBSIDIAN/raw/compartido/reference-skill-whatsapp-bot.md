---
name: Skill whatsapp-conversational-bot
description: Skill maestra + 10 sub-skills para bots WhatsApp multi-proveedor. Invocar antes de crear/modificar workers bot.
type: reference
originSessionId: ff264427-3f05-4e1a-a9c9-a3061566ef37
---
# Skill: whatsapp-conversational-bot

Ubicación: `.claude/skills/whatsapp-conversational-bot/`

## Cuándo invocar

- Crear bot WhatsApp nuevo para cualquier cliente
- Modificar bot existente (Robert/Mica/Maicol/Lau/etc.)
- Elegir proveedor WhatsApp (Meta/Evolution/YCloud)
- Migrar de menús numéricos a conversacional
- Debuggear bot que repite preguntas

Se activa automáticamente con keywords: "bot WhatsApp", "BANT", "Meta Graph", "Evolution API", "YCloud", "anti-friction", "calificar leads", "Click-to-WhatsApp".

## Contenido

| Archivo | Propósito |
|---------|-----------|
| SKILL.md | Índice maestro con flujos de trabajo |
| references/providers/_provider-selection.md | Tabla comparativa Meta vs Evolution vs YCloud |
| references/providers/meta-graph-api.md | Parser + envío Meta oficial |
| references/providers/evolution-api.md | Parser + envío Evolution self-hosted |
| references/providers/ycloud-api.md | Parser + envío YCloud BSP |
| references/providers/chatwoot-bridge.md | Integración Chatwoot multi-proveedor |
| references/bant-system-prompt.md | Prompts BANT desarrollador inmobiliario |
| references/conversational-prop-display.md | Presentación 1-prop-a-la-vez (anti-curiosos) |
| references/deterministic-keywords.md | Keywords pre-LLM (más confiable que prompts) |
| references/llm-response-parser.md | Parser tolerante bullets/markdown |
| references/deploy-test-loop.md | Deploy Coolify + curl test cycle |
| scripts/test-bot.sh | Script reutilizable de test (bash) |

## Uso del script de test

```bash
cd .claude/skills/whatsapp-conversational-bot/scripts/
./test-bot.sh robert 5493765384843 caso_a
./test-bot.sh mica 5493765005465 caso_b
./test-bot.sh maicol 5493764815689 caso_a
```

## Principio clave de la skill

**Las reglas críticas NO van en el prompt del LLM, van en Python.** El LLM ignora reglas en prompts largos. Por eso la skill enfatiza keywords deterministas ANTES del LLM call.

## Conocimiento consolidado

La skill resume el aprendizaje de producción del Sprint 1 Robert, Maicol live (YCloud), y Mica demo (Evolution). Funciona como blueprint reutilizable para los próximos bots.

## Commit

`401158e feat(skills): whatsapp-conversational-bot multi-provider` (2026-04-16)
