"""
Auditor de Infraestructura — Fase 2.2
======================================
Chequea salud de n8n Mica y n8n Lovbot.
FastAPI Arnaldo, n8n Arnaldo y Coolify los cubre guardia_critica.py.

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno (opcionales — tienen defaults):
    N8N_MICA_URL    → URL n8n Mica
    N8N_LOVBOT_URL  → URL n8n Lovbot
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

N8N_MICA_URL   = os.getenv("N8N_MICA_URL",   "https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host")
N8N_LOVBOT_URL = os.getenv("N8N_LOVBOT_URL", "https://n8n.lovbot.ai")

REQUEST_TIMEOUT = 10
RETRY_WAIT      = 5


def _check_n8n_health(nombre: str, url: str) -> dict:
    endpoint = f"{url}/healthz"
    for intento in range(2):
        try:
            r = requests.get(endpoint, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return {"servicio": nombre, "ok": True, "detalle": "responde 200"}
            return {"servicio": nombre, "ok": False,
                    "detalle": f"HTTP {r.status_code}"}
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return {"servicio": nombre, "ok": False,
                        "detalle": f"no responde: {e}"}
    return {"servicio": nombre, "ok": False, "detalle": "no responde"}


def run() -> dict:
    checks = [
        _check_n8n_health("n8n Mica",   N8N_MICA_URL),
        _check_n8n_health("n8n Lovbot", N8N_LOVBOT_URL),
    ]
    alertas = [c for c in checks if not c["ok"]]
    return {
        "auditor": "infra",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {c["servicio"]: c["detalle"] for c in checks},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
