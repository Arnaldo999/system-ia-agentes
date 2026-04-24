"""
Router CRM jurídico — Mica Demo
================================
Endpoints REST para el CRM Estudio Jurídico Demo.

ARQUITECTURA: base Airtable DEDICADA para este demo.
- Base ID: appSjeRUoBGZo5DtO (Estudio Jurídico Demo) — propiedad de Mica/System IA
- Diferencia con inmobiliaria Mica (que usa base compartida appA8QxIhBYYAHw0F con campo Tenant):
  acá cada demo tiene SU base aislada → no hace falta filtrar por Tenant.

Cuando se clone para Arnaldo (workspace propio): duplicar esta base completa,
configurar nuevas env vars apuntando al base_id Arnaldo, y listo.

Path montado en main.py:
    app.include_router(juridico_router, prefix="/clientes/system_ia/demos/juridico")

Endpoints expuestos:
    GET    /crm/health
    GET    /crm/estudio                            # info del estudio (1 solo registro)
    GET    /crm/abogados                           # lista de abogados del estudio
    POST   /crm/abogados                           # crear abogado
    PATCH  /crm/abogados/{record_id}               # actualizar abogado
    GET    /crm/clientes                           # lista de clientes del estudio
    POST   /crm/clientes                           # crear cliente
    PATCH  /crm/clientes/{record_id}               # actualizar cliente
    DELETE /crm/clientes/{record_id}               # soft delete (Estado=Cerrado)
    GET    /crm/clientes/search?q=...              # autocomplete por nombre/DNI
    GET    /crm/tramites                           # lista de trámites (con filtros)
    GET    /crm/tramites/agenda                    # próximos vencimientos ordenados
    POST   /crm/tramites                           # crear trámite
    PATCH  /crm/tramites/{record_id}               # actualizar trámite
    DELETE /crm/tramites/{record_id}               # cerrar trámite (soft)
    GET    /crm/alertas                            # historial alertas enviadas
    POST   /crm/alertas                            # registrar alerta enviada (lo dispara n8n / bot)
    GET    /crm/dashboard                          # stats: total clientes, trámites por urgencia, etc.

Aislamiento: como la base es dedicada, NO hay filtro de Tenant en las queries.
Cada operación va directo contra la tabla. Los datos ya están aislados por base.

NOTA IDs Airtable: son strings tipo "rec...". NUNCA hacer parseInt en el frontend.
Ver feedback_crm_v3_mica_persona_unica.md.
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from datetime import datetime, date

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("juridico.router")

# ── Config ────────────────────────────────────────────────────────────────────
TENANT_SLUG = "mica-demo-juridico"  # solo para identificación interna / Supabase
SUBNICHO = "juridico"

AIRTABLE_TOKEN = (
    os.environ.get("AIRTABLE_API_KEY", "")
    or os.environ.get("AIRTABLE_TOKEN", "")
    or os.environ.get("MICA_AIRTABLE_TOKEN", "")
)
# Base DEDICADA para este demo (Mica creó "Estudio Jurídico Demo")
# NO confundir con appA8QxIhBYYAHw0F (base inmobiliaria Mica)
AIRTABLE_BASE_ID = (
    os.environ.get("MICA_DEMO_JURIDICO_BASE_ID", "")
    or "appSjeRUoBGZo5DtO"  # Estudio Jurídico Demo (Mica) — fallback hardcoded
)

# Tablas (env vars completar tras crearlas en Airtable)
TABLE_ESTUDIOS = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ESTUDIOS", "")
TABLE_ABOGADOS = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ABOGADOS", "")
TABLE_CLIENTES = os.environ.get("MICA_DEMO_JURIDICO_TABLE_CLIENTES", "")
TABLE_TRAMITES = os.environ.get("MICA_DEMO_JURIDICO_TABLE_TRAMITES", "")
TABLE_ALERTAS  = os.environ.get("MICA_DEMO_JURIDICO_TABLE_ALERTAS", "")

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
    """GET a Airtable — base dedicada, no requiere filtro Tenant."""
    p = dict(params or {})

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
    data = r.json()
    return data["records"][0]


def _at_patch(table_id: str, record_id: str, fields: dict) -> dict:
    payload = {"fields": fields, "typecast": True}
    r = requests.patch(
        f"{_airtable_url(table_id)}/{record_id}",
        headers=_headers(),
        json=payload,
        timeout=15,
    )
    if r.status_code != 200:
        logger.error("Airtable PATCH %s/%s: %s — %s", table_id, record_id, r.status_code, r.text[:200])
        raise HTTPException(r.status_code, f"Airtable error: {r.text[:200]}")
    return r.json()


def _serialize_record(rec: dict) -> dict:
    """Convierte registro Airtable a dict plano con id+fields."""
    return {"id": rec["id"], **rec.get("fields", {})}


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class AbogadoCreate(BaseModel):
    estudio_id: Optional[str] = None  # link to Estudios_Juridicos
    nombre_completo: str
    especialidad: Optional[str] = None
    telefono_whatsapp: Optional[str] = None
    email: Optional[str] = None
    matricula: Optional[str] = None
    activo: bool = True
    recibe_alertas_whatsapp: bool = True
    notas: Optional[str] = None


class ClienteCreate(BaseModel):
    estudio_id: Optional[str] = None
    tipo: str = "Persona Física"  # o "Persona Jurídica"
    nombre_completo: str = Field(..., description="Nombre completo o razón social")
    dni_cuit: Optional[str] = None
    telefono_whatsapp: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    abogado_asignado_id: Optional[str] = None
    notas_iniciales: Optional[str] = None
    recibe_alertas_whatsapp: bool = True


class TramiteCreate(BaseModel):
    estudio_id: Optional[str] = None
    cliente_id: str  # required
    abogado_responsable_id: Optional[str] = None
    tipo_tramite: str  # texto libre
    categoria: Optional[str] = None  # Civil/Laboral/etc
    descripcion: Optional[str] = None
    fecha_inicio: Optional[str] = None  # ISO date
    fecha_vencimiento: str  # ISO date — REQUIRED
    estado: str = "Activo"
    fuero_juzgado: Optional[str] = None
    n_expediente: Optional[str] = None
    notas_internas: Optional[str] = None
    notas_cliente: Optional[str] = None


class AlertaCreate(BaseModel):
    tramite_id: str
    cliente_destinatario_id: str
    fecha_envio: Optional[str] = None  # default: ahora
    dias_anticipacion: int  # 30/15/7/3/1/0/-N
    mensaje_enviado: str
    canal: str = "WhatsApp"
    estado_envio: str = "Enviado"


# ── Endpoints ─────────────────────────────────────────────────────────────────

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
            "tramites": bool(TABLE_TRAMITES),
            "alertas":  bool(TABLE_ALERTAS),
        },
    }


@router.get("/crm/estudio")
def obtener_estudio():
    """Retorna info del estudio (asume 1 estudio por tenant para esta demo)."""
    data = _at_get(TABLE_ESTUDIOS, {"maxRecords": 1})
    records = data.get("records", [])
    if not records:
        return {"estudio": None}
    return {"estudio": _serialize_record(records[0])}


@router.get("/crm/abogados")
def listar_abogados(activo: Optional[bool] = None):
    params: dict = {"pageSize": 100, "sort[0][field]": "Nombre Completo"}
    if activo is not None:
        # Filtrar solo activos si se pide
        params["filterByFormula_extra"] = "{Activo}=TRUE()"  # placeholder, _at_get lo combina
        params["filterByFormula"] = "{Activo}=TRUE()" if activo else "NOT({Activo})"
    data = _at_get(TABLE_ABOGADOS, params)
    return {"abogados": [_serialize_record(r) for r in data.get("records", [])]}


@router.post("/crm/abogados")
def crear_abogado(payload: AbogadoCreate):
    fields = {
        "Nombre Completo": payload.nombre_completo,
        "Especialidad": payload.especialidad,
        "Teléfono WhatsApp": payload.telefono_whatsapp,
        "Email": payload.email,
        "Matrícula": payload.matricula,
        "Activo": payload.activo,
        "Recibe Alertas WhatsApp": payload.recibe_alertas_whatsapp,
        "Notas": payload.notas,
    }
    if payload.estudio_id:
        fields["Estudio"] = [payload.estudio_id]
    # limpiar Nones
    fields = {k: v for k, v in fields.items() if v is not None}
    rec = _at_post(TABLE_ABOGADOS, fields)
    return _serialize_record(rec)


@router.patch("/crm/abogados/{record_id}")
def actualizar_abogado(record_id: str, payload: dict):
    # payload viene como dict directo desde el front (campos con nombres Airtable)
    rec = _at_patch(TABLE_ABOGADOS, record_id, payload)
    return _serialize_record(rec)


@router.get("/crm/clientes")
def listar_clientes(estado: Optional[str] = None, abogado_id: Optional[str] = None):
    params: dict = {"pageSize": 100, "sort[0][field]": "Nombre Completo / Razón Social"}
    filters = []
    if estado:
        filters.append(f"{{Estado}}='{estado}'")
    if abogado_id:
        filters.append(f"FIND('{abogado_id}',ARRAYJOIN({{Abogado Asignado}}))")
    if filters:
        params["filterByFormula"] = "AND(" + ",".join(filters) + ")" if len(filters) > 1 else filters[0]
    data = _at_get(TABLE_CLIENTES, params)
    return {"clientes": [_serialize_record(r) for r in data.get("records", [])]}


@router.get("/crm/clientes/search")
def buscar_clientes(q: str = Query(..., min_length=2)):
    """Autocomplete por nombre o DNI/CUIT."""
    q_safe = q.replace("'", "")
    formula = (
        f"OR("
        f"FIND(LOWER('{q_safe}'),LOWER({{Nombre Completo / Razón Social}}))>0,"
        f"FIND('{q_safe}',{{DNI / CUIT}})>0"
        f")"
    )
    data = _at_get(TABLE_CLIENTES, {"filterByFormula": formula, "maxRecords": 10})
    return {"clientes": [_serialize_record(r) for r in data.get("records", [])]}


@router.post("/crm/clientes")
def crear_cliente(payload: ClienteCreate):
    fields = {
        "Tipo": payload.tipo,
        "Nombre Completo / Razón Social": payload.nombre_completo,
        "DNI / CUIT": payload.dni_cuit,
        "Teléfono WhatsApp": payload.telefono_whatsapp,
        "Email": payload.email,
        "Dirección": payload.direccion,
        "Notas Iniciales": payload.notas_iniciales,
        "Recibe Alertas WhatsApp": payload.recibe_alertas_whatsapp,
        "Estado": "Activo",
        "Fecha Alta": date.today().isoformat(),
    }
    if payload.estudio_id:
        fields["Estudio"] = [payload.estudio_id]
    if payload.abogado_asignado_id:
        fields["Abogado Asignado"] = [payload.abogado_asignado_id]
    fields = {k: v for k, v in fields.items() if v is not None}
    rec = _at_post(TABLE_CLIENTES, fields)
    return _serialize_record(rec)


@router.patch("/crm/clientes/{record_id}")
def actualizar_cliente(record_id: str, payload: dict):
    rec = _at_patch(TABLE_CLIENTES, record_id, payload)
    return _serialize_record(rec)


@router.delete("/crm/clientes/{record_id}")
def cerrar_cliente(record_id: str):
    """Soft delete — pasa Estado a 'Cerrado'."""
    rec = _at_patch(TABLE_CLIENTES, record_id, {"Estado": "Cerrado"})
    return {"ok": True, "id": rec["id"]}


@router.get("/crm/tramites")
def listar_tramites(
    estado: Optional[str] = None,
    cliente_id: Optional[str] = None,
    abogado_id: Optional[str] = None,
    categoria: Optional[str] = None,
):
    params: dict = {"pageSize": 200, "sort[0][field]": "Fecha Vencimiento"}
    filters = []
    if estado:
        filters.append(f"{{Estado}}='{estado}'")
    if categoria:
        filters.append(f"{{Categoría}}='{categoria}'")
    if cliente_id:
        filters.append(f"FIND('{cliente_id}',ARRAYJOIN({{Cliente}}))")
    if abogado_id:
        filters.append(f"FIND('{abogado_id}',ARRAYJOIN({{Abogado Responsable}}))")
    if filters:
        params["filterByFormula"] = "AND(" + ",".join(filters) + ")" if len(filters) > 1 else filters[0]
    data = _at_get(TABLE_TRAMITES, params)
    return {"tramites": [_serialize_record(r) for r in data.get("records", [])]}


@router.get("/crm/tramites/agenda")
def agenda_vencimientos(dias: int = Query(30, ge=1, le=365)):
    """Trámites activos con vencimiento en los próximos N días, ordenados por urgencia."""
    formula = f"AND({{Estado}}='Activo',{{Días Para Vencer}}<={dias})"
    data = _at_get(
        TABLE_TRAMITES,
        {
            "filterByFormula": formula,
            "sort[0][field]": "Fecha Vencimiento",
            "pageSize": 100,
        },
    )
    return {"agenda": [_serialize_record(r) for r in data.get("records", [])]}


@router.post("/crm/tramites")
def crear_tramite(payload: TramiteCreate):
    fields = {
        "Tipo Trámite": payload.tipo_tramite,
        "Categoría": payload.categoria,
        "Descripción": payload.descripcion,
        "Fecha Inicio": payload.fecha_inicio,
        "Fecha Vencimiento": payload.fecha_vencimiento,
        "Estado": payload.estado,
        "Fuero / Juzgado": payload.fuero_juzgado,
        "N° Expediente": payload.n_expediente,
        "Notas Internas": payload.notas_internas,
        "Notas Cliente": payload.notas_cliente,
        "Cliente": [payload.cliente_id],
        "Fecha Creación": date.today().isoformat(),
    }
    if payload.estudio_id:
        fields["Estudio"] = [payload.estudio_id]
    if payload.abogado_responsable_id:
        fields["Abogado Responsable"] = [payload.abogado_responsable_id]
    fields = {k: v for k, v in fields.items() if v is not None}
    rec = _at_post(TABLE_TRAMITES, fields)
    return _serialize_record(rec)


@router.patch("/crm/tramites/{record_id}")
def actualizar_tramite(record_id: str, payload: dict):
    rec = _at_patch(TABLE_TRAMITES, record_id, payload)
    return _serialize_record(rec)


@router.delete("/crm/tramites/{record_id}")
def cerrar_tramite(record_id: str):
    rec = _at_patch(TABLE_TRAMITES, record_id, {"Estado": "Cerrado"})
    return {"ok": True, "id": rec["id"]}


@router.get("/crm/alertas")
def listar_alertas(tramite_id: Optional[str] = None, limit: int = 50):
    params: dict = {"pageSize": min(limit, 100), "sort[0][field]": "Fecha Envío", "sort[0][direction]": "desc"}
    if tramite_id:
        params["filterByFormula"] = f"FIND('{tramite_id}',ARRAYJOIN({{Trámite}}))"
    data = _at_get(TABLE_ALERTAS, params)
    return {"alertas": [_serialize_record(r) for r in data.get("records", [])]}


@router.post("/crm/alertas")
def registrar_alerta(payload: AlertaCreate):
    """Registra una alerta enviada — lo dispara n8n / bot tras enviar el WhatsApp."""
    fields = {
        "Trámite": [payload.tramite_id],
        "Cliente Destinatario": [payload.cliente_destinatario_id],
        "Fecha Envío": payload.fecha_envio or datetime.now().isoformat(),
        "Días Anticipación": payload.dias_anticipacion,
        "Mensaje Enviado": payload.mensaje_enviado,
        "Canal": payload.canal,
        "Estado Envío": payload.estado_envio,
    }
    rec = _at_post(TABLE_ALERTAS, fields)
    # Tocar Fecha Última Alerta del trámite
    try:
        _at_patch(
            TABLE_TRAMITES,
            payload.tramite_id,
            {"Fecha Última Alerta": date.today().isoformat()},
        )
    except Exception as e:
        logger.warning("No pude actualizar Fecha Última Alerta del trámite: %s", e)
    return _serialize_record(rec)


@router.get("/crm/dashboard")
def dashboard():
    """Stats agregados para el panel principal del CRM."""
    out = {
        "tenant": TENANT_SLUG,
        "total_clientes_activos": 0,
        "total_tramites_activos": 0,
        "tramites_por_urgencia": {
            "vencidos": 0,
            "hoy_manana": 0,
            "esta_semana": 0,
            "este_mes": 0,
            "ok": 0,
        },
        "alertas_ultimos_7_dias": 0,
    }

    # Clientes activos
    try:
        d = _at_get(TABLE_CLIENTES, {"filterByFormula": "{Estado}='Activo'", "pageSize": 100})
        out["total_clientes_activos"] = len(d.get("records", []))
    except Exception:
        pass

    # Trámites activos + agrupar por urgencia
    try:
        d = _at_get(TABLE_TRAMITES, {"filterByFormula": "{Estado}='Activo'", "pageSize": 200})
        tramites = d.get("records", [])
        out["total_tramites_activos"] = len(tramites)
        for t in tramites:
            urgencia = t.get("fields", {}).get("Urgencia", "")
            if "VENCIDO" in urgencia:
                out["tramites_por_urgencia"]["vencidos"] += 1
            elif "HOY/MAÑANA" in urgencia:
                out["tramites_por_urgencia"]["hoy_manana"] += 1
            elif "ESTA SEMANA" in urgencia:
                out["tramites_por_urgencia"]["esta_semana"] += 1
            elif "ESTE MES" in urgencia:
                out["tramites_por_urgencia"]["este_mes"] += 1
            else:
                out["tramites_por_urgencia"]["ok"] += 1
    except Exception:
        pass

    # Alertas últimos 7 días
    try:
        d = _at_get(
            TABLE_ALERTAS,
            {"filterByFormula": "DATETIME_DIFF(NOW(),{Fecha Envío},'days')<=7", "pageSize": 100},
        )
        out["alertas_ultimos_7_dias"] = len(d.get("records", []))
    except Exception:
        pass

    return out
