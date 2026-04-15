"""
Router SaaS — /tenant/{slug}
GET   /tenant/{slug}        → config pública del tenant (nombre, logo, colores, api_prefix)
POST  /tenant/{slug}/auth   → valida PIN, devuelve token simple
PATCH /tenant/{slug}/marca  → actualiza branding (nombre, logo, colores, ciudad, moneda)
"""
import os
import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from supabase import create_client

router = APIRouter(prefix="/tenant", tags=["SaaS Tenants"])

# ── Versión CRM (el frontend consulta esto para mostrar alerta de actualización)
_CRM_VERSION = {
    "version": "1.3.0",
    "changelog": "Datos 100% reales — eliminados placeholders y nombres de demo",
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
    try:
        res = sb.table("tenants").select("*").eq("slug", slug).eq("activo", True).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' no encontrado")
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

    # API URL: por defecto Coolify Arnaldo, pero algunos tenants tienen su propia infra
    api_url = t.get("api_url", "")
    if not api_url:
        # Tenants que viven en Coolify Robert (Hetzner) — PostgreSQL propio
        if t.get("slug") in ("robert", "demo"):
            api_url = "https://agentes.lovbot.ai"
        else:
            api_url = "https://agentes.arnaldoayalaestratega.cloud"

    return {
        "slug":           t.get("slug", slug),
        "nombre":         t.get("nombre", ""),
        "subniche":       t.get("subniche", ""),
        "api_prefix":     t.get("api_prefix", ""),
        "api_url":        api_url,
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


class CambiarPinRequest(BaseModel):
    pin_actual: str
    pin_nuevo: str

@router.patch("/{slug}/pin")
def tenant_cambiar_pin(slug: str, body: CambiarPinRequest):
    """Cambia el PIN del tenant. Requiere PIN actual para validar."""
    t = _get_tenant(slug)
    pin_hash = t.get("pin_hash")
    if pin_hash:
        ingresado = hashlib.sha256(body.pin_actual.encode()).hexdigest()
        if ingresado != pin_hash:
            raise HTTPException(status_code=401, detail="PIN actual incorrecto")
    if len(body.pin_nuevo) != 4 or not body.pin_nuevo.isdigit():
        raise HTTPException(status_code=422, detail="El PIN debe ser de 4 dígitos")
    nuevo_hash = hashlib.sha256(body.pin_nuevo.encode()).hexdigest()
    sb = _get_sb()
    sb.table("tenants").update({
        "pin_hash": nuevo_hash,
        "updated_at": "now()",
    }).eq("slug", slug).execute()
    return {"status": "ok", "mensaje": "PIN actualizado correctamente"}


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


# ── ADMIN ENDPOINTS ──────────────────────────────────────────────────────────
# Mapa token → agencia. Cada agencia ve solo sus propios tenants.
_ADMIN_TOKENS: dict[str, str] = {
    os.environ.get("LOVBOT_ADMIN_TOKEN",    "lovbot-admin-2026"):    "lovbot",
    os.environ.get("SYSTEM_IA_ADMIN_TOKEN", "system-ia-admin-2026"): "system-ia",
}

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


def _get_agencia(request: Request) -> str:
    """Valida el token y devuelve la agencia correspondiente. 403 si inválido."""
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    agencia = _ADMIN_TOKENS.get(token)
    if not agencia:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return agencia


@admin_router.get("/tenants")
def admin_list_tenants(request: Request):
    """Lista todos los tenants de la agencia autenticada."""
    agencia = _get_agencia(request)

    sb = _get_sb()
    res = sb.table("tenants").select("*").eq("agencia", agencia).order("created_at", desc=False).execute()
    from datetime import date
    tenants = []
    for t in (res.data or []):
        estado = t.get("estado_pago", "trial")
        fecha_vence = t.get("fecha_vence")
        if estado not in ("suspendido",) and fecha_vence:
            try:
                if date.fromisoformat(str(fecha_vence)[:10]) < date.today():
                    estado = "vencido"
            except (ValueError, TypeError):
                pass
        tenants.append({
            "id":              t["id"],
            "slug":            t["slug"],
            "nombre":          t["nombre"],
            "subniche":        t.get("subniche"),
            "plan":            t.get("plan", "trial"),
            "estado_pago":     estado,
            "fecha_alta":      t.get("fecha_alta"),
            "fecha_vence":     fecha_vence,
            "email_admin":     t.get("email_admin"),
            "telefono_admin":  t.get("telefono_admin"),
            "monto_mensual":   t.get("monto_mensual", 0),
            "moneda_pago":     t.get("moneda_pago", "USD"),
            "ciudad":          t.get("ciudad"),
            "activo":          t.get("activo", True),
            "notas":           t.get("notas"),
            "logo_url":        t.get("logo_url"),
        })
    return {"total": len(tenants), "tenants": tenants}


class RenovarRequest(BaseModel):
    dias: int = 30

@admin_router.patch("/tenants/{slug}/renovar")
def admin_renovar(slug: str, body: RenovarRequest, request: Request):
    """Renueva suscripción: suma N días a fecha_vence."""
    _get_agencia(request)

    t = _get_tenant(slug)
    from datetime import date, timedelta
    fecha_actual = t.get("fecha_vence")
    if fecha_actual:
        try:
            base = date.fromisoformat(str(fecha_actual)[:10])
            if base < date.today():
                base = date.today()
        except (ValueError, TypeError):
            base = date.today()
    else:
        base = date.today()

    nueva_fecha = base + timedelta(days=body.dias)
    sb = _get_sb()
    sb.table("tenants").update({
        "fecha_vence": nueva_fecha.isoformat(),
        "estado_pago": "al_dia",
        "updated_at": "now()",
    }).eq("slug", slug).execute()

    return {"status": "ok", "slug": slug, "fecha_vence": nueva_fecha.isoformat(),
            "estado_pago": "al_dia", "dias": body.dias}


@admin_router.patch("/tenants/{slug}/suspender")
def admin_suspender(slug: str, request: Request):
    """Suspende un tenant (override manual)."""
    _get_agencia(request)

    _get_tenant(slug)
    sb = _get_sb()
    sb.table("tenants").update({
        "estado_pago": "suspendido",
        "updated_at": "now()",
    }).eq("slug", slug).execute()
    return {"status": "ok", "slug": slug, "estado_pago": "suspendido"}


@admin_router.patch("/tenants/{slug}/reactivar")
def admin_reactivar(slug: str, request: Request):
    """Reactiva un tenant suspendido."""
    _get_agencia(request)

    _get_tenant(slug)
    sb = _get_sb()
    sb.table("tenants").update({
        "estado_pago": "al_dia",
        "updated_at": "now()",
    }).eq("slug", slug).execute()
    return {"status": "ok", "slug": slug, "estado_pago": "al_dia"}


class NuevoTenantRequest(BaseModel):
    slug:           str
    nombre:         str
    pin:            str = "0000"
    subniche:       str = "inmobiliaria"
    plan:           str = "starter"
    ciudad:         str = ""
    moneda:         str = "USD"
    email_admin:    str = ""
    telefono_admin: str = ""
    monto_mensual:  float = 0
    moneda_pago:    str = "USD"
    dias:           int = 30
    notas:          str = ""

@admin_router.post("/tenants")
def admin_crear_tenant(body: NuevoTenantRequest, request: Request):
    """Crea un nuevo tenant/cliente del CRM. Lo asigna a la agencia del token."""
    agencia = _get_agencia(request)

    sb = _get_sb()
    existing = sb.table("tenants").select("id").eq("slug", body.slug).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail=f"Tenant '{body.slug}' ya existe")

    from datetime import date, timedelta
    pin_hash = hashlib.sha256(body.pin.encode()).hexdigest()
    nuevo = {
        "slug":           body.slug,
        "nombre":         body.nombre,
        "subniche":       body.subniche,
        "api_prefix":     "/demos/inmobiliaria",
        "pin_hash":       pin_hash,
        "plan":           body.plan,
        "estado_pago":    "al_dia",
        "fecha_alta":     date.today().isoformat(),
        "fecha_vence":    (date.today() + timedelta(days=body.dias)).isoformat(),
        "email_admin":    body.email_admin,
        "telefono_admin": body.telefono_admin,
        "monto_mensual":  body.monto_mensual,
        "moneda_pago":    body.moneda_pago,
        "ciudad":         body.ciudad,
        "moneda":         body.moneda,
        "notas":          body.notas,
        "agencia":        agencia,
        "activo":         True,
    }
    res = sb.table("tenants").insert(nuevo).execute()
    return {"status": "ok", "tenant": res.data[0] if res.data else nuevo}


class UpdateApiPrefixRequest(BaseModel):
    api_prefix: str

@admin_router.patch("/tenants/{slug}/api-prefix")
def admin_update_api_prefix(slug: str, body: UpdateApiPrefixRequest, request: Request):
    """Actualiza el api_prefix de un tenant (útil para apuntar a servidor diferente)."""
    _get_agencia(request)
    _get_tenant(slug)
    sb = _get_sb()
    if not body.api_prefix:
        raise HTTPException(status_code=400, detail="api_prefix requerido")
    sb.table("tenants").update({"api_prefix": body.api_prefix, "updated_at": "now()"}).eq("slug", slug).execute()
    return {"status": "ok", "slug": slug, "api_prefix": body.api_prefix}
