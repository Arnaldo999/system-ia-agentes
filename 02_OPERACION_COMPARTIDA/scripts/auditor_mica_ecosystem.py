"""
Auditor System IA Ecosystem (Mica)
====================================
Verifica el estado de la infraestructura de Micaela Colmenares (System IA).

Checks:
    1. Backend Mica (Easypanel)  — FastAPI backend responde en agentes.arnaldoayalaestratega.cloud
    2. Airtable Mica base        — API key activa, base appA8QxIhBYYAHw0F accesible
    3. Vercel frontends Mica     — systemia-brief-form + CRM demo accesibles

Nota: Evolution API (instancias Lau + Demo) ya se cubre en auditor_evolution.py.

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas (opcionales — skip si ausentes):
    MICA_BACKEND_URL            → URL del backend (default: agentes.arnaldoayalaestratega.cloud)
    AIRTABLE_API_KEY            → API key Airtable (compartida Arnaldo+Mica)
    MICA_AIRTABLE_BASE          → Base ID Airtable Mica (default: appA8QxIhBYYAHw0F)
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

MICA_BACKEND_URL   = os.getenv("MICA_BACKEND_URL", "https://agentes.arnaldoayalaestratega.cloud")
AIRTABLE_API_KEY   = os.getenv("AIRTABLE_API_KEY", "")
MICA_AIRTABLE_BASE = os.getenv("MICA_AIRTABLE_BASE", "appA8QxIhBYYAHw0F")

REQUEST_TIMEOUT = 8
RETRY_WAIT      = 4

VERCEL_URLS = [
    ("System IA Brief Form", "https://systemia-brief-form.vercel.app/"),
    ("Lovbot Demos (CRM Mica)", "https://lovbot-demos.vercel.app/"),
]

MICA_HEALTH_PATHS = [
    "/clientes/system_ia/demos/inmobiliaria/health",
    "/clientes/system_ia/demos/inmobiliaria-v2/health",
    "/",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(url: str, headers: dict = None, params: dict = None,
         timeout: int = REQUEST_TIMEOUT) -> tuple[int, dict | list | None]:
    """GET con 1 retry. Devuelve (status_code, body_json_o_none)."""
    for intento in range(2):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, None
        except Exception:
            if intento == 0:
                time.sleep(RETRY_WAIT)
    return -1, None


def _head_or_get(url: str, timeout: int = REQUEST_TIMEOUT) -> tuple[int, float]:
    """HEAD con fallback a GET. Devuelve (status_code, latency_ms)."""
    import time as _time
    for method in (requests.head, requests.get):
        try:
            t0 = _time.monotonic()
            r = method(url, timeout=timeout, allow_redirects=True)
            latency = (_time.monotonic() - t0) * 1000
            return r.status_code, latency
        except Exception:
            continue
    return -1, 0.0


# ═══ CHECKS ══════════════════════════════════════════════════════════════════


def _check_backend_mica() -> dict:
    """
    Verifica que el backend FastAPI de Mica (Easypanel via Arnaldo) responda.
    Prueba el endpoint de health del worker demo inmobiliaria Mica.
    Un 200 en /health o cualquier respuesta del servidor (incluso 404 en /)
    indica que el proceso está vivo.
    """
    for path in MICA_HEALTH_PATHS:
        status, _ = _get(f"{MICA_BACKEND_URL}{path}")
        if status == 200:
            return {"ok": True,
                    "detalle": f"Backend Mica OK — {path} HTTP 200"}
        if status in (404, 422):
            # El servidor responde aunque la ruta no exista
            if path == "/":
                return {"ok": True,
                        "detalle": f"Backend Mica responde (/ HTTP {status} — proceso vivo)"}
            continue
        if status == -1:
            return {"ok": False, "tipo": "backend_inaccesible",
                    "detalle": f"Backend Mica no responde en {MICA_BACKEND_URL} (timeout/conexion rechazada)"}

    return {"ok": False, "tipo": "backend_error",
            "detalle": f"Backend Mica {MICA_BACKEND_URL} no devolvio 200 en ninguna ruta"}


def _check_airtable_mica() -> dict:
    """
    Verifica que la API key de Airtable sea válida y que la base de Mica
    (appA8QxIhBYYAHw0F) sea accesible.
    """
    if not AIRTABLE_API_KEY:
        return {"ok": None, "detalle": "AIRTABLE_API_KEY no configurada — skip"}

    url = f"https://api.airtable.com/v0/meta/bases/{MICA_AIRTABLE_BASE}/tables"
    status, data = _get(url, headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}"})

    if status == 401:
        return {"ok": False, "tipo": "airtable_token_invalido",
                "detalle": "Airtable API key inválida o revocada (401)"}
    if status == 403:
        return {"ok": False, "tipo": "airtable_sin_acceso",
                "detalle": f"Airtable: sin acceso a base {MICA_AIRTABLE_BASE} (403)"}
    if status == 404:
        return {"ok": False, "tipo": "airtable_base_no_encontrada",
                "detalle": f"Airtable base {MICA_AIRTABLE_BASE} no encontrada (404)"}
    if status != 200:
        return {"ok": False, "tipo": "airtable_error",
                "detalle": f"Airtable API HTTP {status}"}

    tablas = (data or {}).get("tables", [])
    nombres = [t.get("name", "?") for t in tablas[:5]]
    return {"ok": True,
            "detalle": f"Airtable Mica OK — {len(tablas)} tabla(s): {', '.join(nombres)}"}


def _check_vercel_mica() -> dict:
    """
    Verifica que los frontends Vercel de Mica estén accesibles.
    systemia-brief-form es el más crítico — si no existe aún, reporta warning no error.
    """
    fallos = []
    ok_list = []
    pendientes = []

    for nombre, url in VERCEL_URLS:
        status, latency_ms = _head_or_get(url, timeout=8)
        if status == 200:
            ok_list.append(f"{nombre} ({latency_ms:.0f}ms)")
        elif status in (404, -1) and "systemia-brief-form" in url:
            pendientes.append(f"{nombre}: aún no desplegado")
        else:
            fallos.append(f"{nombre}: HTTP {status if status != -1 else 'timeout'}")

    if fallos:
        return {"ok": False, "tipo": "vercel_caido",
                "detalle": "Vercel fallos: " + " | ".join(fallos)}

    msg_parts = []
    if ok_list:
        msg_parts.append(f"OK: {', '.join(ok_list)}")
    if pendientes:
        msg_parts.append(f"Pendiente deploy: {', '.join(pendientes)}")

    return {"ok": True, "detalle": "Vercel Mica — " + " | ".join(msg_parts)}


# ── Runner ────────────────────────────────────────────────────────────────────

def run() -> dict:
    checks_raw = {
        "Backend Mica (Easypanel)": _check_backend_mica(),
        "Airtable Mica base":       _check_airtable_mica(),
        "Vercel frontends Mica":    _check_vercel_mica(),
    }

    alertas = []
    detalle = {}

    for nombre, c in checks_raw.items():
        detalle[nombre] = c["detalle"]
        ok_val = c["ok"]
        if ok_val is False:  # None = skip, no se alerta
            alertas.append({
                "nombre":  nombre,
                "tipo":    c.get("tipo", "desconocido"),
                "detalle": c["detalle"],
            })

    return {
        "auditor": "mica_ecosystem",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": detalle,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
