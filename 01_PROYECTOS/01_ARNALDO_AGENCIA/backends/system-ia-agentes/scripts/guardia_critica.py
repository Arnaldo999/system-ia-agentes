"""
Guardia Crítica — Monitoreo de producción Arnaldo
=================================================
Corre cada 5 minutos via cron en el entorno Arnaldo.
Alerta por Telegram si algún servicio crítico está caído.

ALCANCE Y LIMITACIÓN DOCUMENTADA:
- Este script corre en el VPS de Arnaldo (Coolify Hostinger).
- Si el VPS cae completamente, este script tampoco corre.
- La protección ante caída total de VPS queda como mejora futura (ej: cron externo o UptimeRobot).
- Lo que sí cubre: FastAPI caído, n8n caído, app Coolify unhealthy, CORS Maicol,
  frontend CRM Maicol, Chatwoot Arnaldo, backend Robert (ping externo),
  CRM Robert frontend, CORS Robert, admin Robert.
  Mica CRM: preparado pero deshabilitado hasta que defina dominio prod.

ENVÍO CONSOLIDADO:
- Si hay múltiples servicios caídos, se manda UN SOLO mensaje de Telegram con todos juntos.
- Cada servicio tiene cooldown individual de 30 min (no re-alerta hasta que pase ese tiempo).
- Si un servicio se recupera, su cooldown se limpia (volvería a alertar si cae de nuevo).
- Checks que devuelven None (deshabilitados) se saltan silenciosamente.

VARIABLES DE ENTORNO REQUERIDAS:
- TELEGRAM_BOT_TOKEN     → token del bot Telegram
- TELEGRAM_CHAT_ID       → chat_id de Arnaldo (863363759)
- COOLIFY_API_URL        → URL base Coolify (ej: https://coolify.arnaldoayalaestratega.cloud)
- COOLIFY_TOKEN          → API key Coolify
- COOLIFY_APP_UUID       → UUID de la app FastAPI en Coolify (ygjvl9byac1x99laqj4ky1b5)
- FASTAPI_URL            → URL pública FastAPI (ej: https://agentes.arnaldoayalaestratega.cloud)
- N8N_URL                → URL pública n8n Arnaldo (ej: https://n8n.arnaldoayalaestratega.cloud)

VARIABLES OPCIONALES (tienen defaults):
- N8N_MICA_URL           → default: https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host
- N8N_LOVBOT_URL         → default: https://n8n.lovbot.ai
- MAICOL_CRM_FRONTEND    → default: https://crm.backurbanizaciones.com
- CHATWOOT_URL           → default: https://chatwoot.arnaldoayalaestratega.cloud
- BACKEND_ROBERT_URL     → default: https://agentes.lovbot.ai
- MAICOL_CORS_ORIGIN     → default: https://crm.backurbanizaciones.com
- MAICOL_CORS_ENDPOINT   → default: /clientes/arnaldo/maicol/crm/propiedades
- ROBERT_CRM_URL         → default: https://crm.lovbot.ai
- ROBERT_ADMIN_URL       → default: https://admin.lovbot.ai
- ROBERT_BACKEND_CORS    → default: https://agentes.lovbot.ai

CHECKS MICA (deshabilitados — activar cuando Mica defina dominio prod):
- MICA_CRM_ENABLED       → setear "1" para habilitar los checks de Mica
- MICA_CRM_URL           → default: https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2
                            Cuando Mica defina dominio prod (ej: crm.systemia.com),
                            setear MICA_CRM_URL en Coolify y poner MICA_CRM_ENABLED=1.
                            TODO: actualizar cuando se defina dominio prod (consultar a Arnaldo).

USO:
  python scripts/guardia_critica.py

CRON EN COOLIFY (Scheduled Tasks, cada 5 minutos):
  */5 * * * *   python scripts/guardia_critica.py

DESHABILITAR TEMPORALMENTE:
  En Coolify → la app → Scheduled Tasks → pausar la tarea.
  O: setear env var GUARDIA_DISABLED=1 para que el script salga sin hacer nada.
"""

import os
import json
import time
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del repo
_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

# ── Kill switch ───────────────────────────────────────────────────────────────

if os.getenv("GUARDIA_DISABLED", "").strip() == "1":
    print("[guardia] GUARDIA_DISABLED=1 — saliendo sin checks")
    exit(0)

# ── Configuración ────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
COOLIFY_API_URL    = os.environ["COOLIFY_API_URL"].rstrip("/")
COOLIFY_TOKEN      = os.environ["COOLIFY_TOKEN"]
COOLIFY_APP_UUID   = os.environ["COOLIFY_APP_UUID"]
FASTAPI_URL        = os.environ["FASTAPI_URL"].rstrip("/")
N8N_URL            = os.environ["N8N_URL"].rstrip("/")

# Opcionales con defaults
N8N_MICA_URL        = os.getenv("N8N_MICA_URL", "https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host").rstrip("/")
N8N_LOVBOT_URL      = os.getenv("N8N_LOVBOT_URL", "https://n8n.lovbot.ai").rstrip("/")
MAICOL_CRM_FRONTEND = os.getenv("MAICOL_CRM_FRONTEND", "https://crm.backurbanizaciones.com").rstrip("/")
CHATWOOT_URL        = os.getenv("CHATWOOT_URL", "https://chatwoot.arnaldoayalaestratega.cloud").rstrip("/")
BACKEND_ROBERT_URL  = os.getenv("BACKEND_ROBERT_URL", "https://agentes.lovbot.ai").rstrip("/")
MAICOL_CORS_ORIGIN  = os.getenv("MAICOL_CORS_ORIGIN", "https://crm.backurbanizaciones.com")
MAICOL_CORS_ENDPOINT = os.getenv("MAICOL_CORS_ENDPOINT", "/clientes/arnaldo/maicol/crm/propiedades")

# Robert — checks de CRM y admin (LIVE, habilitados)
ROBERT_CRM_URL      = os.getenv("ROBERT_CRM_URL", "https://crm.lovbot.ai").rstrip("/")
ROBERT_ADMIN_URL    = os.getenv("ROBERT_ADMIN_URL", "https://admin.lovbot.ai").rstrip("/")
ROBERT_BACKEND_CORS = os.getenv("ROBERT_BACKEND_CORS", "https://agentes.lovbot.ai").rstrip("/")
ROBERT_CORS_ORIGIN  = os.getenv("ROBERT_CORS_ORIGIN", "https://crm.lovbot.ai")

# Mica — checks deshabilitados hasta que se defina dominio prod
# Para activar: setear MICA_CRM_ENABLED=1 y opcionalmente MICA_CRM_URL en Coolify.
# TODO: cuando Mica defina dominio prod (ej: crm.systemia.com), actualizar MICA_CRM_URL
#       y poner MICA_CRM_ENABLED=1. Consultar a Arnaldo antes de activar.
MICA_CRM_ENABLED    = os.getenv("MICA_CRM_ENABLED", "0")
MICA_CRM_URL        = os.getenv("MICA_CRM_URL", "https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2").rstrip("/")

ESTADO_PATH     = Path("/tmp/guardia_estado.json")
COOLDOWN_MIN    = 30          # minutos entre alertas del mismo servicio
REQUEST_TIMEOUT = 10          # segundos timeout por request
RETRY_WAIT      = 5           # segundos entre intento 1 y retry


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
    """Retorna (ok, detalle). ok=True si status==healthy y workers_activos>=6."""
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
                return False, f"workers_activos={workers} (esperado >=6)"
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


def check_n8n_mica() -> tuple[bool, str]:
    """Chequea /healthz de n8n Mica (Easypanel)."""
    url = f"{N8N_MICA_URL}/healthz"
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


def check_n8n_lovbot() -> tuple[bool, str]:
    """Chequea /healthz de n8n Lovbot (Hetzner)."""
    url = f"{N8N_LOVBOT_URL}/healthz"
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


def check_maicol_crm_cors() -> tuple[bool, str]:
    """
    Verifica que el endpoint de propiedades Maicol responde correctamente
    a un preflight CORS desde el dominio del CRM.
    Este fue exactamente el bug del 2026-04-22 que tumbó el CRM de Maicol.
    """
    url = f"{FASTAPI_URL}{MAICOL_CORS_ENDPOINT}"
    headers = {
        "Origin": MAICOL_CORS_ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    }
    for intento in range(2):
        try:
            r = requests.options(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code not in (200, 204):
                return False, f"preflight HTTP {r.status_code}"
            acao = r.headers.get("Access-Control-Allow-Origin", "")
            if acao == MAICOL_CORS_ORIGIN or acao == "*":
                return True, f"CORS ok (ACAO={acao})"
            return False, f"Access-Control-Allow-Origin ausente o incorrecto: '{acao}'"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_maicol_crm_frontend() -> tuple[bool, str]:
    """Verifica que el frontend del CRM de Maicol responde 200."""
    url = f"{MAICOL_CRM_FRONTEND}/"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_chatwoot_arnaldo() -> tuple[bool, str]:
    """Verifica que Chatwoot Arnaldo responde 200 o 302."""
    url = f"{CHATWOOT_URL}/"
    for intento in range(2):
        try:
            # No seguir redirects para detectar 302 también como OK
            r = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            if r.status_code in (200, 302):
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_backend_robert() -> tuple[bool, str]:
    """
    Ping externo al backend de Robert — solo verifica disponibilidad,
    no toca ningún dato ni lógica de Lovbot.
    Acepta 200, 404 y 405 como respuesta válida (el endpoint existe).
    """
    url = f"{BACKEND_ROBERT_URL}/health"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (200, 404, 405):
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_robert_crm_frontend() -> tuple[bool, str]:
    """
    Verifica que el frontend del CRM de Robert responde 200.
    Agnóstico a la versión del CRM (v1/v2): cuando se hace sync-crm-prod
    el dominio crm.lovbot.ai queda igual, solo cambia el archivo servido.
    Solo ping externo — no toca datos ni lógica de Lovbot.
    """
    url = f"{ROBERT_CRM_URL}/"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_robert_crm_cors() -> tuple[bool, str]:
    """
    Verifica CORS del backend de Robert para el CRM.
    Preflight OPTIONS a /health con Origin: crm.lovbot.ai.
    Valida que responde 200/204 + Access-Control-Allow-Origin correcto.
    Solo ping externo — no toca datos ni lógica de Lovbot.
    """
    url = f"{ROBERT_BACKEND_CORS}/health"
    headers = {
        "Origin": ROBERT_CORS_ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    }
    for intento in range(2):
        try:
            r = requests.options(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code not in (200, 204):
                return False, f"preflight HTTP {r.status_code}"
            acao = r.headers.get("Access-Control-Allow-Origin", "")
            if acao == ROBERT_CORS_ORIGIN or acao == "*":
                return True, f"CORS ok (ACAO={acao})"
            return False, f"Access-Control-Allow-Origin ausente o incorrecto: '{acao}'"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_robert_admin() -> tuple[bool, str]:
    """
    Verifica que el panel admin de Robert responde 200.
    Solo ping externo — no toca datos ni lógica de Lovbot.
    """
    url = f"{ROBERT_ADMIN_URL}/"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_mica_crm_frontend() -> tuple[bool, str] | None:
    """
    Verifica que el frontend del CRM de Mica responde 200.

    DESHABILITADO por defecto. Para activar:
      1. Definir el dominio prod de Mica (ej: crm.systemia.com) — consultar a Arnaldo.
      2. Setear MICA_CRM_URL=https://crm.systemia.com en Coolify (env vars de la app).
      3. Setear MICA_CRM_ENABLED=1 en Coolify.
    URL actual (dev): https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2
    TODO: actualizar cuando se defina dominio prod (consultar a Arnaldo).
    """
    if MICA_CRM_ENABLED != "1":
        return None  # Deshabilitado — saltar silenciosamente
    url = f"{MICA_CRM_URL}"
    for intento in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


def check_mica_crm_cors() -> tuple[bool, str] | None:
    """
    Verifica CORS del backend Arnaldo para el CRM de Mica.
    Preflight OPTIONS a /health con Origin: $MICA_CRM_URL.

    DESHABILITADO por defecto. Para activar: igual que check_mica_crm_frontend().
    Setear MICA_CRM_ENABLED=1 y MICA_CRM_URL en Coolify.
    TODO: actualizar cuando se defina dominio prod (consultar a Arnaldo).
    """
    if MICA_CRM_ENABLED != "1":
        return None  # Deshabilitado — saltar silenciosamente
    url = f"{FASTAPI_URL}/health"
    headers = {
        "Origin": MICA_CRM_URL,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    }
    for intento in range(2):
        try:
            r = requests.options(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code not in (200, 204):
                return False, f"preflight HTTP {r.status_code}"
            acao = r.headers.get("Access-Control-Allow-Origin", "")
            if acao == MICA_CRM_URL or acao == "*":
                return True, f"CORS ok (ACAO={acao})"
            return False, f"Access-Control-Allow-Origin ausente o incorrecto: '{acao}'"
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return False, f"no responde: {e}"
    return False, "no responde"


# ── Telegram ──────────────────────────────────────────────────────────────────

def enviar_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        if not r.ok:
            print(f"[guardia] ERROR Telegram HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[guardia] ERROR enviando Telegram: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ahora = datetime.datetime.now().strftime("%d/%m %H:%M")
    estado = cargar_estado()

    checks = {
        "fastapi":            check_fastapi,
        "n8n":                check_n8n,
        "n8n_mica":           check_n8n_mica,
        "n8n_lovbot":         check_n8n_lovbot,
        "coolify":            check_coolify,
        "maicol_cors":        check_maicol_crm_cors,
        "maicol_frontend":    check_maicol_crm_frontend,
        "chatwoot_arnaldo":   check_chatwoot_arnaldo,
        "backend_robert":     check_backend_robert,
        "robert_crm":         check_robert_crm_frontend,
        "robert_crm_cors":    check_robert_crm_cors,
        "robert_admin":       check_robert_admin,
        "mica_crm":           check_mica_crm_frontend,
        "mica_crm_cors":      check_mica_crm_cors,
    }

    nombres = {
        "fastapi":            "FastAPI Arnaldo",
        "n8n":                "n8n Arnaldo",
        "n8n_mica":           "n8n Mica",
        "n8n_lovbot":         "n8n Lovbot",
        "coolify":            "Coolify app",
        "maicol_cors":        "Maicol CRM — preflight CORS",
        "maicol_frontend":    "Maicol CRM — frontend",
        "chatwoot_arnaldo":   "Chatwoot Arnaldo",
        "backend_robert":     "Backend Robert (ping externo)",
        "robert_crm":         "Robert CRM frontend",
        "robert_crm_cors":    "Robert CRM CORS",
        "robert_admin":       "Robert admin",
        "mica_crm":           "Mica CRM frontend",
        "mica_crm_cors":      "Mica CRM CORS",
    }

    # Acumular alertas que pasaron el cooldown
    alertas_pendientes: list[tuple[str, str, str]] = []  # (servicio, nombre, detalle)

    for servicio, fn in checks.items():
        resultado = fn()

        # Check deshabilitado — saltar silenciosamente
        if resultado is None:
            print(f"[guardia] --- {nombres[servicio]}: deshabilitado (skip)")
            continue

        ok, detalle = resultado

        if ok:
            # Limpiar cooldown si el servicio se recuperó
            if servicio in estado:
                estado[servicio].pop("ultima_alerta", None)
            print(f"[guardia] OK  {nombres[servicio]}: {detalle}")
            continue

        print(f"[guardia] ERR {nombres[servicio]}: {detalle}")

        if not puede_alertar(estado, servicio):
            print(f"[guardia] --- {nombres[servicio]}: cooldown activo, no se alerta")
            continue

        # Acumular — registrar alerta ya para que el cooldown corra
        alertas_pendientes.append((servicio, nombres[servicio], detalle))
        registrar_alerta(estado, servicio)

    # Enviar UN solo mensaje consolidado si hay alertas
    if alertas_pendientes:
        lineas_fallo = "\n".join(
            f"❌ <b>{nombre}</b> — {detalle}"
            for _, nombre, detalle in alertas_pendientes
        )
        n = len(alertas_pendientes)
        plural = "servicio caído" if n == 1 else "servicios caídos"
        mensaje = (
            f"🚨 <b>GUARDIA CRÍTICA</b> — {ahora}\n\n"
            f"{lineas_fallo}\n\n"
            f"<b>{n} {plural}</b> — revisá inmediatamente."
        )
        enviar_telegram(mensaje)
        print(f"[guardia] Telegram enviado — {n} alerta(s): {[s for s, _, _ in alertas_pendientes]}")
    else:
        print(f"[guardia] Todo OK — sin alertas a enviar")

    guardar_estado(estado)


if __name__ == "__main__":
    main()
