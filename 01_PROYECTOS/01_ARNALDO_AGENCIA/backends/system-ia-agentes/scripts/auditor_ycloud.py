"""
Auditor YCloud — Fase 2.3
==========================
Verifica estado del número WhatsApp de Maicol via API YCloud.
Chequea: número encontrado, qualityRating no RED, status CONNECTED.

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas:
    YCLOUD_API_KEY_MAICOL  → API key YCloud de Maicol
    NUMERO_BOT_MAICOL      → número a verificar (ej: 5493764815689)
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # en container las vars vienen del entorno Coolify

YCLOUD_API_KEY  = os.getenv("YCLOUD_API_KEY_MAICOL", "")
NUMERO_MAICOL   = os.getenv("NUMERO_BOT_MAICOL", "5493764815689")
YCLOUD_API_URL  = "https://api.ycloud.com/v2/whatsapp/phoneNumbers"

REQUEST_TIMEOUT = 10
RETRY_WAIT      = 5

QUALITY_MALOS   = {"RED"}
STATUS_MALOS    = {"FLAGGED", "RESTRICTED", "BANNED", "DISCONNECTED"}


def run() -> dict:
    if not YCLOUD_API_KEY:
        return {
            "auditor": "ycloud",
            "ok": False,
            "alertas": [{"tipo": "config_faltante", "detalle": "YCLOUD_API_KEY_MAICOL no configurada"}],
            "detalle": {},
        }

    headers = {"X-API-Key": YCLOUD_API_KEY}

    for intento in range(2):
        try:
            r = requests.get(YCLOUD_API_URL, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return {
                    "auditor": "ycloud",
                    "ok": False,
                    "alertas": [{"tipo": "api_inaccesible", "detalle": f"no responde: {e}"}],
                    "detalle": {},
                }

    numeros = data.get("items", [])
    if not numeros:
        return {
            "auditor": "ycloud",
            "ok": False,
            "alertas": [{"tipo": "api_vacia", "detalle": "API no devolvió números — verificar key"}],
            "detalle": {},
        }

    # Buscar el número de Maicol
    numero = next((n for n in numeros if n.get("wabaPhoneNumber", "").replace("+", "") == NUMERO_MAICOL
                   or n.get("displayPhoneNumber", "").replace("+", "").replace(" ", "") == NUMERO_MAICOL
                   or n.get("phoneNumber", "").replace("+", "").replace(" ", "") == NUMERO_MAICOL), None)

    if not numero:
        return {
            "auditor": "ycloud",
            "ok": False,
            "alertas": [{"tipo": "numero_no_encontrado",
                         "detalle": f"número {NUMERO_MAICOL} no encontrado en la cuenta YCloud"}],
            "detalle": {"numeros_en_cuenta": len(numeros)},
        }

    quality = numero.get("qualityRating", "UNKNOWN")
    status  = numero.get("status", "UNKNOWN")
    nombre  = numero.get("verifiedName", NUMERO_MAICOL)

    alertas = []
    if quality in QUALITY_MALOS:
        alertas.append({
            "tipo": "calidad_degradada",
            "detalle": f"qualityRating={quality} — riesgo de bloqueo",
        })
    if status in STATUS_MALOS:
        alertas.append({
            "tipo": "numero_bloqueado",
            "detalle": f"status={status} — número restringido o baneado",
        })

    return {
        "auditor": "ycloud",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {
            "numero":  nombre,
            "quality": quality,
            "status":  status,
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
