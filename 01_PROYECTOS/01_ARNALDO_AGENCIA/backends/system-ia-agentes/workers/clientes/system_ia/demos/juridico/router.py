"""
Router CRM Estudio de Marcas (Propiedad Industrial) — Mica Demo
================================================================
Endpoints REST para CRM especializado en estudios jurídicos que registran
marcas comerciales ante INPI Argentina.

Nicho específico (no jurídico genérico): registro de marcas, oposiciones,
DJUM, renovaciones, vigilancia del Boletín INPI.

ARQUITECTURA: base Airtable DEDICADA appSjeRUoBGZo5DtO
Diseño basado en el modelo real de Mica (Rawson IP Manager — base44 prototipo).

Tablas:
  - Estudios_Juridicos
  - Abogados
  - Clientes_Estudio (titulares de marcas)
  - Leads (consultas de publicidad/web)
  - Propuestas (cotizaciones de registro)
  - Marcas (en trámite/concedidas ante INPI)
  - Oposiciones (8 etapas INPI Resol. 183/18 + 295/24)
  - Comunicaciones_Oposicion (notificaciones a clientes)
  - Analisis_Confundibilidad (pizarra socios)
  - Marcas_Para_Cargar (buffer admin)
  - Turnos (Cal.com)
  - Alertas_Enviadas

Path montado en main.py:
    app.include_router(juridico_router, prefix="/clientes/system_ia/demos/juridico")
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("juridico.router")

# ── Config ────────────────────────────────────────────────────────────────────
TENANT_SLUG = "mica-demo-juridico"
SUBNICHO = "marcas-inpi"

AIRTABLE_TOKEN = (
    os.environ.get("AIRTABLE_API_KEY", "")
    or os.environ.get("AIRTABLE_TOKEN", "")
    or os.environ.get("MICA_AIRTABLE_TOKEN", "")
)
AIRTABLE_BASE_ID = (
    os.environ.get("MICA_DEMO_JURIDICO_BASE_ID", "")
    or "appSjeRUoBGZo5DtO"
)

# Tablas (env vars con fallback a IDs hardcodeados)
TABLE_ESTUDIOS = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ESTUDIOS", "tbluLhi7Dj27JNwxt")
TABLE_ABOGADOS = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ABOGADOS", "tblbxhuWCNGFhM60R")
TABLE_CLIENTES = os.environ.get("MICA_DEMO_JURIDICO_TABLE_CLIENTES", "tblM2IZ15DAgRCgXO")
TABLE_LEADS    = os.environ.get("MICA_DEMO_JURIDICO_TABLE_LEADS",    "tblQcKgQ6cGKjElMz")
TABLE_PROPUESTAS    = os.environ.get("MICA_DEMO_JURIDICO_TABLE_PROPUESTAS",    "tbl6wdMibXg70NGdj")
TABLE_MARCAS        = os.environ.get("MICA_DEMO_JURIDICO_TABLE_MARCAS",        "tblZnXVhccJyRue6i")
TABLE_OPOSICIONES   = os.environ.get("MICA_DEMO_JURIDICO_TABLE_OPOSICIONES",   "tblttukSCkzQsChhG")
TABLE_COMUNICACIONES = os.environ.get("MICA_DEMO_JURIDICO_TABLE_COMUNICACIONES", "tblX6blYSOCeyu8ve")
TABLE_ANALISIS      = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ANALISIS",      "tblcZlzitnTxRevYQ")
TABLE_PARA_CARGAR   = os.environ.get("MICA_DEMO_JURIDICO_TABLE_PARA_CARGAR",   "tblji7DIl9FwdZ06Q")
TABLE_TURNOS        = os.environ.get("MICA_DEMO_JURIDICO_TABLE_TURNOS",        "tblIg1rFN5e4IKB4s")
TABLE_ALERTAS       = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ALERTAS",       "tbl13tRhUoMSUsaKc")

router = APIRouter(tags=["juridico-mica-demo"])


# ── Helper Airtable ───────────────────────────────────────────────────────────

def _airtable_url(table_id: str) -> str:
    if not AIRTABLE_BASE_ID or not table_id:
        raise HTTPException(500, "Airtable base/table no configurados")
    return f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"


def _headers() -> dict:
    if not AIRTABLE_TOKEN:
        raise HTTPException(500, "AIRTABLE_TOKEN no configurado")
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def _at_get(table_id: str, params: Optional[dict] = None) -> dict:
    p = dict(params or {})
    if "pageSize" not in p:
        p["pageSize"] = 100
    elif p["pageSize"] > 100:
        p["pageSize"] = 100
    r = requests.get(_airtable_url(table_id), headers=_headers(), params=p, timeout=15)
    if r.status_code != 200:
        logger.error("Airtable GET %s: %s — %s", table_id, r.status_code, r.text[:200])
        raise HTTPException(r.status_code, f"Airtable error: {r.text[:200]}")
    return r.json()


def _at_post(table_id: str, fields: dict) -> dict:
    payload = {"records": [{"fields": fields}], "typecast": True}
    r = requests.post(_airtable_url(table_id), headers=_headers(), json=payload, timeout=15)
    if r.status_code not in (200, 201):
        logger.error("Airtable POST %s: %s — %s", table_id, r.status_code, r.text[:200])
        raise HTTPException(r.status_code, f"Airtable error: {r.text[:200]}")
    return r.json()["records"][0]


def _at_patch(table_id: str, record_id: str, fields: dict) -> dict:
    payload = {"fields": fields, "typecast": True}
    r = requests.patch(
        f"{_airtable_url(table_id)}/{record_id}",
        headers=_headers(), json=payload, timeout=15,
    )
    if r.status_code != 200:
        logger.error("Airtable PATCH %s/%s: %s — %s", table_id, record_id, r.status_code, r.text[:200])
        raise HTTPException(r.status_code, f"Airtable error: {r.text[:200]}")
    return r.json()


def _at_delete(table_id: str, record_id: str) -> dict:
    r = requests.delete(f"{_airtable_url(table_id)}/{record_id}", headers=_headers(), timeout=15)
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"Airtable error: {r.text[:200]}")
    return r.json()


def _serialize(rec: dict) -> dict:
    return {"id": rec["id"], **rec.get("fields", {})}


def _list(table_id: str, **params) -> list:
    """Helper genérico para listar registros con params Airtable."""
    data = _at_get(table_id, params)
    return [_serialize(r) for r in data.get("records", [])]


# ── Modelos Pydantic genéricos ────────────────────────────────────────────────

class GenericCreate(BaseModel):
    """Modelo abierto — recibe cualquier campo y se pasa directo a Airtable."""
    class Config:
        extra = "allow"


# ════════════════════════════════════════════════════════════════════════════
# HEALTH + CONFIG
# ════════════════════════════════════════════════════════════════════════════

@router.get("/crm/health")
def health():
    return {
        "ok": True,
        "tenant": TENANT_SLUG,
        "subnicho": SUBNICHO,
        "airtable_configured": bool(AIRTABLE_TOKEN and AIRTABLE_BASE_ID),
        "tables": {
            "estudios": bool(TABLE_ESTUDIOS),
            "abogados": bool(TABLE_ABOGADOS),
            "clientes": bool(TABLE_CLIENTES),
            "leads": bool(TABLE_LEADS),
            "propuestas": bool(TABLE_PROPUESTAS),
            "marcas": bool(TABLE_MARCAS),
            "oposiciones": bool(TABLE_OPOSICIONES),
            "comunicaciones": bool(TABLE_COMUNICACIONES),
            "analisis": bool(TABLE_ANALISIS),
            "para_cargar": bool(TABLE_PARA_CARGAR),
            "turnos": bool(TABLE_TURNOS),
            "alertas": bool(TABLE_ALERTAS),
        },
    }


@router.get("/crm/dashboard")
def dashboard():
    """Stats agregados para el panel principal."""
    out = {
        "tenant": TENANT_SLUG,
        "leads_nuevos": 0, "leads_calificados": 0, "leads_clientes": 0,
        "propuestas_pendientes": 0, "propuestas_aceptadas": 0,
        "marcas_total": 0, "marcas_en_tramite": 0, "marcas_concedidas": 0, "marcas_con_oposicion": 0,
        "oposiciones_activas": 0, "oposiciones_recientes": [],
        "comunicaciones_borrador": 0, "comunicaciones_enviadas": 0,
        "marcas_para_cargar_pendientes": 0,
        "analisis_en_curso": 0,
        "djum_proximos_90d": 0,
        "renovaciones_proximas_180d": 0,
    }

    # Leads
    try:
        leads = _list(TABLE_LEADS, pageSize=100)
        out["leads_nuevos"] = sum(1 for l in leads if l.get("Estado") == "Nuevo")
        out["leads_calificados"] = sum(1 for l in leads if l.get("Estado") in ("Calificado", "Agendado"))
        out["leads_clientes"] = sum(1 for l in leads if l.get("Estado") == "Cliente")
    except Exception:
        pass

    # Propuestas
    try:
        props = _list(TABLE_PROPUESTAS, pageSize=100)
        out["propuestas_pendientes"] = sum(1 for p in props if p.get("Estado") == "Pendiente")
        out["propuestas_aceptadas"] = sum(1 for p in props if p.get("Estado") == "Aceptada")
    except Exception:
        pass

    # Marcas
    try:
        marcas = _list(TABLE_MARCAS, pageSize=100)
        out["marcas_total"] = len(marcas)
        out["marcas_en_tramite"] = sum(1 for m in marcas if m.get("Estado") in ("En trámite", "Solicitada", "En publicación", "En estudio"))
        out["marcas_concedidas"] = sum(1 for m in marcas if m.get("Estado") in ("Concedida", "Renovada"))
        out["marcas_con_oposicion"] = sum(1 for m in marcas if m.get("Estado") == "Con oposición")
    except Exception:
        pass

    # Oposiciones
    try:
        opos = _list(TABLE_OPOSICIONES, pageSize=100)
        activas = [o for o in opos if o.get("Estado") in ("Activa", "En espera")]
        out["oposiciones_activas"] = len(activas)
        out["oposiciones_recientes"] = sorted(
            opos, key=lambda x: x.get("Fecha Inicio", ""), reverse=True
        )[:5]
    except Exception:
        pass

    # Comunicaciones
    try:
        comm = _list(TABLE_COMUNICACIONES, pageSize=100)
        out["comunicaciones_borrador"] = sum(1 for c in comm if c.get("Estado") in ("Borrador", "Vista previa"))
        out["comunicaciones_enviadas"] = sum(1 for c in comm if c.get("Estado") in ("Enviada", "Aceptada"))
    except Exception:
        pass

    # Marcas para cargar
    try:
        cargar = _list(TABLE_PARA_CARGAR, pageSize=100)
        out["marcas_para_cargar_pendientes"] = sum(1 for c in cargar if c.get("Estado") in ("Pendiente", "En curso"))
    except Exception:
        pass

    # Análisis
    try:
        anal = _list(TABLE_ANALISIS, pageSize=100)
        out["analisis_en_curso"] = sum(1 for a in anal if a.get("Estado") == "En análisis")
    except Exception:
        pass

    return out


# ════════════════════════════════════════════════════════════════════════════
# CRUD GENÉRICO (factory de endpoints)
# ════════════════════════════════════════════════════════════════════════════

def _make_crud_endpoints(prefix: str, table_id_func, plural_key: str):
    """Genera endpoints GET / POST / PATCH / DELETE para una tabla."""

    @router.get(f"/crm/{prefix}")
    def listar(estado: Optional[str] = None, sort_field: Optional[str] = None, sort_dir: str = "desc"):
        params = {"pageSize": 100}
        if sort_field:
            params["sort[0][field]"] = sort_field
            params["sort[0][direction]"] = sort_dir
        if estado:
            params["filterByFormula"] = f"{{Estado}}='{estado}'"
        items = _list(table_id_func(), **params)
        return {plural_key: items}

    @router.post(f"/crm/{prefix}")
    def crear(payload: dict):
        rec = _at_post(table_id_func(), payload)
        return _serialize(rec)

    @router.patch(f"/crm/{prefix}/{{record_id}}")
    def actualizar(record_id: str, payload: dict):
        rec = _at_patch(table_id_func(), record_id, payload)
        return _serialize(rec)

    @router.delete(f"/crm/{prefix}/{{record_id}}")
    def eliminar(record_id: str):
        _at_delete(table_id_func(), record_id)
        return {"ok": True, "id": record_id}

    listar.__name__ = f"listar_{prefix}"
    crear.__name__ = f"crear_{prefix}"
    actualizar.__name__ = f"actualizar_{prefix}"
    eliminar.__name__ = f"eliminar_{prefix}"


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS POR ENTIDAD
# ════════════════════════════════════════════════════════════════════════════

# ── Estudio (1 solo registro) ─────────────────────────────────────────────────

@router.get("/crm/estudio")
def obtener_estudio():
    items = _list(TABLE_ESTUDIOS, maxRecords=1)
    return {"estudio": items[0] if items else None}


# ── Abogados ─────────────────────────────────────────────────────────────────

_make_crud_endpoints("abogados", lambda: TABLE_ABOGADOS, "abogados")


# ── Clientes ──────────────────────────────────────────────────────────────────

_make_crud_endpoints("clientes", lambda: TABLE_CLIENTES, "clientes")


@router.get("/crm/clientes/search")
def buscar_clientes(q: str = Query(..., min_length=2)):
    q_safe = q.replace("'", "")
    formula = (
        f"OR("
        f"FIND(LOWER('{q_safe}'),LOWER({{Nombre Completo / Razón Social}}))>0,"
        f"FIND('{q_safe}',{{DNI / CUIT}})>0"
        f")"
    )
    items = _list(TABLE_CLIENTES, filterByFormula=formula, maxRecords=10)
    return {"clientes": items}


# ── Leads ────────────────────────────────────────────────────────────────────

_make_crud_endpoints("leads", lambda: TABLE_LEADS, "leads")


# ── Propuestas ────────────────────────────────────────────────────────────────

_make_crud_endpoints("propuestas", lambda: TABLE_PROPUESTAS, "propuestas")


# ── Marcas ────────────────────────────────────────────────────────────────────

_make_crud_endpoints("marcas", lambda: TABLE_MARCAS, "marcas")


@router.get("/crm/marcas/proximos-vencimientos")
def marcas_proximos_vencimientos(dias: int = Query(180, ge=1, le=730)):
    """Marcas con vencimiento próximo (renovación)."""
    formula = f"AND({{Estado}}='Concedida',DATETIME_DIFF({{Fecha Vencimiento}},TODAY(),'days')<={dias},DATETIME_DIFF({{Fecha Vencimiento}},TODAY(),'days')>=0)"
    items = _list(TABLE_MARCAS, filterByFormula=formula, **{"sort[0][field]": "Fecha Vencimiento"})
    return {"marcas": items}


@router.get("/crm/marcas/djum-proximos")
def marcas_djum_proximos(dias: int = Query(90, ge=1, le=365)):
    formula = f"AND({{Estado}}='Concedida',DATETIME_DIFF({{Fecha DJUM}},TODAY(),'days')<={dias},DATETIME_DIFF({{Fecha DJUM}},TODAY(),'days')>=0)"
    items = _list(TABLE_MARCAS, filterByFormula=formula, **{"sort[0][field]": "Fecha DJUM"})
    return {"marcas": items}


# ── Oposiciones ──────────────────────────────────────────────────────────────

_make_crud_endpoints("oposiciones", lambda: TABLE_OPOSICIONES, "oposiciones")


@router.get("/crm/oposiciones/activas")
def oposiciones_activas():
    formula = "OR({Estado}='Activa',{Estado}='En espera')"
    items = _list(TABLE_OPOSICIONES, filterByFormula=formula, **{"sort[0][field]": "Fecha Inicio", "sort[0][direction]": "desc"})
    return {"oposiciones": items}


# ── Comunicaciones de Oposición ──────────────────────────────────────────────

_make_crud_endpoints("comunicaciones", lambda: TABLE_COMUNICACIONES, "comunicaciones")


# ── Análisis de Confundibilidad ──────────────────────────────────────────────

_make_crud_endpoints("analisis", lambda: TABLE_ANALISIS, "analisis")


# ── Marcas para Cargar ──────────────────────────────────────────────────────

_make_crud_endpoints("marcas-cargar", lambda: TABLE_PARA_CARGAR, "marcas_para_cargar")


# ── Turnos (Cal.com) ────────────────────────────────────────────────────────

_make_crud_endpoints("turnos", lambda: TABLE_TURNOS, "turnos")


# ── Alertas Enviadas ────────────────────────────────────────────────────────

_make_crud_endpoints("alertas", lambda: TABLE_ALERTAS, "alertas")
