"""
Onboarding Mica — endpoints que sirven al flujo systemia-onboarding.vercel.app
===============================================================================

El cliente completa el brief, recibe un slug, y entra a la pagina de onboarding
a conectar su WhatsApp via QR (Evolution API).

Endpoints:
    POST /clientes/system_ia/onboarding/iniciar?slug=X
        - Valida que el cliente exista (tabla Clientes_Agencia en Airtable)
        - Crea instancia Evolution si no existe
        - Registra webhook hacia el worker correspondiente
        - Devuelve nombre_empresa, numero esperado, links de Chatwoot/CRM

    GET /clientes/system_ia/onboarding/qr?slug=X
        - Devuelve el QR base64 de la instancia Evolution
        - Si la instancia ya esta conectada, retorna estado=open

    GET /clientes/system_ia/onboarding/estado?slug=X
        - Devuelve estado de conexion (open/close/qrcode/connecting)
        - La pagina polea cada 3s para detectar conexion

Nota: mientras Robert no este aprobado por Meta, todos los clientes Mica
conectan via Evolution. Cuando Robert sea aprobado, este mismo endpoint
podra routear a Tech Provider revisando el campo provider del cliente.
"""

from __future__ import annotations

import os
import re
import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/clientes/system_ia/onboarding",
    tags=["Mica — Onboarding"],
)

# ── Config ────────────────────────────────────────────────────────────────────

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
BACKEND_BASE_URL  = os.environ.get(
    "MICA_BACKEND_BASE_URL",
    "https://agentes.arnaldoayalaestratega.cloud",
).rstrip("/")

# Airtable Mica — base compartida donde viven los clientes de Mica
AIRTABLE_TOKEN = (
    os.environ.get("AIRTABLE_API_KEY", "")
    or os.environ.get("AIRTABLE_TOKEN", "")
)
AIRTABLE_BASE_MICA = (
    os.environ.get("MICA_AIRTABLE_BASE_ID", "")
    or os.environ.get("MICA_DEMO_AIRTABLE_BASE", "")
)
# Tabla "Clientes_Agencia" debe crearse en la base Mica con campos:
#   Slug, Nombre_Empresa, Numero_WhatsApp, Evolution_Instance, Provider,
#   Chatwoot_Url, CRM_Url, Estado, Vertical
TABLE_CLIENTES_AGENCIA = os.environ.get(
    "MICA_AIRTABLE_TABLE_CLIENTES_AGENCIA", "Clientes_Agencia"
)

AT_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}
EVO_HEADERS = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}

DEFAULT_WORKER_PATH = "/clientes/system_ia/demos/inmobiliaria/whatsapp"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _slug_valido(slug: str) -> bool:
    return bool(slug) and bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug))


def _buscar_cliente(slug: str) -> dict | None:
    """Busca el cliente por slug en la tabla Clientes_Agencia de Airtable Mica."""
    if not (AIRTABLE_TOKEN and AIRTABLE_BASE_MICA):
        return None
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_MICA}/{TABLE_CLIENTES_AGENCIA}"
    try:
        r = requests.get(
            url,
            headers=AT_HEADERS,
            params={"filterByFormula": f"{{Slug}}='{slug}'", "maxRecords": 1},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        recs = r.json().get("records", [])
        if not recs:
            return None
        rec = recs[0]
        fields = rec.get("fields", {})
        return {
            "id": rec.get("id"),
            "slug": fields.get("Slug", slug),
            "nombre_empresa": fields.get("Nombre_Empresa", ""),
            "numero_whatsapp": fields.get("Numero_WhatsApp", ""),
            "evolution_instance": fields.get("Evolution_Instance", "") or slug,
            "provider": (fields.get("Provider") or "evolution").lower(),
            "chatwoot_url": fields.get("Chatwoot_Url", ""),
            "crm_url": fields.get("CRM_Url", ""),
            "vertical": fields.get("Vertical", "inmobiliaria"),
            "estado": fields.get("Estado", "pendiente"),
        }
    except Exception as e:
        print(f"[MICA-ONB] Error buscar cliente {slug}: {e}")
        return None


def _evo_get(path: str) -> tuple[int, dict | list | None]:
    if not (EVOLUTION_API_URL and EVOLUTION_API_KEY):
        return -1, None
    try:
        r = requests.get(f"{EVOLUTION_API_URL}{path}", headers=EVO_HEADERS, timeout=10)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception:
        return -1, None


def _evo_post(path: str, body: dict) -> tuple[int, dict | list | None]:
    if not (EVOLUTION_API_URL and EVOLUTION_API_KEY):
        return -1, None
    try:
        r = requests.post(
            f"{EVOLUTION_API_URL}{path}", headers=EVO_HEADERS, json=body, timeout=15
        )
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception:
        return -1, None


def _instance_exists(instance: str) -> bool:
    status, _ = _evo_get(f"/instance/connectionState/{instance}")
    return status == 200


def _instance_estado(instance: str) -> str:
    status, data = _evo_get(f"/instance/connectionState/{instance}")
    if status != 200 or not data:
        return "unknown"
    return ((data.get("instance") or {}).get("state") or "unknown").lower()


def _instance_create(instance: str, webhook_path: str) -> dict | None:
    """Crea instancia Evolution con webhook apuntando al worker correspondiente."""
    webhook_url = f"{BACKEND_BASE_URL}{webhook_path}"
    body = {
        "instanceName": instance,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
        "webhook": {
            "url": webhook_url,
            "byEvents": False,
            "base64": False,
            "events": ["MESSAGES_UPSERT"],
        },
    }
    status, data = _evo_post("/instance/create", body)
    if status in (200, 201):
        return data
    print(f"[MICA-ONB] Error crear instancia {instance}: HTTP {status} — {data}")
    return None


def _instance_get_qr(instance: str) -> str:
    """Retorna el QR base64 de la instancia (o '' si ya conectada)."""
    status, data = _evo_get(f"/instance/connect/{instance}")
    if status != 200 or not data:
        return ""
    return data.get("base64", "") or data.get("code", "") or ""


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/iniciar")
async def iniciar(slug: str = Query(..., min_length=2, max_length=60)):
    slug = slug.strip().lower()
    if not _slug_valido(slug):
        raise HTTPException(400, detail="Slug inválido")

    cliente = _buscar_cliente(slug)
    if not cliente:
        raise HTTPException(
            404,
            detail=(
                "No encontramos tu cuenta. Contactá a Micaela para que la active "
                "con el brief que completaste."
            ),
        )

    # Mientras Robert no este aprobado: todos los clientes Mica van por Evolution.
    # Cuando sea aprobado, se chequeara cliente["provider"] == "meta" y se routeara
    # al flujo Embedded Signup.
    provider = cliente["provider"]
    if provider != "evolution":
        return JSONResponse(
            {
                "provider": provider,
                "mensaje": (
                    "Este cliente está configurado para Tech Provider Meta. "
                    "El flujo Embedded Signup se activa en otra URL."
                ),
                "nombre_empresa": cliente["nombre_empresa"],
            }
        )

    instance = cliente["evolution_instance"]

    # Crear instancia si no existe
    if not _instance_exists(instance):
        _instance_create(instance, DEFAULT_WORKER_PATH)

    return {
        "slug": slug,
        "provider": "evolution",
        "nombre_empresa": cliente["nombre_empresa"],
        "numero": cliente["numero_whatsapp"] or "Tu WhatsApp Business",
        "chatwoot_url": cliente["chatwoot_url"],
        "crm_url": cliente["crm_url"],
        "instance": instance,
    }


@router.get("/qr")
async def qr(slug: str = Query(..., min_length=2, max_length=60)):
    slug = slug.strip().lower()
    if not _slug_valido(slug):
        raise HTTPException(400, detail="Slug inválido")

    cliente = _buscar_cliente(slug)
    if not cliente:
        raise HTTPException(404, detail="Cliente no encontrado")

    instance = cliente["evolution_instance"]
    estado = _instance_estado(instance)

    if estado == "open":
        return {"qrcode": "", "state": "open"}

    qr_b64 = _instance_get_qr(instance)
    return {"qrcode": qr_b64, "state": estado}


@router.get("/estado")
async def estado(slug: str = Query(..., min_length=2, max_length=60)):
    slug = slug.strip().lower()
    if not _slug_valido(slug):
        raise HTTPException(400, detail="Slug inválido")

    cliente = _buscar_cliente(slug)
    if not cliente:
        raise HTTPException(404, detail="Cliente no encontrado")

    instance = cliente["evolution_instance"]
    state = _instance_estado(instance)
    return {"slug": slug, "instance": instance, "state": state}
