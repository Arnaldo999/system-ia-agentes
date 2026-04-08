"""
Router SaaS — /tenant/{slug}
GET   /tenant/{slug}        → config pública del tenant (nombre, logo, colores, api_prefix)
POST  /tenant/{slug}/auth   → valida PIN, devuelve token simple
PATCH /tenant/{slug}/marca  → actualiza branding (nombre, logo, colores, ciudad, moneda)
"""
import os
import hashlib
import secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

router = APIRouter(prefix="/tenant", tags=["SaaS Tenants"])

# ── Versión CRM (el frontend consulta esto para mostrar alerta de actualización)
_CRM_VERSION = {
    "version": "1.0.0",
    "changelog": "Agenda sincronizada con bot + Cal.com, subnichos, confirmación de citas",
}

# Endpoint fuera del prefix /tenant para que sea /crm/version
from fastapi import APIRouter as _R
crm_router = _R(tags=["CRM"])

@crm_router.get("/crm/version")
def crm_version():
    return _CRM_VERSION

# ── Supabase client ────────────────────────────────────────────────────────────
_sb = None

def _get_sb():
    global _sb
    if _sb is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _sb = create_client(url, key)
    return _sb


def _get_tenant(slug: str) -> dict:
    sb = _get_sb()
    res = sb.table("tenants").select("*").eq("slug", slug).eq("activo", True).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' no encontrado")
    return res.data


# ── Schemas ────────────────────────────────────────────────────────────────────
class AuthRequest(BaseModel):
    pin: str

class MarcaUpdate(BaseModel):
    nombre:         str | None = None
    logo_url:       str | None = None
    color_primario: str | None = None
    color_acento:   str | None = None
    ciudad:         str | None = None
    moneda:         str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/{slug}")
def tenant_config(slug: str):
    """Devuelve configuración pública del tenant (sin datos sensibles)."""
    t = _get_tenant(slug)
    # Calcular estado_pago real según fecha_vence
    estado = t.get("estado_pago", "trial")
    fecha_vence = t.get("fecha_vence")
    if estado not in ("suspendido",) and fecha_vence:
        from datetime import date
        try:
            vence = date.fromisoformat(str(fecha_vence)[:10])
            if vence < date.today():
                estado = "vencido"
        except (ValueError, TypeError):
            pass

    return {
        "slug":           t["slug"],
        "nombre":         t["nombre"],
        "subniche":       t["subniche"],
        "api_prefix":     t["api_prefix"],
        "logo_url":       t.get("logo_url"),
        "color_primario": t.get("color_primario", "#0A261A"),
        "color_acento":   t.get("color_acento", "#E5B239"),
        "ciudad":         t.get("ciudad"),
        "moneda":         t.get("moneda", "USD"),
        "requiere_pin":   bool(t.get("pin_hash")),
        "estado_pago":    estado,
        "plan":           t.get("plan", "trial"),
        "fecha_vence":    fecha_vence,
    }


@router.post("/{slug}/auth")
def tenant_auth(slug: str, body: AuthRequest):
    """Valida PIN del tenant. Devuelve token de sesión simple."""
    t = _get_tenant(slug)

    pin_hash = t.get("pin_hash")
    if not pin_hash:
        # Sin PIN configurado → acceso libre
        return {"status": "ok", "token": "public", "nombre": t["nombre"]}

    # Validar PIN (SHA-256)
    ingresado = hashlib.sha256(body.pin.encode()).hexdigest()
    if ingresado != pin_hash:
        raise HTTPException(status_code=401, detail="PIN incorrecto")

    # Token simple: no necesitamos JWT por ahora
    token = secrets.token_urlsafe(32)
    return {
        "status": "ok",
        "token":  token,
        "nombre": t["nombre"],
    }


@router.patch("/{slug}/marca")
def tenant_update_marca(slug: str, body: MarcaUpdate):
    """Actualiza branding del tenant: nombre, logo, colores, ciudad, moneda."""
    _get_tenant(slug)  # verifica que existe
    sb = _get_sb()
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    update["updated_at"] = "now()"
    res = sb.table("tenants").update(update).eq("slug", slug).execute()
    t = res.data[0] if res.data else {}
    return {
        "status":         "ok",
        "slug":           slug,
        "nombre":         t.get("nombre"),
        "logo_url":       t.get("logo_url"),
        "color_primario": t.get("color_primario"),
        "color_acento":   t.get("color_acento"),
        "ciudad":         t.get("ciudad"),
        "moneda":         t.get("moneda"),
    }
