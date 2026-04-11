"""
Auditor Evolution API — Fase 2.4
==================================
Verifica estado de instancias WhatsApp de Mica via Evolution API.
Chequea: instancia conectada, sesión activa, no hay QR pendiente.

Instancias monitoreadas:
    - System IA Demo (instancia base de Mica)
    - Lau Emprende   (cliente activo de Mica)

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas:
    EVOLUTION_API_URL   → URL base Evolution API
    EVOLUTION_API_KEY   → API key Evolution
    EVOLUTION_INSTANCE  → nombre instancia base (ej: "System IA Demo")
    LAU_EVOLUTION_INSTANCE → nombre instancia Lau (ej: "Lau Emprende")
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()  # en container las vars vienen del entorno Coolify

EVOLUTION_API_URL  = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_API_KEY  = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "System IA Demo")
LAU_INSTANCE       = os.getenv("LAU_EVOLUTION_INSTANCE", "Lau Emprende")

REQUEST_TIMEOUT = 10
RETRY_WAIT      = 5

# Estados que indican problema
ESTADOS_MALOS = {"close", "connecting", "qrcode", "refused", "disconnected"}


def _check_instance(nombre: str) -> dict:
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        return {"instancia": nombre, "ok": False,
                "tipo": "config_faltante",
                "detalle": "EVOLUTION_API_URL o EVOLUTION_API_KEY no configuradas"}

    headers = {"apikey": EVOLUTION_API_KEY}
    url     = f"{EVOLUTION_API_URL}/instance/connectionState/{nombre}"

    for intento in range(2):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code == 404:
                return {"instancia": nombre, "ok": False,
                        "tipo": "instancia_no_encontrada",
                        "detalle": f"instancia '{nombre}' no existe en Evolution API"}
            r.raise_for_status()
            data  = r.json()
            state = data.get("instance", {}).get("state", "").lower()

            if not state:
                return {"instancia": nombre, "ok": False,
                        "tipo": "estado_desconocido",
                        "detalle": f"respuesta inesperada: {data}"}

            if state == "open":
                return {"instancia": nombre, "ok": True,
                        "detalle": f"conectada (state=open)"}

            if state == "qrcode":
                return {"instancia": nombre, "ok": False,
                        "tipo": "qr_pendiente",
                        "detalle": "esperando escaneo de QR — sesión desconectada"}

            if state in ESTADOS_MALOS:
                return {"instancia": nombre, "ok": False,
                        "tipo": "instancia_desconectada",
                        "detalle": f"state={state} — instancia no operativa"}

            return {"instancia": nombre, "ok": True,
                    "detalle": f"state={state}"}

        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return {"instancia": nombre, "ok": False,
                        "tipo": "api_inaccesible",
                        "detalle": f"no responde Evolution API: {e}"}

    return {"instancia": nombre, "ok": False,
            "tipo": "api_inaccesible", "detalle": "no responde"}


def run() -> dict:
    instancias = [EVOLUTION_INSTANCE, LAU_INSTANCE]
    checks     = [_check_instance(i) for i in instancias if i]
    alertas    = [c for c in checks if not c["ok"]]

    return {
        "auditor": "evolution",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {c["instancia"]: c["detalle"] for c in checks},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
