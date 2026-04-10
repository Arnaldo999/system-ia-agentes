"""
Guardia Crítica — Monitoreo de producción Arnaldo
=================================================
Corre cada 5 minutos via cron en el entorno Arnaldo.
Alerta por Telegram si FastAPI, n8n o Coolify están caídos.

ALCANCE Y LIMITACIÓN DOCUMENTADA:
- Este script corre en el VPS de Arnaldo (Coolify Hostinger).
- Si el VPS cae completamente, este script tampoco corre.
- La protección ante caída total de VPS queda como mejora futura (ej: cron externo o UptimeRobot).
- Lo que sí cubre: FastAPI caído, n8n caído, app Coolify unhealthy.

VARIABLES DE ENTORNO REQUERIDAS:
- TELEGRAM_BOT_TOKEN     → token del bot Telegram
- TELEGRAM_CHAT_ID       → chat_id de Arnaldo (863363759)
- COOLIFY_API_URL        → URL base Coolify (ej: https://coolify.arnaldoayalaestratega.cloud)
- COOLIFY_TOKEN          → API key Coolify
- COOLIFY_APP_UUID       → UUID de la app FastAPI en Coolify (ygjvl9byac1x99laqj4ky1b5)
- FASTAPI_URL            → URL pública FastAPI (ej: https://agentes.arnaldoayalaestratega.cloud)
- N8N_URL                → URL pública n8n Arnaldo (ej: https://n8n.arnaldoayalaestratega.cloud)

USO:
  python guardia_critica.py

CRON (cada 5 minutos):
  */5 * * * * /path/to/venv/bin/python /path/to/guardia_critica.py >> /var/log/guardia_critica.log 2>&1
"""

import os
import json
import time
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del repo
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

# ── Configuración ────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
COOLIFY_API_URL    = os.environ["COOLIFY_API_URL"].rstrip("/")
COOLIFY_TOKEN      = os.environ["COOLIFY_TOKEN"]
COOLIFY_APP_UUID   = os.environ["COOLIFY_APP_UUID"]
FASTAPI_URL        = os.environ["FASTAPI_URL"].rstrip("/")
N8N_URL            = os.environ["N8N_URL"].rstrip("/")

ESTADO_PATH    = Path("/tmp/guardia_estado.json")
COOLDOWN_MIN   = 30          # minutos entre alertas del mismo servicio
REQUEST_TIMEOUT = 10         # segundos timeout por request
RETRY_WAIT      = 5          # segundos entre intento 1 y retry


# ── Estado persistido (cooldown por servicio) ─────────────────────────────────

def cargar_estado() -> dict:
    if ESTADO_PATH.exists():
        try:
            return json.loads(ESTADO_PATH.read_text())
        except Exception:
            pass
    return {}


def guardar_estado(estado: dict):
    ESTADO_PATH.write_text(json.dumps(estado, indent=2))


def puede_alertar(estado: dict, servicio: str) -> bool:
    """Devuelve True si pasaron más de COOLDOWN_MIN desde la última alerta."""
    ultima = estado.get(servicio, {}).get("ultima_alerta")
    if not ultima:
        return True
    delta = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(ultima)
    return delta.total_seconds() > COOLDOWN_MIN * 60


def registrar_alerta(estado: dict, servicio: str):
    estado.setdefault(servicio, {})["ultima_alerta"] = datetime.datetime.utcnow().isoformat()


# ── Checks individuales ───────────────────────────────────────────────────────

def check_fastapi() -> tuple[bool, str]:
    """
    Retorna (ok, detalle).
    ok=True si status==healthy y workers_activos>=6.
    """
    url = f"{FASTAPI_URL}/health"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "healthy":
                return False, f"status={data.get('status')}"
            workers = data.get("workers_activos", 0)
            if workers < 6:
                return False, f"workers_activos={workers} (esperado ≥6)"
            return True, f"healthy, workers={workers}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_n8n() -> tuple[bool, str]:
    """Chequea /healthz de n8n Arnaldo."""
    url = f"{N8N_URL}/healthz"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return True, "ok"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_coolify() -> tuple[bool, str]:
    """Consulta la API Coolify para verificar que la app esté running:healthy."""
    url = f"{COOLIFY_API_URL}/api/v1/applications/{COOLIFY_APP_UUID}"
    headers = {"Authorization": f"Bearer {COOLIFY_TOKEN}"}
    for intento in range(2):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "")
            if status == "running:healthy":
                return True, f"status={status}"
            return False, f"status={status}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"error API Coolify: {e}"
    return False, "error API Coolify"


# ── Telegram ──────────────────────────────────────────────────────────────────

def enviar_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
    }
    try:
        requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        print(f"[guardia] ERROR enviando Telegram: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ahora = datetime.datetime.now().strftime("%d/%m %H:%M")
    estado = cargar_estado()

    checks = {
        "fastapi":  check_fastapi,
        "n8n":      check_n8n,
        "coolify":  check_coolify,
    }

    nombres = {
        "fastapi": "FastAPI Arnaldo",
        "n8n":     "n8n Arnaldo",
        "coolify": "Coolify app",
    }

    for servicio, fn in checks.items():
        ok, detalle = fn()

        if ok:
            # Limpiar cooldown si el servicio se recuperó
            if servicio in estado:
                estado[servicio].pop("ultima_alerta", None)
            print(f"[guardia] ✅ {servicio}: {detalle}")
            continue

        print(f"[guardia] ❌ {servicio}: {detalle}")

        if not puede_alertar(estado, servicio):
            print(f"[guardia] ⏸ {servicio}: cooldown activo, no se alerta")
            continue

        mensaje = (
            f"🚨 <b>GUARDIA CRÍTICA</b> — {ahora}\n\n"
            f"❌ <b>{nombres[servicio]}</b> — caído\n"
            f"Detalle: <code>{detalle}</code>\n\n"
            f"Revisá inmediatamente."
        )
        enviar_telegram(mensaje)
        registrar_alerta(estado, servicio)
        print(f"[guardia] 📨 alerta enviada por {servicio}")

    guardar_estado(estado)


if __name__ == "__main__":
    main()
