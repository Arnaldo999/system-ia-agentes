"""
Router FastAPI — CRM Agencia Lovbot
=====================================
Panel de agencia de Robert (admin.lovbot.ai/agencia).
Gestiona el funnel de prospectos y clientes que contratan el producto Lovbot.

BD: lovbot_agencia (PostgreSQL Hetzner)
    SEPARADA de lovbot_crm_modelo (demo inmobiliaria) y robert_crm (bot prod).
    Env var de BD: LOVBOT_AGENCIA_PG_DB=lovbot_agencia

Auth: Bearer token via header Authorization o query param ?token=
      Token: lovbot-admin-2026  (mismo que admin panel)

Prefijo: /agencia
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Config de BD ─────────────────────────────────────────────────────────────
PG_HOST = os.environ.get("LOVBOT_PG_HOST", "localhost")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_DB   = os.environ.get("LOVBOT_AGENCIA_PG_DB", "lovbot_agencia")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")

# Token admin — mismo que usa el panel admin
ADMIN_TOKEN = os.environ.get("LOVBOT_ADMIN_TOKEN", "lovbot-admin-2026")


# ── Conexion ──────────────────────────────────────────────────────────────────
def _conn():
    """Abre conexion a lovbot_agencia en Hetzner."""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        connect_timeout=8,
    )


# ── Auth ──────────────────────────────────────────────────────────────────────
def _verificar_token(request: Request) -> None:
    """
    Verifica token Bearer en header Authorization o query param ?token=
    Lanza 401 si falta o no coincide con LOVBOT_ADMIN_TOKEN.
    """
    auth_header = request.headers.get("Authorization", "")
    token_query = request.query_params.get("token", "")

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif token_query:
        token = token_query.strip()

    if not token or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalido o ausente")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class LeadIn(BaseModel):
    nombre_contacto: str
    apellido_contacto: Optional[str] = None
    nombre_empresa: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    ciudad: Optional[str] = None
    pais: Optional[str] = "Mexico"
    fuente_id: Optional[int] = None
    canal_raw: Optional[str] = None
    tipo_cliente: Optional[str] = "inmobiliaria"
    estado: Optional[str] = "lead"
    presupuesto_aprox: Optional[str] = None
    decision_estimada: Optional[date] = None
    proximo_contacto: Optional[date] = None
    responsable: Optional[str] = "Robert"
    notas: Optional[str] = None
    fb_lead_id: Optional[str] = None
    lead_center_id: Optional[str] = None


class LeadPatch(BaseModel):
    nombre_contacto: Optional[str] = None
    apellido_contacto: Optional[str] = None
    nombre_empresa: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    ciudad: Optional[str] = None
    pais: Optional[str] = None
    fuente_id: Optional[int] = None
    canal_raw: Optional[str] = None
    tipo_cliente: Optional[str] = None
    estado: Optional[str] = None
    motivo_perdida: Optional[str] = None
    presupuesto_aprox: Optional[str] = None
    decision_estimada: Optional[date] = None
    proximo_contacto: Optional[date] = None
    responsable: Optional[str] = None
    notas: Optional[str] = None


class LeadDeleteBody(BaseModel):
    motivo_perdida: Optional[str] = None


class ConvertirClienteIn(BaseModel):
    plan: Optional[str] = "crm_basico"
    monto_implementacion: Optional[float] = None
    monto_mensual: Optional[float] = None
    moneda: Optional[str] = "USD"
    fecha_inicio_contrato: Optional[date] = None
    tenant_slug: Optional[str] = None
    db_nombre: Optional[str] = None
    notas: Optional[str] = None


class ContactoLogIn(BaseModel):
    tipo_contacto: str
    resumen: Optional[str] = None
    resultado: Optional[str] = None
    duracion_min: Optional[int] = None
    proximo_contacto: Optional[date] = None
    proximo_accion: Optional[str] = None
    responsable: Optional[str] = "Robert"
    fecha_contacto: Optional[str] = None  # ISO string; si None usa NOW()


class PropuestaIn(BaseModel):
    lead_id: int
    titulo: Optional[str] = None
    version: Optional[int] = 1
    monto_implementacion: Optional[float] = None
    monto_mensual: Optional[float] = None
    moneda: Optional[str] = "USD"
    incluye_bot: Optional[bool] = True
    incluye_crm: Optional[bool] = True
    descripcion_alcance: Optional[str] = None
    estado: Optional[str] = "borrador"
    fecha_envio: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    pdf_url: Optional[str] = None
    notas: Optional[str] = None
    responsable: Optional[str] = "Robert"


class PropuestaPatch(BaseModel):
    titulo: Optional[str] = None
    estado: Optional[str] = None
    fecha_envio: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    fecha_respuesta: Optional[date] = None
    monto_implementacion: Optional[float] = None
    monto_mensual: Optional[float] = None
    pdf_url: Optional[str] = None
    notas: Optional[str] = None


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(
    prefix="/agencia",
    tags=["Agencia CRM"],
)


# ────────────────────────────────────────────────────────────────────────────
# 1. GET /agencia/funnel-resumen
# ────────────────────────────────────────────────────────────────────────────
@router.get("/funnel-resumen")
def get_funnel_resumen(request: Request):
    """
    Retorna los conteos por etapa del funnel.
    Consulta la vista agencia_funnel_resumen.
    Alimenta las 6 cards de conteo del frontend.
    """
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT estado, total, con_followup_vencido FROM agencia_funnel_resumen")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Estructurar como dict para acceso rapido desde el frontend
        result = {row["estado"]: {"total": row["total"], "followup_vencido": row["con_followup_vencido"]} for row in rows}
        return {"ok": True, "funnel": result, "rows": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 2. GET /agencia/leads
# ────────────────────────────────────────────────────────────────────────────
@router.get("/leads")
def get_leads(
    request: Request,
    estado: Optional[str] = Query(None),
    canal: Optional[str] = Query(None),
    responsable: Optional[str] = Query(None),
    buscar: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Lista leads paginada.
    Filtros opcionales: estado, canal (fuente), responsable, buscar (texto libre en nombre/empresa/whatsapp).
    """
    _verificar_token(request)
    conditions = []
    params = []

    if estado:
        conditions.append("l.estado = %s")
        params.append(estado)
    if responsable:
        conditions.append("l.responsable = %s")
        params.append(responsable)
    if canal:
        conditions.append("(f.slug = %s OR l.canal_raw = %s)")
        params.extend([canal, canal])
    if buscar:
        conditions.append(
            "(l.nombre_contacto ILIKE %s OR l.apellido_contacto ILIKE %s "
            "OR l.nombre_empresa ILIKE %s OR l.whatsapp ILIKE %s)"
        )
        like = "%" + buscar + "%"
        params.extend([like, like, like, like])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT
            l.*,
            f.slug  AS fuente_slug,
            f.nombre AS fuente_nombre
        FROM agencia_leads l
        LEFT JOIN agencia_fuentes f ON f.id = l.fuente_id
        {where}
        ORDER BY l.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Conteo total para paginacion
        count_sql = f"SELECT COUNT(*) FROM agencia_leads l LEFT JOIN agencia_fuentes f ON f.id = l.fuente_id {where}"
        cur.execute(count_sql, params[:-2])  # sin limit/offset
        total = cur.fetchone()["count"]
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "total": total, "limit": limit, "offset": offset, "leads": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 3. POST /agencia/leads
# ────────────────────────────────────────────────────────────────────────────
@router.post("/leads", status_code=201)
def crear_lead(request: Request, body: LeadIn):
    """Crea un nuevo lead en el funnel de la agencia."""
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO agencia_leads (
                nombre_contacto, apellido_contacto, nombre_empresa,
                whatsapp, email, ciudad, pais,
                fuente_id, canal_raw, tipo_cliente, estado,
                presupuesto_aprox, decision_estimada, proximo_contacto,
                responsable, notas, fb_lead_id, lead_center_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING *
            """,
            (
                body.nombre_contacto, body.apellido_contacto, body.nombre_empresa,
                body.whatsapp, body.email, body.ciudad, body.pais,
                body.fuente_id, body.canal_raw, body.tipo_cliente, body.estado,
                body.presupuesto_aprox, body.decision_estimada, body.proximo_contacto,
                body.responsable, body.notas, body.fb_lead_id, body.lead_center_id,
            ),
        )
        nuevo = dict(cur.fetchone())
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "lead": nuevo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 4. PATCH /agencia/leads/{id}
# ────────────────────────────────────────────────────────────────────────────
@router.patch("/leads/{lead_id}")
def actualizar_lead(request: Request, lead_id: int, body: LeadPatch):
    """Actualiza campos de un lead (estado, notas, proximo_contacto, etc.)."""
    _verificar_token(request)
    campos = body.model_dump(exclude_none=True)
    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    set_clause = ", ".join(f"{k} = %s" for k in campos)
    values = list(campos.values()) + [lead_id]

    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"UPDATE agencia_leads SET {set_clause} WHERE id = %s RETURNING *",
            values,
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} no encontrado")
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "lead": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 5. DELETE /agencia/leads/{id}
# Soft delete: cambia estado a 'perdido' con motivo opcional.
# ────────────────────────────────────────────────────────────────────────────
@router.delete("/leads/{lead_id}")
def eliminar_lead(request: Request, lead_id: int, body: Optional[LeadDeleteBody] = None):
    """
    Soft delete: marca el lead como 'perdido' con motivo opcional.
    No elimina el registro fisicamente para mantener trazabilidad.
    """
    _verificar_token(request)
    motivo = (body.motivo_perdida if body else None) or "Eliminado manualmente"
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "UPDATE agencia_leads SET estado = 'perdido', motivo_perdida = %s WHERE id = %s RETURNING id, estado, motivo_perdida",
            (motivo, lead_id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} no encontrado")
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "lead_id": lead_id, "estado": "perdido", "motivo": motivo}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 6. GET /agencia/leads/{id}/contactos
# ────────────────────────────────────────────────────────────────────────────
@router.get("/leads/{lead_id}/contactos")
def get_contactos_lead(request: Request, lead_id: int):
    """Log cronologico de interacciones sobre un lead."""
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT * FROM agencia_contactos_log
            WHERE entidad_tipo = 'lead' AND entidad_id = %s
            ORDER BY fecha_contacto DESC
            """,
            (lead_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "lead_id": lead_id, "total": len(rows), "contactos": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 7. POST /agencia/leads/{id}/contactos
# ────────────────────────────────────────────────────────────────────────────
@router.post("/leads/{lead_id}/contactos", status_code=201)
def registrar_contacto_lead(request: Request, lead_id: int, body: ContactoLogIn):
    """Registra una nueva interaccion sobre un lead."""
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        fecha_sql = body.fecha_contacto if body.fecha_contacto else None
        if fecha_sql:
            cur.execute(
                """
                INSERT INTO agencia_contactos_log
                    (entidad_tipo, entidad_id, tipo_contacto, resumen, resultado,
                     duracion_min, proximo_contacto, proximo_accion, responsable, fecha_contacto)
                VALUES ('lead', %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamp)
                RETURNING *
                """,
                (lead_id, body.tipo_contacto, body.resumen, body.resultado,
                 body.duracion_min, body.proximo_contacto, body.proximo_accion,
                 body.responsable, fecha_sql),
            )
        else:
            cur.execute(
                """
                INSERT INTO agencia_contactos_log
                    (entidad_tipo, entidad_id, tipo_contacto, resumen, resultado,
                     duracion_min, proximo_contacto, proximo_accion, responsable)
                VALUES ('lead', %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (lead_id, body.tipo_contacto, body.resumen, body.resultado,
                 body.duracion_min, body.proximo_contacto, body.proximo_accion,
                 body.responsable),
            )

        nuevo = dict(cur.fetchone())

        # Si el contacto tiene proximo_contacto, actualizar el campo en el lead
        if body.proximo_contacto:
            cur.execute(
                "UPDATE agencia_leads SET proximo_contacto = %s WHERE id = %s",
                (body.proximo_contacto, lead_id),
            )

        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "contacto": nuevo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 8. POST /agencia/leads/{id}/convertir-cliente
# ────────────────────────────────────────────────────────────────────────────
@router.post("/leads/{lead_id}/convertir-cliente", status_code=201)
def convertir_lead_a_cliente(request: Request, lead_id: int, body: ConvertirClienteIn):
    """
    Convierte un lead en cliente:
    1. Verifica que el lead exista y no este ya convertido.
    2. Crea fila en agencia_clientes con datos del lead + datos del contrato.
    3. Actualiza agencia_leads: estado='cliente', cliente_id=nuevo_cliente.id
    """
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Verificar lead
        cur.execute("SELECT * FROM agencia_leads WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} no encontrado")
        if lead["estado"] == "cliente" and lead["cliente_id"]:
            raise HTTPException(
                status_code=409,
                detail=f"Lead {lead_id} ya fue convertido al cliente {lead['cliente_id']}"
            )

        # Crear cliente
        cur.execute(
            """
            INSERT INTO agencia_clientes (
                nombre_empresa, nombre_contacto, apellido_contacto,
                whatsapp, email, ciudad, pais,
                lead_origen_id, fuente_id,
                plan, monto_implementacion, monto_mensual, moneda,
                fecha_inicio_contrato, tenant_slug, db_nombre,
                estado, responsable, notas
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                'activo', %s, %s
            )
            RETURNING *
            """,
            (
                lead["nombre_empresa"], lead["nombre_contacto"], lead["apellido_contacto"],
                lead["whatsapp"], lead["email"], lead["ciudad"], lead["pais"],
                lead_id, lead["fuente_id"],
                body.plan, body.monto_implementacion, body.monto_mensual, body.moneda,
                body.fecha_inicio_contrato, body.tenant_slug, body.db_nombre,
                lead["responsable"], body.notas,
            ),
        )
        nuevo_cliente = dict(cur.fetchone())
        cliente_id = nuevo_cliente["id"]

        # Actualizar lead
        cur.execute(
            "UPDATE agencia_leads SET estado = 'cliente', cliente_id = %s WHERE id = %s",
            (cliente_id, lead_id),
        )

        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "cliente": nuevo_cliente, "lead_id": lead_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 9. GET /agencia/clientes
# ────────────────────────────────────────────────────────────────────────────
@router.get("/clientes")
def get_clientes(
    request: Request,
    estado: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Lista clientes activos (o filtrados por estado/plan). Ordenados por fecha de inicio desc."""
    _verificar_token(request)
    conditions = []
    params = []

    if estado:
        conditions.append("estado = %s")
        params.append(estado)
    if plan:
        conditions.append("plan = %s")
        params.append(plan)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params_count = params.copy()
    params.extend([limit, offset])

    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT COUNT(*) FROM agencia_clientes {where}", params_count)
        total = cur.fetchone()["count"]
        cur.execute(
            f"SELECT * FROM agencia_clientes {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "total": total, "limit": limit, "offset": offset, "clientes": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 10. GET /agencia/clientes/{id}
# ────────────────────────────────────────────────────────────────────────────
@router.get("/clientes/{cliente_id}")
def get_cliente_detalle(request: Request, cliente_id: int):
    """
    Detalle de un cliente: datos basicos + propuestas asociadas + pagos recientes.
    """
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM agencia_clientes WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
        if not cliente:
            raise HTTPException(status_code=404, detail=f"Cliente {cliente_id} no encontrado")

        # Propuestas del lead de origen
        propuestas = []
        if cliente["lead_origen_id"]:
            cur.execute(
                "SELECT * FROM agencia_propuestas WHERE lead_id = %s ORDER BY version DESC",
                (cliente["lead_origen_id"],),
            )
            propuestas = [dict(r) for r in cur.fetchall()]

        # Pagos
        cur.execute(
            "SELECT * FROM agencia_pagos WHERE cliente_id = %s ORDER BY periodo_anio DESC, periodo_mes DESC LIMIT 24",
            (cliente_id,),
        )
        pagos = [dict(r) for r in cur.fetchall()]

        # Log de contactos (post-cierre)
        cur.execute(
            "SELECT * FROM agencia_contactos_log WHERE entidad_tipo='cliente' AND entidad_id=%s ORDER BY fecha_contacto DESC LIMIT 20",
            (cliente_id,),
        )
        contactos = [dict(r) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return {
            "ok": True,
            "cliente": dict(cliente),
            "propuestas": propuestas,
            "pagos": pagos,
            "contactos_recientes": contactos,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 11. GET /agencia/fuentes
# ────────────────────────────────────────────────────────────────────────────
@router.get("/fuentes")
def get_fuentes(request: Request, solo_activas: bool = Query(True)):
    """Catalogo de canales/fuentes. Usado para poblar selects en el frontend."""
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if solo_activas:
            cur.execute("SELECT * FROM agencia_fuentes WHERE activo = TRUE ORDER BY nombre")
        else:
            cur.execute("SELECT * FROM agencia_fuentes ORDER BY nombre")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "fuentes": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 12. POST /agencia/propuestas
# ────────────────────────────────────────────────────────────────────────────
@router.post("/propuestas", status_code=201)
def crear_propuesta(request: Request, body: PropuestaIn):
    """Crea una propuesta formal para un lead (puede haber varias versiones)."""
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO agencia_propuestas (
                lead_id, version, titulo,
                monto_implementacion, monto_mensual, moneda,
                incluye_bot, incluye_crm, descripcion_alcance,
                estado, fecha_envio, fecha_vencimiento, pdf_url,
                notas, responsable
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
            RETURNING *
            """,
            (
                body.lead_id, body.version, body.titulo,
                body.monto_implementacion, body.monto_mensual, body.moneda,
                body.incluye_bot, body.incluye_crm, body.descripcion_alcance,
                body.estado, body.fecha_envio, body.fecha_vencimiento, body.pdf_url,
                body.notas, body.responsable,
            ),
        )
        nueva = dict(cur.fetchone())
        # Si se crea como 'enviada', actualizar estado del lead a 'propuesta'
        if body.estado == "enviada":
            cur.execute(
                "UPDATE agencia_leads SET estado = 'propuesta' WHERE id = %s AND estado NOT IN ('cliente','perdido')",
                (body.lead_id,),
            )
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "propuesta": nueva}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 13. GET /agencia/propuestas/{id}
# ────────────────────────────────────────────────────────────────────────────
@router.get("/propuestas/{propuesta_id}")
def get_propuesta(request: Request, propuesta_id: int):
    """Detalle de una propuesta."""
    _verificar_token(request)
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT p.*, l.nombre_contacto, l.nombre_empresa
            FROM agencia_propuestas p
            LEFT JOIN agencia_leads l ON l.id = p.lead_id
            WHERE p.id = %s
            """,
            (propuesta_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"Propuesta {propuesta_id} no encontrada")
        return {"ok": True, "propuesta": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 14. PATCH /agencia/propuestas/{id}
# ────────────────────────────────────────────────────────────────────────────
@router.patch("/propuestas/{propuesta_id}")
def actualizar_propuesta(request: Request, propuesta_id: int, body: PropuestaPatch):
    """Actualiza estado u otros campos de una propuesta (enviada/aceptada/rechazada/etc.)."""
    _verificar_token(request)
    campos = body.model_dump(exclude_none=True)
    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    set_clause = ", ".join(f"{k} = %s" for k in campos)
    values = list(campos.values()) + [propuesta_id]

    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"UPDATE agencia_propuestas SET {set_clause} WHERE id = %s RETURNING *",
            values,
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail=f"Propuesta {propuesta_id} no encontrada")

        # Si se acepta la propuesta, avanzar el lead a 'negociacion'
        if campos.get("estado") == "aceptada":
            cur.execute(
                "UPDATE agencia_leads SET estado = 'negociacion' WHERE id = %s AND estado NOT IN ('cliente','perdido')",
                (row["lead_id"],),
            )

        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "propuesta": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────────────────────
# 15. GET /agencia/pagos
# ────────────────────────────────────────────────────────────────────────────
@router.get("/pagos")
def get_pagos(
    request: Request,
    cliente_id: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Historial de cobros.
    Filtros: cliente_id (requerido para ver un cliente especifico), estado.
    """
    _verificar_token(request)
    conditions = []
    params = []

    if cliente_id:
        conditions.append("p.cliente_id = %s")
        params.append(cliente_id)
    if estado:
        conditions.append("p.estado = %s")
        params.append(estado)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params_count = params.copy()
    params.extend([limit, offset])

    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT COUNT(*) FROM agencia_pagos p {where}",
            params_count,
        )
        total = cur.fetchone()["count"]
        cur.execute(
            f"""
            SELECT p.*, c.nombre_empresa, c.nombre_contacto
            FROM agencia_pagos p
            LEFT JOIN agencia_clientes c ON c.id = p.cliente_id
            {where}
            ORDER BY p.periodo_anio DESC, p.periodo_mes DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "total": total, "pagos": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
