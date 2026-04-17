---
name: worker-deploy
description: Deploy de un worker FastAPI a Coolify. Uso: /worker-deploy [proyecto] [entorno]. Proyectos: maicol, prueba, lovbot-robert, social, lau. Entornos: arnaldo (Coolify Hostinger), robert (Coolify Hetzner).
---

# /worker-deploy — Deploy Worker FastAPI

Ejecutá este flujo completo al recibir `/worker-deploy [proyecto] [entorno]`:

## Paso 1 — Identificar proyecto y entorno

Parsear los argumentos:
- **proyecto**: maicol | prueba | social | lovbot-robert | (nombre custom)
- **entorno**: arnaldo | robert

Si faltan argumentos, preguntar antes de continuar.

## Paso 2 — Mapeo proyecto → paths y UUIDs

| Proyecto | Worker path | Coolify UUID (Arnaldo) | Coolify UUID (Robert/Hetzner) |
|----------|------------|------------------------|-------------------------------|
| maicol | `workers/clientes/arnaldo/maicol/worker.py` | `ygjvl9byac1x99laqj4ky1b5` | — |
| prueba | `workers/clientes/arnaldo/prueba/worker.py` | (ver infraestructura.md) | — |
| social | `workers/social/worker.py` | `ygjvl9byac1x99laqj4ky1b5` | — |
| lovbot-robert | `workers/clientes/lovbot/robert_inmobiliaria/worker.py` | — | `ywg48w0gswwk0skokow48o8k` |

Base path del repo: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`

## Paso 3 — Validar sintaxis Python

```bash
python -m py_compile "01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/[worker_path]"
```

Si hay error de sintaxis → **DETENER**. Mostrar error y pedir que se corrija antes de continuar.

## Paso 4 — Git push (si hay cambios)

```bash
cd "01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes"
git status
git add -A
git commit -m "deploy: [proyecto] [fecha]"
git push origin master:main
```

Si no hay cambios, saltar al paso 5 directamente.

## Paso 5 — Trigger deploy en plataforma

### Entorno: arnaldo (Coolify Hostinger)
```bash
curl -s -X POST "https://coolify.arnaldoayalaestratega.cloud/api/v1/deploy?uuid=[UUID]&force=true" \
  -H "Authorization: Bearer $COOLIFY_TOKEN"
```
Token en `.env`: `COOLIFY_TOKEN`

### Entorno: robert (Coolify Hetzner)
```bash
curl -s -X POST "https://coolify.lovbot.ai/api/v1/deploy" \
  -H "Authorization: Bearer $COOLIFY_TOKEN_ROBERT" \
  -H "Content-Type: application/json" \
  -d '{"uuid":"[UUID]","force":true}'
```
Token en `.env`: variable `COOLIFY_TOKEN_LOVBOT` (o leer de .env)

## Paso 6 — Verificar health post-deploy

Esperar ~30 segundos y verificar:

### Arnaldo
```bash
curl -s "https://agentes.arnaldoayalaestratega.cloud/health"
```

### Robert
```bash
curl -s "https://agentes.lovbot.ai/health"
```

Respuesta esperada: `{"status": "ok"}` o similar.

## Paso 7 — Reportar resultado

Mostrar resumen:
```
✅ Deploy [proyecto] → [entorno]
   Worker: [path]
   Plataforma: [URL]
   Health: [status]
   Tiempo total: ~Xmin
```

Si algo falla en cualquier paso → mostrar error claro y detener. No hacer deploy parcial.

## Reglas críticas
- NUNCA hacer deploy sin validar Python primero
- NUNCA compartir tokens en el output
- Si el proyecto es `maicol` o `lau` → advertir que es PRODUCCIÓN LIVE con clientes reales
- Leer tokens desde `.env` en `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/.env`
