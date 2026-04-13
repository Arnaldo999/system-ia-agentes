"""
Auditor Meta Tech Provider — Fase 2.4
=======================================
Verifica estado del WABA de Robert (Lovbot) via Meta Graph API.
Chequea: token válido, número activo, calidad no degradada.

Instancia monitoreada:
    - Lovbot (Robert) — WABA + phone number via Meta

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas:
    LOVBOT_META_ACCESS_TOKEN   → token de acceso Meta (system user o page token)
    LOVBOT_META_WABA_ID        → WABA ID de Robert (ej: 1416819116022399)
    LOVBOT_META_PHONE_NUMBER_ID → phone number ID (ej: 735319949657644)
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()  # en container las vars vienen del entorno Coolify

META_TOKEN    = os.getenv("LOVBOT_META_ACCESS_TOKEN", "")
WABA_ID       = os.getenv("LOVBOT_META_WABA_ID", "")
PHONE_ID      = os.getenv("LOVBOT_META_PHONE_NUMBER_ID", "")

GRAPH_BASE    = "https://graph.facebook.com/v19.0"
REQUEST_TIMEOUT = 10
RETRY_WAIT      = 5

# Calidades que indican problema
QUALITY_MALOS = {"RED", "FLAGGED"}

# Estados de número que indican problema
STATUS_MALOS  = {"FLAGGED", "RESTRICTED", "BANNED"}


def _get(url: str, params: dict = None) -> tuple[int, dict]:
    """GET con 1 retry. Retorna (status_code, json_data)."""
    for intento in range(2):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            return r.status_code, r.json()
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                raise


def _check_token() -> dict:
    """Verifica que el token sea válido via /me."""
    try:
        status, data = _get(f"{GRAPH_BASE}/me", params={"access_token": META_TOKEN})
        if status == 200 and data.get("id"):
            return {"ok": True, "detalle": f"token válido (id={data['id']})"}
        error = data.get("error", {})
        msg = error.get("message", f"HTTP {status}")
        code = error.get("code", "?")
        if code in (190, 102, 463, 467):  # códigos de token expirado/inválido
            return {"ok": False, "tipo": "token_vencido",
                    "detalle": f"token inválido o vencido — {msg}"}
        return {"ok": False, "tipo": "token_invalido",
                "detalle": f"HTTP {status} — {msg}"}
    except Exception as e:
        return {"ok": False, "tipo": "api_inaccesible",
                "detalle": f"no responde Meta API: {e}"}


def _check_phone_number() -> dict:
    """Verifica estado y calidad del número de teléfono."""
    if not PHONE_ID:
        return {"ok": True, "detalle": "LOVBOT_META_PHONE_NUMBER_ID no configurado — skip"}
    try:
        status, data = _get(
            f"{GRAPH_BASE}/{PHONE_ID}",
            params={
                "access_token": META_TOKEN,
                "fields": "display_phone_number,verified_name,quality_rating,status,code_verification_status",
            },
        )
        if status != 200:
            error = data.get("error", {})
            msg = error.get("message", f"HTTP {status}")
            return {"ok": False, "tipo": "numero_error",
                    "detalle": f"no se pudo consultar número: {msg}"}

        quality = data.get("quality_rating", "UNKNOWN")
        phone_status = data.get("status", "UNKNOWN")
        display = data.get("display_phone_number", PHONE_ID)
        verified = data.get("verified_name", "")

        alertas_internas = []
        if quality in QUALITY_MALOS:
            alertas_internas.append(f"qualityRating={quality}")
        if phone_status in STATUS_MALOS:
            alertas_internas.append(f"status={phone_status}")

        if alertas_internas:
            return {"ok": False, "tipo": "numero_degradado",
                    "detalle": f"{display} ({verified}) — {', '.join(alertas_internas)}"}

        return {"ok": True,
                "detalle": f"{display} ({verified}) — quality={quality}, status={phone_status}"}
    except Exception as e:
        return {"ok": False, "tipo": "api_inaccesible",
                "detalle": f"no responde Meta API: {e}"}


def _check_waba() -> dict:
    """Verifica estado general de la cuenta WABA."""
    if not WABA_ID:
        return {"ok": True, "detalle": "LOVBOT_META_WABA_ID no configurado — skip"}
    try:
        status, data = _get(
            f"{GRAPH_BASE}/{WABA_ID}",
            params={
                "access_token": META_TOKEN,
                "fields": "name,account_review_status,ban_state,message_template_namespace",
            },
        )
        if status != 200:
            error = data.get("error", {})
            msg = error.get("message", f"HTTP {status}")
            return {"ok": False, "tipo": "waba_error",
                    "detalle": f"no se pudo consultar WABA: {msg}"}

        ban_state    = data.get("ban_state", "NONE")
        review_status = data.get("account_review_status", "APPROVED")
        name         = data.get("name", WABA_ID)

        if ban_state and ban_state != "NONE":
            return {"ok": False, "tipo": "waba_baneada",
                    "detalle": f"WABA '{name}' ban_state={ban_state} — cuenta restringida"}

        if review_status in ("REJECTED", "PENDING"):
            return {"ok": False, "tipo": "waba_revision",
                    "detalle": f"WABA '{name}' account_review_status={review_status}"}

        return {"ok": True,
                "detalle": f"WABA '{name}' — ban_state={ban_state}, review={review_status}"}
    except Exception as e:
        return {"ok": False, "tipo": "api_inaccesible",
                "detalle": f"no responde Meta API: {e}"}


def run() -> dict:
    if not META_TOKEN:
        return {
            "auditor": "meta",
            "ok": True,
            "alertas": [],
            "detalle": {"Meta token": "LOVBOT_META_ACCESS_TOKEN no configurado — skip (no aplica a este entorno)"},
        }

    token_check  = _check_token()
    phone_check  = _check_phone_number()
    waba_check   = _check_waba()

    checks  = [token_check, phone_check, waba_check]
    nombres = ["Meta token", "Número WhatsApp", "WABA"]
    alertas = []

    for check, nombre in zip(checks, nombres):
        if not check["ok"]:
            alertas.append({
                "nombre":  nombre,
                "tipo":    check.get("tipo", "desconocido"),
                "detalle": check["detalle"],
            })

    return {
        "auditor": "meta",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {nombre: c["detalle"] for nombre, c in zip(nombres, checks)},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
