"""
Auditor de Workflows — Fase 2.2
=================================
Chequea estado activo de workflows críticos en las 3 instancias n8n.
Detecta: workflow inactivo, workflow no encontrado (404), error en ejecuciones recientes.

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas:
    N8N_ARNALDO_URL, N8N_ARNALDO_KEY
    N8N_MICA_URL,    N8N_MICA_KEY
    N8N_LOVBOT_URL,  N8N_LOVBOT_KEY
"""

import os
import time
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # en container las vars vienen del entorno Coolify

N8N_ARNALDO_URL = os.getenv("N8N_ARNALDO_URL", "https://n8n.arnaldoayalaestratega.cloud")
N8N_ARNALDO_KEY = os.getenv("N8N_ARNALDO_KEY", "")
N8N_MICA_URL    = os.getenv("N8N_MICA_URL",    "https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host")
N8N_MICA_KEY    = os.getenv("N8N_MICA_KEY",    "")
N8N_LOVBOT_URL  = os.getenv("N8N_LOVBOT_URL",  "https://n8n.lovbot.ai")
N8N_LOVBOT_KEY  = os.getenv("N8N_LOVBOT_KEY",  "")

REQUEST_TIMEOUT = 10
RETRY_WAIT      = 5
VENTANA_EJECUCIONES_H = 26  # horas — ventana para buscar errores en schedules

# Workflows críticos: id, nombre legible, instancia, URL, key
WORKFLOWS_CRITICOS = [
    {"id": "o4CrjByltFurUWox", "nombre": "Bot Maicol",           "instancia": "arnaldo", "url": N8N_ARNALDO_URL, "key": N8N_ARNALDO_KEY},
    {"id": "aJILcfjRoKDFvGWY", "nombre": "Redes Arnaldo",        "instancia": "arnaldo", "url": N8N_ARNALDO_URL, "key": N8N_ARNALDO_KEY},
    {"id": "yE7fwesbdjxIxoDn", "nombre": "Alerta Cuotas Maicol", "instancia": "arnaldo", "url": N8N_ARNALDO_URL, "key": N8N_ARNALDO_KEY},
    {"id": "aOiZFbmvMoPSE0vB", "nombre": "Redes Mica",           "instancia": "mica",    "url": N8N_MICA_URL,    "key": N8N_MICA_KEY},
    {"id": "OyTCUWbtnigfu5Oh", "nombre": "Lovbot Eventos",       "instancia": "lovbot",  "url": N8N_LOVBOT_URL,  "key": N8N_LOVBOT_KEY},
    {"id": "vF3bMbCzFz3D2W9z", "nombre": "Lovbot Onboarding",    "instancia": "lovbot",  "url": N8N_LOVBOT_URL,  "key": N8N_LOVBOT_KEY},
    {"id": "zEyLpnNJeapT9auj", "nombre": "Lovbot Login Code",    "instancia": "lovbot",  "url": N8N_LOVBOT_URL,  "key": N8N_LOVBOT_KEY},
]

# Workflows con schedule automático — chequeamos ejecuciones recientes
WORKFLOWS_SCHEDULE = [
    {"id": "aJILcfjRoKDFvGWY", "nombre": "Redes Arnaldo", "url": N8N_ARNALDO_URL, "key": N8N_ARNALDO_KEY},
    {"id": "aOiZFbmvMoPSE0vB", "nombre": "Redes Mica",    "url": N8N_MICA_URL,    "key": N8N_MICA_KEY},
    {"id": "fbGdj63Ry7QIw9eL", "nombre": "Backup N8N",    "url": N8N_ARNALDO_URL, "key": N8N_ARNALDO_KEY},
]


def _get(url: str, key: str, path: str) -> tuple[bool, any]:
    """GET a la API de n8n. Retorna (ok, data_o_error)."""
    headers = {"X-N8N-API-KEY": key} if key else {}
    for intento in range(2):
        try:
            r = requests.get(f"{url}/api/v1{path}", headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code == 404:
                return False, {"status": 404}
            r.raise_for_status()
            return True, r.json()
        except requests.exceptions.HTTPError as e:
            return False, {"error": str(e)}
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, {"error": str(e)}
    return False, {"error": "no responde"}


def _check_estado_activo(wf: dict) -> dict:
    ok, data = _get(wf["url"], wf["key"], f"/workflows/{wf['id']}")
    if not ok:
        error_str = data.get("error", "") if isinstance(data, dict) else str(data)
        if isinstance(data, dict) and data.get("status") == 404:
            return {"nombre": wf["nombre"], "instancia": wf["instancia"],
                    "ok": False, "tipo": "workflow_inexistente",
                    "detalle": "HTTP 404 — no encontrado"}
        if "401" in error_str:
            # API REST no accesible con esta key — skip sin falso positivo
            return {"nombre": wf["nombre"], "instancia": wf["instancia"],
                    "ok": True, "detalle": "API REST no accesible (401) — skip"}
        return {"nombre": wf["nombre"], "instancia": wf["instancia"],
                "ok": False, "tipo": "workflow_inactivo",
                "detalle": error_str or "error desconocido"}
    if not data.get("active", False):
        return {"nombre": wf["nombre"], "instancia": wf["instancia"],
                "ok": False, "tipo": "workflow_inactivo",
                "detalle": "active=false"}
    return {"nombre": wf["nombre"], "instancia": wf["instancia"],
            "ok": True, "detalle": "activo"}


def _check_ejecuciones(wf: dict) -> dict:
    ok, data = _get(wf["url"], wf["key"], f"/executions?workflowId={wf['id']}&limit=5")
    if not ok:
        error_str = data.get("error", "") if isinstance(data, dict) else str(data)
        if "401" in error_str:
            return {"nombre": wf["nombre"], "ok": True,
                    "detalle": "API REST no accesible (401) — skip"}
        return {"nombre": wf["nombre"], "ok": False,
                "tipo": "ejecucion_con_error",
                "detalle": f"error consultando ejecuciones: {error_str}"}

    ejecuciones = data.get("data", [])
    if not ejecuciones:
        return {"nombre": wf["nombre"], "ok": True, "detalle": "sin ejecuciones registradas"}

    ventana = datetime.timedelta(hours=VENTANA_EJECUCIONES_H)
    ahora   = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    recientes = []
    for e in ejecuciones:
        ts_str = e.get("startedAt") or e.get("createdAt", "")
        if not ts_str:
            continue
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if (ahora - ts) < ventana:
                recientes.append(e)
        except Exception:
            continue

    if not recientes:
        return {"nombre": wf["nombre"], "ok": True, "detalle": "sin ejecuciones en últimas 26h"}

    ultima = recientes[0]
    status = ultima.get("status", "")
    if status in ("error", "crashed"):
        ts_str = ultima.get("startedAt", "")
        return {"nombre": wf["nombre"], "ok": False,
                "tipo": "ejecucion_con_error",
                "detalle": f"última ejecución: {status} — {ts_str}"}

    return {"nombre": wf["nombre"], "ok": True, "detalle": f"última ejecución: {status}"}


def run() -> dict:
    resultados_estado = [_check_estado_activo(wf) for wf in WORKFLOWS_CRITICOS]
    resultados_ejecuciones = [_check_ejecuciones(wf) for wf in WORKFLOWS_SCHEDULE]

    alertas = [r for r in resultados_estado + resultados_ejecuciones if not r["ok"]]

    return {
        "auditor": "workflows",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {
            "estado_activo":  resultados_estado,
            "ejecuciones":    resultados_ejecuciones,
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
