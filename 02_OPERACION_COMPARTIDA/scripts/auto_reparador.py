"""
Auto-Reparador — Repara automáticamente fallos detectados por los auditores
===========================================================================
Se ejecuta después de la auditoría. Recibe los resultados y aplica fixes
conocidos: restart/redeploy Coolify, restart Evolution, etc.

Solo repara problemas que tienen solución programática.
Si algo requiere intervención humana, lo reporta.

Variables de entorno:
    COOLIFY_URL, COOLIFY_TOKEN           → Coolify Arnaldo
    EVOLUTION_API_URL, EVOLUTION_API_KEY  → Evolution API Mica
"""

import os
import time
import requests

COOLIFY_URL   = os.getenv("COOLIFY_URL", "https://coolify.arnaldoayalaestratega.cloud")
COOLIFY_TOKEN = os.getenv("COOLIFY_TOKEN", "")
COOLIFY_APP_UUID = "ygjvl9byac1x99laqj4ky1b5"

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")

TIMEOUT = 15


def _coolify_headers():
    return {"Authorization": f"Bearer {COOLIFY_TOKEN}"}


def _reparar_fastapi_arnaldo() -> dict:
    """Restart FastAPI Arnaldo en Coolify. Si falla, intenta deploy completo."""
    if not COOLIFY_TOKEN:
        return {"reparado": False, "accion": "sin token Coolify"}

    # Paso 1: restart
    try:
        r = requests.post(
            f"{COOLIFY_URL}/api/v1/applications/{COOLIFY_APP_UUID}/restart",
            headers=_coolify_headers(), timeout=TIMEOUT
        )
        print(f"[reparador] Restart Arnaldo: {r.status_code}")
    except Exception as e:
        return {"reparado": False, "accion": f"restart falló: {e}"}

    time.sleep(60)

    # Verificar health
    try:
        h = requests.get("https://agentes.arnaldoayalaestratega.cloud/health", timeout=10)
        if h.status_code == 200 and "healthy" in h.text:
            return {"reparado": True, "accion": "restart exitoso"}
    except Exception:
        pass

    # Paso 2: deploy completo
    try:
        r = requests.post(
            f"{COOLIFY_URL}/api/v1/deploy?uuid={COOLIFY_APP_UUID}&force=true",
            headers=_coolify_headers(), timeout=TIMEOUT
        )
        print(f"[reparador] Deploy Arnaldo: {r.status_code}")
    except Exception as e:
        return {"reparado": False, "accion": f"deploy falló: {e}"}

    time.sleep(120)

    # Verificar health final
    try:
        h = requests.get("https://agentes.arnaldoayalaestratega.cloud/health", timeout=10)
        if h.status_code == 200 and "healthy" in h.text:
            return {"reparado": True, "accion": "deploy completo exitoso"}
    except Exception:
        pass

    return {"reparado": False, "accion": "restart + deploy fallaron — intervención manual"}


def _reparar_evolution_instance(instancia: str) -> dict:
    """Restart instancia Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        return {"reparado": False, "accion": "sin config Evolution"}
    try:
        r = requests.post(
            f"{EVOLUTION_API_URL}/instance/restart/{instancia}",
            headers={"apikey": EVOLUTION_API_KEY},
            timeout=TIMEOUT
        )
        print(f"[reparador] Restart Evolution {instancia}: {r.status_code}")
        time.sleep(30)

        # Verificar
        h = requests.get(
            f"{EVOLUTION_API_URL}/instance/connectionState/{instancia}",
            headers={"apikey": EVOLUTION_API_KEY},
            timeout=10
        )
        if h.status_code == 200 and '"open"' in h.text:
            return {"reparado": True, "accion": f"restart {instancia} exitoso"}
        return {"reparado": False, "accion": f"restart {instancia} — sigue desconectada"}
    except Exception as e:
        return {"reparado": False, "accion": f"error: {e}"}


# ── Mapa de reparaciones por tipo de alerta ──────────────────────────────────

REPARACIONES = {
    "infraestructura_caida": {
        "FastAPI Arnaldo":  _reparar_fastapi_arnaldo,
    },
    "instancia_desconectada": {
        # Se matchea por nombre de instancia
    },
}


def reparar(resultados: list[dict]) -> list[dict]:
    """
    Recibe resultados de los auditores. Intenta reparar las alertas que puede.
    Retorna lista de acciones tomadas.
    """
    acciones = []

    for resultado in resultados:
        if resultado.get("ok") or resultado.get("error_runner"):
            continue

        auditor = resultado.get("auditor", "")

        for alerta in resultado.get("alertas", []):
            tipo = alerta.get("tipo", "")
            nombre = alerta.get("nombre", "") or alerta.get("servicio", "")

            # FastAPI Arnaldo caído
            if tipo == "infraestructura_caida" and "Arnaldo" in nombre:
                print(f"[reparador] Intentando reparar: {nombre}")
                res = _reparar_fastapi_arnaldo()
                acciones.append({"servicio": nombre, **res})

            # Evolution instancia desconectada
            elif auditor == "evolution" and ("desconectada" in str(alerta.get("detalle", "")).lower()
                                             or tipo == "instancia_desconectada"):
                instancia = alerta.get("instancia", nombre)
                print(f"[reparador] Intentando reparar Evolution: {instancia}")
                res = _reparar_evolution_instance(instancia)
                acciones.append({"servicio": f"Evolution {instancia}", **res})

    return acciones


def formatear_acciones(acciones: list[dict]) -> str:
    """Formatea las acciones de reparación para Telegram."""
    if not acciones:
        return ""
    lineas = ["\n🔧 <b>AUTO-REPARACIÓN</b>:"]
    for a in acciones:
        icono = "✅" if a.get("reparado") else "❌"
        lineas.append(f"  {icono} {a['servicio']} — {a['accion']}")
    return "\n".join(lineas)
