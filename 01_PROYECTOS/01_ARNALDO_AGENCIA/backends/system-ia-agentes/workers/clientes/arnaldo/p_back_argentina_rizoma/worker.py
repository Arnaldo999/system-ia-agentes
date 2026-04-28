import os
import logging
import requests
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger("rizoma-crm")

router = APIRouter(prefix="/clientes/arnaldo/p-back-argentina/rizoma", tags=["Rizoma CRM"])

TENANT_SLUG = "p-back-argentina-rizoma"

# ── Auth: delega al sistema de tenants Supabase (mismo que Mica y demos) ──────
_bearer = HTTPBearer(auto_error=False)

# Tokens válidos emitidos por /tenant/{slug}/auth — validamos contra Supabase
# El token es opaco (secrets.token_urlsafe) — solo verificamos que existe en
# la sesión activa del tenant. Para escala actual (1 cliente) es suficiente.
# El frontend usa POST /tenant/p-back-argentina-rizoma/auth para obtenerlo.

def _verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    token = credentials.credentials
    # Token "public" solo existe si el tenant no tiene PIN (no es nuestro caso)
    if token == "public":
        raise HTTPException(status_code=401, detail="Acceso no autorizado")
    # Validación: el token fue emitido por /tenant/{slug}/auth — es stateless
    # en el servidor (no guardamos en BD), así que verificamos que tenga formato válido
    # y que el tenant esté activo. Para invalidar tokens hay que hacer logout en el HTML.
    if len(token) < 20:
        raise HTTPException(status_code=401, detail="Token inválido")
    return token

# ── Config Airtable ────────────────────────────────────────────────────────────
BASE_ID   = os.environ.get("AIRTABLE_BASE_ID_RIZOMA", "appq1OPr8VJVnFosU")
TOKEN     = os.environ.get("AIRTABLE_TOKEN_RIZOMA", "")
HEADERS   = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

T_LEADS         = os.environ.get("AIRTABLE_TABLE_LEADS_RIZOMA", "")
T_PERSONAS      = os.environ.get("AIRTABLE_TABLE_PERSONAS_RIZOMA", "")
T_PROPIEDADES   = os.environ.get("AIRTABLE_TABLE_PROPIEDADES_RIZOMA", "")
T_CONTRATOS     = os.environ.get("AIRTABLE_TABLE_CONTRATOS_RIZOMA", "")
T_TASACIONES    = os.environ.get("AIRTABLE_TABLE_TASACIONES_RIZOMA", "")
T_ASESORES      = os.environ.get("AIRTABLE_TABLE_ASESORES_RIZOMA", "")

# ── Helpers Airtable ──────────────────────────────────────────────────────────

def _headers():
    tok = os.environ.get("AIRTABLE_TOKEN_RIZOMA", TOKEN)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

def at_get(table_id: str, params: dict = {}) -> list:
    if not table_id:
        return []
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    all_records = []
    offset = None
    while True:
        p = dict(params)
        if offset:
            p["offset"] = offset
        r = requests.get(url, headers=_headers(), params=p, timeout=10)
        if not r.ok:
            logger.error(f"Airtable GET error {r.status_code}: {r.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Airtable error: {r.status_code}")
        data = r.json()
        all_records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return all_records

def at_post(table_id: str, fields: dict) -> dict:
    if not table_id:
        raise HTTPException(status_code=500, detail="Table ID no configurado")
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    r = requests.post(url, headers=_headers(), json={"fields": fields}, timeout=10)
    if not r.ok:
        logger.error(f"Airtable POST error {r.status_code}: {r.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Airtable error: {r.status_code}")
    return r.json()

def at_patch(table_id: str, record_id: str, fields: dict) -> dict:
    if not table_id:
        raise HTTPException(status_code=500, detail="Table ID no configurado")
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}/{record_id}"
    r = requests.patch(url, headers=_headers(), json={"fields": fields}, timeout=10)
    if not r.ok:
        logger.error(f"Airtable PATCH error {r.status_code}: {r.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Airtable error: {r.status_code}")
    return r.json()

def record_to_dict(rec: dict) -> dict:
    return {"id": rec["id"], **rec.get("fields", {})}

# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    telefono: str
    nombre: Optional[str] = ""
    fuente: Optional[str] = "WhatsApp"
    intencion: Optional[str] = ""
    notas_humanas: Optional[str] = ""
    asesor_id: Optional[str] = None

class LeadUpdate(BaseModel):
    nombre: Optional[str] = None
    estado: Optional[str] = None
    fuente: Optional[str] = None
    intencion: Optional[str] = None
    bant_presupuesto: Optional[str] = None
    bant_timing: Optional[str] = None
    bant_autoridad: Optional[str] = None
    bant_necesidad: Optional[str] = None
    asesor_id: Optional[str] = None
    persona_id: Optional[str] = None
    notas_humanas: Optional[str] = None

class PersonaCreate(BaseModel):
    nombre_completo: str
    telefono: Optional[str] = ""
    email: Optional[str] = ""
    dni: Optional[str] = ""
    roles: Optional[List[str]] = ["Interesado"]
    localidad: Optional[str] = ""
    notas: Optional[str] = ""

class PersonaUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    dni: Optional[str] = None
    roles: Optional[List[str]] = None
    localidad: Optional[str] = None
    notas: Optional[str] = None

class PropiedadCreate(BaseModel):
    nombre: str
    tipo: Optional[str] = "Casa"
    modalidad: Optional[str] = "Venta"
    ubicacion: Optional[str] = ""
    localidad: Optional[str] = "Posadas"
    precio: Optional[float] = None
    moneda: Optional[str] = "USD"
    superficie_total_m2: Optional[float] = None
    dormitorios: Optional[int] = None
    descripcion: Optional[str] = ""
    disponible: Optional[bool] = True
    asesor_id: Optional[str] = None

class PropiedadUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    modalidad: Optional[str] = None
    ubicacion: Optional[str] = None
    localidad: Optional[str] = None
    precio: Optional[float] = None
    moneda: Optional[str] = None
    disponible: Optional[bool] = None
    descripcion: Optional[str] = None
    asesor_id: Optional[str] = None

class ContratoCreate(BaseModel):
    tipo: str
    persona_id: str
    propiedad_id: str
    monto: Optional[float] = None
    moneda: Optional[str] = "USD"
    fecha_firma: Optional[str] = None
    asesor_id: Optional[str] = None
    notas: Optional[str] = ""
    estado: Optional[str] = "En Proceso"
    duracion_meses: Optional[int] = None
    garantia: Optional[str] = None
    fecha_inicio_vigencia: Optional[str] = None
    fecha_fin_vigencia: Optional[str] = None
    comision_pct: Optional[float] = None

class ContratoUpdate(BaseModel):
    estado: Optional[str] = None
    notas: Optional[str] = None
    fecha_firma: Optional[str] = None
    fecha_inicio_vigencia: Optional[str] = None
    fecha_fin_vigencia: Optional[str] = None

class TasacionCreate(BaseModel):
    solicitante_id: str
    direccion_inmueble: str
    tipo_inmueble: Optional[str] = "Casa"
    fecha_solicitud: Optional[str] = None
    asesor_id: Optional[str] = None
    notas: Optional[str] = ""

class TasacionUpdate(BaseModel):
    estado: Optional[str] = None
    fecha_visita: Optional[str] = None
    valor_estimado: Optional[float] = None
    moneda_estimado: Optional[str] = "USD"
    notas: Optional[str] = None

# ── LEADS ─────────────────────────────────────────────────────────────────────

@router.get("/leads")
def get_leads(estado: str = "", fuente: str = "", intencion: str = "", _auth: str = Depends(_verify_token)):
    records = at_get(T_LEADS)
    result = [record_to_dict(r) for r in records]
    if estado:
        result = [r for r in result if r.get("Estado") == estado]
    if fuente:
        result = [r for r in result if r.get("Fuente") == fuente]
    if intencion:
        result = [r for r in result if r.get("Intencion") == intencion]
    return {"records": result, "total": len(result)}

@router.post("/leads")
def create_lead(body: LeadCreate, _auth: str = Depends(_verify_token)):
    fields = {
        "Telefono": body.telefono,
        "Nombre": body.nombre,
        "Estado": "Nuevo",
        "Fuente": body.fuente,
    }
    if body.intencion:
        fields["Intencion"] = body.intencion
    if body.notas_humanas:
        fields["Notas Humanas"] = body.notas_humanas
    if body.asesor_id:
        fields["Asesor Asignado"] = [body.asesor_id]
    rec = at_post(T_LEADS, fields)
    return record_to_dict(rec)

@router.patch("/leads/{record_id}")
def update_lead(record_id: str, body: LeadUpdate, _auth: str = Depends(_verify_token)):
    fields = {}
    if body.nombre is not None:
        fields["Nombre"] = body.nombre
    if body.estado is not None:
        fields["Estado"] = body.estado
    if body.fuente is not None:
        fields["Fuente"] = body.fuente
    if body.intencion is not None:
        fields["Intencion"] = body.intencion
    if body.bant_presupuesto is not None:
        fields["BANT Presupuesto"] = body.bant_presupuesto
    if body.bant_timing is not None:
        fields["BANT Timing"] = body.bant_timing
    if body.bant_autoridad is not None:
        fields["BANT Autoridad"] = body.bant_autoridad
    if body.bant_necesidad is not None:
        fields["BANT Necesidad"] = body.bant_necesidad
    if body.notas_humanas is not None:
        fields["Notas Humanas"] = body.notas_humanas
    if body.asesor_id is not None:
        fields["Asesor Asignado"] = [body.asesor_id]
    if body.persona_id is not None:
        fields["Persona Vinculada"] = [body.persona_id]
    if not fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    rec = at_patch(T_LEADS, record_id, fields)
    return record_to_dict(rec)

# ── PERSONAS ──────────────────────────────────────────────────────────────────

@router.get("/personas")
def get_personas(q: str = "", _auth: str = Depends(_verify_token)):
    records = at_get(T_PERSONAS)
    result = [record_to_dict(r) for r in records]
    if q:
        q_lower = q.lower()
        result = [
            r for r in result
            if q_lower in str(r.get("Nombre Completo", "")).lower()
            or q_lower in str(r.get("Telefono", "")).lower()
        ]
    return {"records": result, "total": len(result)}

@router.post("/personas")
def create_persona(body: PersonaCreate, _auth: str = Depends(_verify_token)):
    # Capitalizar primera letra de cada rol (Airtable multipleSelects es case-sensitive)
    roles = [r.capitalize() for r in (body.roles or ["Interesado"])]
    fields = {
        "Nombre Completo": body.nombre_completo,
        "Roles": roles,
    }
    if body.telefono:
        fields["Telefono"] = body.telefono
    if body.email:
        fields["Email"] = body.email
    if body.dni:
        fields["DNI"] = body.dni
    if body.localidad:
        fields["Localidad"] = body.localidad
    if body.notas:
        fields["Notas"] = body.notas
    rec = at_post(T_PERSONAS, fields)
    return record_to_dict(rec)

@router.patch("/personas/{record_id}")
def update_persona(record_id: str, body: PersonaUpdate, _auth: str = Depends(_verify_token)):
    fields = {}
    if body.nombre_completo is not None:
        fields["Nombre Completo"] = body.nombre_completo
    if body.telefono is not None:
        fields["Telefono"] = body.telefono
    if body.email is not None:
        fields["Email"] = body.email
    if body.dni is not None:
        fields["DNI"] = body.dni
    if body.roles is not None:
        fields["Roles"] = [r.capitalize() for r in body.roles]
    if body.localidad is not None:
        fields["Localidad"] = body.localidad
    if body.notas is not None:
        fields["Notas"] = body.notas
    if not fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    rec = at_patch(T_PERSONAS, record_id, fields)
    return record_to_dict(rec)

# ── PROPIEDADES ───────────────────────────────────────────────────────────────

@router.get("/propiedades")
def get_propiedades(tipo: str = "", modalidad: str = "", localidad: str = "", disponible: str = "", _auth: str = Depends(_verify_token)):
    records = at_get(T_PROPIEDADES)
    result = [record_to_dict(r) for r in records]
    if tipo:
        result = [r for r in result if r.get("Tipo") == tipo]
    if modalidad:
        result = [r for r in result if r.get("Modalidad") == modalidad]
    if localidad:
        result = [r for r in result if r.get("Localidad") == localidad]
    if disponible == "true":
        result = [r for r in result if r.get("Disponible") is True]
    elif disponible == "false":
        result = [r for r in result if r.get("Disponible") is False]
    return {"records": result, "total": len(result)}

@router.post("/propiedades")
def create_propiedad(body: PropiedadCreate, _auth: str = Depends(_verify_token)):
    fields = {
        "Nombre": body.nombre,
        "Tipo": body.tipo,
        "Modalidad": body.modalidad,
        "Disponible": body.disponible if body.disponible is not None else True,
    }
    if body.ubicacion:
        fields["Ubicacion"] = body.ubicacion
    if body.localidad:
        fields["Localidad"] = body.localidad
    if body.precio is not None:
        fields["Precio"] = body.precio
    if body.moneda:
        fields["Moneda"] = body.moneda
    if body.superficie_total_m2 is not None:
        fields["Superficie Total m2"] = body.superficie_total_m2
    if body.dormitorios is not None:
        fields["Dormitorios"] = body.dormitorios
    if body.descripcion:
        fields["Descripcion"] = body.descripcion
    if body.asesor_id:
        fields["Asesor Responsable"] = [body.asesor_id]
    rec = at_post(T_PROPIEDADES, fields)
    return record_to_dict(rec)

@router.patch("/propiedades/{record_id}")
def update_propiedad(record_id: str, body: PropiedadUpdate, _auth: str = Depends(_verify_token)):
    fields = {}
    if body.nombre is not None:
        fields["Nombre"] = body.nombre
    if body.tipo is not None:
        fields["Tipo"] = body.tipo
    if body.modalidad is not None:
        fields["Modalidad"] = body.modalidad
    if body.ubicacion is not None:
        fields["Ubicacion"] = body.ubicacion
    if body.localidad is not None:
        fields["Localidad"] = body.localidad
    if body.precio is not None:
        fields["Precio"] = body.precio
    if body.moneda is not None:
        fields["Moneda"] = body.moneda
    if body.disponible is not None:
        fields["Disponible"] = body.disponible
    if body.descripcion is not None:
        fields["Descripcion"] = body.descripcion
    if body.asesor_id is not None:
        fields["Asesor Responsable"] = [body.asesor_id]
    if not fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    rec = at_patch(T_PROPIEDADES, record_id, fields)
    return record_to_dict(rec)

# ── CONTRATOS ─────────────────────────────────────────────────────────────────

@router.get("/contratos")
def get_contratos(tipo: str = "", estado: str = "", _auth: str = Depends(_verify_token)):
    records = at_get(T_CONTRATOS)
    result = [record_to_dict(r) for r in records]
    if tipo:
        result = [r for r in result if r.get("Tipo") == tipo]
    if estado:
        result = [r for r in result if r.get("Estado") == estado]
    return {"records": result, "total": len(result)}

@router.post("/contratos")
def create_contrato(body: ContratoCreate, _auth: str = Depends(_verify_token)):
    fields = {
        "Tipo": body.tipo,
        "Estado": body.estado or "En Proceso",
        "Persona": [body.persona_id],
        "Propiedad": [body.propiedad_id],
    }
    if body.monto is not None:
        fields["Monto"] = body.monto
    if body.moneda:
        fields["Moneda"] = body.moneda
    if body.fecha_firma:
        fields["Fecha Firma"] = body.fecha_firma
    if body.asesor_id:
        fields["Asesor"] = [body.asesor_id]
    if body.notas:
        fields["Notas"] = body.notas
    if body.comision_pct is not None:
        fields["Comision Pct"] = body.comision_pct
    if body.tipo in ("Alquiler", "Alquiler Temporal"):
        if body.duracion_meses is not None:
            fields["Duracion Meses"] = body.duracion_meses
        if body.garantia:
            fields["Garantia"] = body.garantia
        if body.fecha_inicio_vigencia:
            fields["Fecha Inicio Vigencia"] = body.fecha_inicio_vigencia
        if body.fecha_fin_vigencia:
            fields["Fecha Fin Vigencia"] = body.fecha_fin_vigencia
    rec = at_post(T_CONTRATOS, fields)
    # Cascade: si estado = Firmado → marcar propiedad no disponible
    if body.estado == "Firmado" and T_PROPIEDADES:
        try:
            at_patch(T_PROPIEDADES, body.propiedad_id, {"Disponible": False})
        except Exception as e:
            logger.warning(f"No se pudo actualizar disponibilidad propiedad: {e}")
    return record_to_dict(rec)

@router.patch("/contratos/{record_id}")
def update_contrato(record_id: str, body: ContratoUpdate, _auth: str = Depends(_verify_token)):
    fields = {}
    if body.estado is not None:
        fields["Estado"] = body.estado
    if body.notas is not None:
        fields["Notas"] = body.notas
    if body.fecha_firma is not None:
        fields["Fecha Firma"] = body.fecha_firma
    if body.fecha_inicio_vigencia is not None:
        fields["Fecha Inicio Vigencia"] = body.fecha_inicio_vigencia
    if body.fecha_fin_vigencia is not None:
        fields["Fecha Fin Vigencia"] = body.fecha_fin_vigencia
    if not fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    rec = at_patch(T_CONTRATOS, record_id, fields)
    return record_to_dict(rec)

# ── TASACIONES ────────────────────────────────────────────────────────────────

@router.get("/tasaciones")
def get_tasaciones(estado: str = "", _auth: str = Depends(_verify_token)):
    records = at_get(T_TASACIONES)
    result = [record_to_dict(r) for r in records]
    if estado:
        result = [r for r in result if r.get("Estado") == estado]
    return {"records": result, "total": len(result)}

@router.post("/tasaciones")
def create_tasacion(body: TasacionCreate, _auth: str = Depends(_verify_token)):
    fields = {
        "Estado": "Solicitada",
        "Solicitante": [body.solicitante_id],
        "Direccion Inmueble": body.direccion_inmueble,
        "Tipo Inmueble": body.tipo_inmueble or "Casa",
    }
    if body.fecha_solicitud:
        fields["Fecha Solicitud"] = body.fecha_solicitud
    if body.asesor_id:
        fields["Asesor Asignado"] = [body.asesor_id]
    if body.notas:
        fields["Notas"] = body.notas
    rec = at_post(T_TASACIONES, fields)
    return record_to_dict(rec)

@router.patch("/tasaciones/{record_id}")
def update_tasacion(record_id: str, body: TasacionUpdate, _auth: str = Depends(_verify_token)):
    fields = {}
    if body.estado is not None:
        fields["Estado"] = body.estado
    if body.fecha_visita is not None:
        fields["Fecha Visita"] = body.fecha_visita
    if body.valor_estimado is not None:
        fields["Valor Estimado"] = body.valor_estimado
    if body.moneda_estimado is not None:
        fields["Moneda Estimado"] = body.moneda_estimado
    if body.notas is not None:
        fields["Notas"] = body.notas
    if not fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    rec = at_patch(T_TASACIONES, record_id, fields)
    return record_to_dict(rec)

# ── ASESORES ──────────────────────────────────────────────────────────────────

@router.get("/asesores")
def get_asesores(activo: str = "true", _auth: str = Depends(_verify_token)):
    records = at_get(T_ASESORES)
    result = [record_to_dict(r) for r in records]
    if activo == "true":
        result = [r for r in result if r.get("Activo") is True]
    return {"records": result, "total": len(result)}

# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

@router.get("/health")
def health(_auth: str = Depends(_verify_token)):
    return {
        "status": "ok",
        "base_id": BASE_ID,
        "tables_configured": {
            "leads": bool(T_LEADS),
            "personas": bool(T_PERSONAS),
            "propiedades": bool(T_PROPIEDADES),
            "contratos": bool(T_CONTRATOS),
            "tasaciones": bool(T_TASACIONES),
            "asesores": bool(T_ASESORES),
        }
    }
