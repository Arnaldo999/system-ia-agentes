# Setup Guardia Crítica

Script: `02_OPERACION_COMPARTIDA/scripts/guardia_critica.py`

## Qué hace

Corre cada 5 minutos. Chequea:
- FastAPI Arnaldo (`/health`) — status + workers_activos ≥ 6
- n8n Arnaldo (`/healthz`) — responde 200
- Coolify app status — `running:healthy` via API

Si alguno falla: retry 1 vez (espera 5s), luego alerta Telegram.
Cooldown 30min por servicio para evitar spam.
Estado persistido en `/tmp/guardia_estado.json`.

## Limitación documentada

Este script corre en el VPS de Arnaldo (Coolify Hostinger).
**Si el VPS cae completamente, este script tampoco corre.**
Protección ante caída total de VPS = mejora futura (ej: UptimeRobot externo o cron en otro servidor).

## Variables de entorno requeridas

Todas deben existir en el `.env` raíz o en el entorno donde corra el cron:

| Variable | Descripción |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID Arnaldo (`863363759`) |
| `COOLIFY_API_URL` | URL base Coolify (ej: `https://coolify.arnaldoayalaestratega.cloud`) |
| `COOLIFY_TOKEN` | API key Coolify |
| `COOLIFY_APP_UUID` | UUID app FastAPI en Coolify (`ygjvl9byac1x99laqj4ky1b5`) |
| `FASTAPI_URL` | URL pública FastAPI (`https://agentes.arnaldoayalaestratega.cloud`) |
| `N8N_URL` | URL pública n8n Arnaldo (`https://n8n.arnaldoayalaestratega.cloud`) |

## Instalación del cron en el VPS

```bash
# 1. Verificar que python-dotenv esté instalado
pip install requests python-dotenv

# 2. Editar crontab
crontab -e

# 3. Agregar línea (ajustar paths al VPS)
*/5 * * * * /usr/bin/python3 /path/to/repo/02_OPERACION_COMPARTIDA/scripts/guardia_critica.py >> /var/log/guardia_critica.log 2>&1
```

## Test manual

```bash
cd /path/to/repo
python 02_OPERACION_COMPARTIDA/scripts/guardia_critica.py
```

Salida esperada si todo OK:
```
[guardia] ✅ fastapi: healthy, workers=6
[guardia] ✅ n8n: ok
[guardia] ✅ coolify: status=running:healthy
```
