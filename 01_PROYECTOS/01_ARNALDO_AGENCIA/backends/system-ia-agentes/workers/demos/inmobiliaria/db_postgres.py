"""
DB PostgreSQL — Lovbot Inmobiliaria
====================================
Reemplaza las funciones de Airtable del worker con PostgreSQL.
Misma interfaz, diferente backend.

Conexión: via env vars LOVBOT_PG_HOST/PORT/DB/USER/PASS
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime, timedelta

# ── Config ───────────────────────────────────────────────────────────────────
PG_HOST = os.environ.get("LOVBOT_PG_HOST", "localhost")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_DB   = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")

TENANT = os.environ.get("LOVBOT_TENANT_SLUG", "demo")


def _conn():
    """Crea conexión a PostgreSQL."""
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
        connect_timeout=8,
    )


def _available() -> bool:
    """Verifica si PostgreSQL está configurado."""
    return bool(PG_HOST and PG_PASS)


# ── LEADS (equivalente a _at_registrar_lead) ─────────────────────────────────

def registrar_lead(telefono: str, nombre: str, score: str = "",
                   tipo: str = "", zona: str = "", notas: str = "",
                   presupuesto: str = "", operacion: str = "",
                   ciudad: str = "", subniche: str = "",
                   fuente_detalle: str = "") -> None:
    """Registra o actualiza un lead en PostgreSQL."""
    if not _available():
        print("[DB] PostgreSQL no configurado — skip")
        return

    # Mapear score a estado
    estado_map = {"caliente": "calificado", "tibio": "contactado"}
    estado = estado_map.get(score, "no_contactado")

    # Parsear nombre/apellido
    partes = nombre.strip().split(" ", 1) if nombre else [""]
    nombre_p = partes[0]
    apellido_p = partes[1] if len(partes) > 1 else ""

    # Fuente
    if fuente_detalle and fuente_detalle.startswith("ad:"):
        fuente = "meta_ads"
    elif fuente_detalle and fuente_detalle.startswith("canal:voz"):
        fuente = "voz"
    else:
        fuente = "whatsapp_directo"

    try:
        conn = _conn()
        cur = conn.cursor()

        # Buscar si existe
        cur.execute("SELECT id FROM leads WHERE tenant_slug=%s AND telefono=%s", (TENANT, telefono))
        existing = cur.fetchone()

        if existing:
            # UPDATE
            cur.execute("""
                UPDATE leads SET
                    nombre=COALESCE(NULLIF(%s,''), nombre),
                    apellido=COALESCE(NULLIF(%s,''), apellido),
                    score=COALESCE(NULLIF(%s,''), score),
                    estado=COALESCE(NULLIF(%s,''), estado),
                    tipo_propiedad=COALESCE(NULLIF(%s,''), tipo_propiedad),
                    zona=COALESCE(NULLIF(%s,''), zona),
                    operacion=COALESCE(NULLIF(%s,''), operacion),
                    ciudad=COALESCE(NULLIF(%s,''), ciudad),
                    presupuesto=COALESCE(NULLIF(%s,''), presupuesto),
                    sub_nicho=COALESCE(NULLIF(%s,''), sub_nicho),
                    notas_bot=COALESCE(NULLIF(%s,''), notas_bot),
                    fuente_detalle=COALESCE(NULLIF(%s,''), fuente_detalle),
                    fuente=COALESCE(NULLIF(%s,''), fuente),
                    fecha_ultimo_contacto=NOW()
                WHERE tenant_slug=%s AND telefono=%s
            """, (nombre_p, apellido_p, score, estado,
                  tipo, zona, operacion, ciudad, presupuesto,
                  subniche, notas, fuente_detalle, fuente,
                  TENANT, telefono))
            print(f"[DB] UPDATE lead tel={telefono}")
        else:
            # INSERT
            cur.execute("""
                INSERT INTO leads (
                    tenant_slug, telefono, nombre, apellido, score, estado,
                    tipo_propiedad, zona, operacion, ciudad, presupuesto,
                    sub_nicho, notas_bot, fuente, fuente_detalle,
                    fecha_whatsapp, llego_whatsapp, fecha_ultimo_contacto
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            """, (TENANT, telefono, nombre_p, apellido_p, score, estado,
                  tipo, zona, operacion, ciudad, presupuesto,
                  subniche, notas, fuente, fuente_detalle,
                  date.today(), True))
            print(f"[DB] INSERT lead tel={telefono}")

        # Activar seguimiento para caliente/tibio
        if score in ("caliente", "tibio"):
            cur.execute("""
                UPDATE leads SET
                    estado_seguimiento='activo',
                    cantidad_seguimientos=0,
                    proximo_seguimiento=%s,
                    ultimo_contacto_bot=NOW()
                WHERE tenant_slug=%s AND telefono=%s
            """, ((date.today() + timedelta(days=1)).isoformat(), TENANT, telefono))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error registrar_lead: {e}")


def guardar_email(telefono: str, email: str) -> None:
    """Guarda email de un lead."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE leads SET email=%s WHERE tenant_slug=%s AND telefono=%s",
                    (email, TENANT, telefono))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error guardar_email: {e}")


def guardar_cita(telefono: str, fecha_cita: str) -> None:
    """Guarda fecha de cita y cambia estado."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE leads SET fecha_cita=%s, estado='visita_agendada'
            WHERE tenant_slug=%s AND telefono=%s
        """, (fecha_cita[:10], TENANT, telefono))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error guardar_cita: {e}")


def guardar_propiedad_interes(telefono: str, propiedad: str) -> None:
    """Guarda la propiedad de interés."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE leads SET propiedad_interes=%s WHERE tenant_slug=%s AND telefono=%s",
                    (propiedad[:200], TENANT, telefono))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error guardar_propiedad_interes: {e}")


def actualizar_ultimo_contacto(telefono: str) -> None:
    """Actualiza fecha_ultimo_contacto."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE leads SET fecha_ultimo_contacto=NOW() WHERE tenant_slug=%s AND telefono=%s",
                    (TENANT, telefono))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error actualizar_ultimo_contacto: {e}")


def desactivar_seguimiento(telefono: str) -> None:
    """Pausa el seguimiento cuando el lead responde."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE leads SET estado_seguimiento='pausado'
            WHERE tenant_slug=%s AND telefono=%s AND estado_seguimiento IN ('activo', 'dormido')
        """, (TENANT, telefono))
        if cur.rowcount > 0:
            print(f"[DB] Seguimiento pausado para {telefono}")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error desactivar_seguimiento: {e}")


def activar_nurturing(telefono: str, dias: int = 3) -> None:
    """Activa nurturing para leads fríos."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE leads SET
                estado_seguimiento='activo',
                cantidad_seguimientos=0,
                proximo_seguimiento=%s
            WHERE tenant_slug=%s AND telefono=%s
        """, ((date.today() + timedelta(days=dias)).isoformat(), TENANT, telefono))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error activar_nurturing: {e}")


def guardar_historial(telefono: str, historial: str) -> None:
    """Guarda historial de conversación en notas_bot."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE leads SET notas_bot=%s WHERE tenant_slug=%s AND telefono=%s",
                    (historial[:5000], TENANT, telefono))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error guardar_historial: {e}")


# ── PROPIEDADES (equivalente a _at_buscar_propiedades) ───────────────────────

def buscar_propiedades(tipo: str = None, operacion: str = None,
                       zona: str = None, presupuesto: str = None,
                       limit: int = 5) -> list[dict]:
    """Busca propiedades filtradas. Retorna lista de dicts (misma interfaz que Airtable)."""
    if not _available():
        return []

    conditions = ["tenant_slug=%s", "(disponible='✅ Disponible' OR disponible='⏳ Reservado')"]
    params = [TENANT]

    if tipo:
        conditions.append("LOWER(tipo)=LOWER(%s)")
        params.append(tipo)
    if operacion:
        conditions.append("LOWER(operacion)=LOWER(%s)")
        params.append(operacion)
    if zona and zona.lower() not in ("otra zona", "otra", "no sé", "no se"):
        conditions.append("zona=%s")
        params.append(zona)
    if presupuesto and presupuesto in ("hata_50k", "50k_100k", "100k_200k", "mas_200k"):
        conditions.append("presupuesto=%s")
        params.append(presupuesto)

    where = " AND ".join(conditions)
    params.append(limit)

    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM propiedades WHERE {where} ORDER BY precio ASC LIMIT %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Mapear a formato compatible con Airtable (campos con mayúsculas)
        result = []
        for r in rows:
            result.append({
                "Titulo": r.get("titulo", ""),
                "Nombre": r.get("titulo", ""),
                "Descripcion": r.get("descripcion", ""),
                "Tipo": r.get("tipo", ""),
                "Operacion": r.get("operacion", ""),
                "Zona": r.get("zona", ""),
                "Precio": float(r["precio"]) if r.get("precio") else None,
                "Moneda": r.get("moneda", "USD"),
                "Presupuesto": r.get("presupuesto", ""),
                "Disponible": r.get("disponible", "✅ Disponible"),
                "Dormitorios": r.get("dormitorios"),
                "Banios": r.get("banios"),
                "Metros_Cubiertos": r.get("metros_cubiertos"),
                "Metros_Terreno": r.get("metros_terreno"),
                "Imagen": r.get("imagen_url", ""),
                "Maps": r.get("maps_url", ""),
                "Direccion": r.get("direccion", ""),
            })
        return result
    except Exception as e:
        print(f"[DB] Error buscar_propiedades: {e}")
        return []


# ── CRM ENDPOINTS DATA ──────────────────────────────────────────────────────

def get_all_leads() -> list[dict]:
    """Retorna todos los leads para el CRM."""
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM leads WHERE tenant_slug=%s ORDER BY created_at DESC", (TENANT,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Mapear a formato compatible con CRM HTML (campos Airtable-like)
        result = []
        for r in rows:
            result.append({
                "id": f"pg_{r['id']}",
                "Nombre": r.get("nombre", ""),
                "Apellido": r.get("apellido", ""),
                "Telefono": r.get("telefono", ""),
                "Email": r.get("email", ""),
                "Operacion": r.get("operacion", ""),
                "Tipo_Propiedad": r.get("tipo_propiedad", ""),
                "Zona": r.get("zona", ""),
                "Presupuesto": r.get("presupuesto", ""),
                "Estado": r.get("estado", "no_contactado"),
                "Score": r.get("score_numerico", 0),
                "Sub_nicho": r.get("sub_nicho", ""),
                "Notas_Bot": r.get("notas_bot", ""),
                "Fuente": r.get("fuente", ""),
                "Fuente_Detalle": r.get("fuente_detalle", ""),
                "Propiedad_Interes": r.get("propiedad_interes", ""),
                "Ciudad": r.get("ciudad", ""),
                "Fecha_WhatsApp": r["fecha_whatsapp"].isoformat() if r.get("fecha_whatsapp") else "",
                "Fecha_Cita": r["fecha_cita"].isoformat() if r.get("fecha_cita") else "",
                "fecha_ultimo_contacto": r["fecha_ultimo_contacto"].isoformat() if r.get("fecha_ultimo_contacto") else "",
                "Llego_WhatsApp": r.get("llego_whatsapp", True),
                "Estado_Seguimiento": r.get("estado_seguimiento", ""),
                "Cantidad_Seguimientos": r.get("cantidad_seguimientos", 0),
                # Sprint 1 — Campos universales multi-subnicho
                "Asesor_Asignado": r.get("asesor_asignado", ""),
                "Tipo_Cliente": r.get("tipo_cliente", ""),
                "Propiedad_Interes_Id": r.get("propiedad_interes_id"),
            })
        return result
    except Exception as e:
        print(f"[DB] Error get_all_leads: {e}")
        return []


def get_all_propiedades() -> list[dict]:
    """Retorna todas las propiedades para el CRM."""
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM propiedades WHERE tenant_slug=%s ORDER BY created_at DESC", (TENANT,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Mapear a formato compatible con CRM HTML (campos Airtable-like)
        result = []
        for r in rows:
            result.append({
                "id": f"pg_{r['id']}",
                "Titulo": r.get("titulo", ""),
                "titulo": r.get("titulo", ""),
                "Nombre": r.get("titulo", ""),
                "Descripcion": r.get("descripcion", ""),
                "descripcion": r.get("descripcion", ""),
                "Tipo": r.get("tipo", ""),
                "tipo": r.get("tipo", ""),
                "Operacion": r.get("operacion", ""),
                "operacion": r.get("operacion", ""),
                "Zona": r.get("zona", ""),
                "zona": r.get("zona", ""),
                "Precio": float(r["precio"]) if r.get("precio") else None,
                "precio": float(r["precio"]) if r.get("precio") else None,
                "Moneda": r.get("moneda", "USD"),
                "moneda": r.get("moneda", "USD"),
                "Presupuesto": r.get("presupuesto", ""),
                "presupuesto": r.get("presupuesto", ""),
                "Disponible": r.get("disponible", "✅ Disponible"),
                "disponible": r.get("disponible", "✅ Disponible"),
                "Dormitorios": r.get("dormitorios"),
                "dormitorios": r.get("dormitorios"),
                "Banios": r.get("banios"),
                "banios": r.get("banios"),
                "Metros_Cubiertos": float(r["metros_cubiertos"]) if r.get("metros_cubiertos") else None,
                "metros_cubiertos": float(r["metros_cubiertos"]) if r.get("metros_cubiertos") else None,
                "Metros_Terreno": float(r["metros_terreno"]) if r.get("metros_terreno") else None,
                "metros_terreno": float(r["metros_terreno"]) if r.get("metros_terreno") else None,
                "Imagen_URL": r.get("imagen_url", ""),
                "imagen_url": r.get("imagen_url", ""),
                "Imagen": r.get("imagen_url", ""),
                "Google_Maps_URL": r.get("maps_url", ""),
                "Maps": r.get("maps_url", ""),
                "maps_url": r.get("maps_url", ""),
                "Direccion": r.get("direccion", ""),
                "direccion": r.get("direccion", ""),
                # Sprint 1 — Campos universales multi-subnicho
                "Propietario_Nombre": r.get("propietario_nombre", ""),
                "Propietario_Telefono": r.get("propietario_telefono", ""),
                "Propietario_Email": r.get("propietario_email", ""),
                "Comision_Pct": float(r["comision_pct"]) if r.get("comision_pct") else None,
                "Tipo_Cartera": r.get("tipo_cartera", "propia"),
                "Asesor_Asignado": r.get("asesor_asignado", ""),
                "Loteo": r.get("loteo", ""),
                "Numero_Lote": r.get("numero_lote", ""),
                "Propietario_Id": r.get("propietario_id"),
            })
        return result
    except Exception as e:
        print(f"[DB] Error get_all_propiedades: {e}")
        return []


def get_all_activos() -> list[dict]:
    """Retorna todos los clientes activos para el CRM."""
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM clientes_activos WHERE tenant_slug=%s ORDER BY created_at DESC", (TENANT,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Mapear a formato Airtable-like
        result = []
        for r in rows:
            result.append({
                "id": f"pg_{r['id']}",
                "Nombre": r.get("nombre", ""),
                "Apellido": r.get("apellido", ""),
                "Telefono": r.get("telefono", ""),
                "Email": r.get("email", ""),
                "Propiedad": r.get("propiedad", ""),
                "Estado_Pago": r.get("estado_pago", "al_dia"),
                "Monto_Cuota": float(r["monto_cuota"]) if r.get("monto_cuota") else None,
                "Cuotas_Pagadas": r.get("cuotas_pagadas", 0),
                "Cuotas_Total": r.get("cuotas_total", 0),
                "Proximo_Vencimiento": r["proximo_vencimiento"].isoformat() if r.get("proximo_vencimiento") else "",
                "Notas": r.get("notas", ""),
            })
        return result
    except Exception as e:
        print(f"[DB] Error get_all_activos: {e}")
        return []


def actualizar_score_por_telefono(telefono: str, score: str) -> bool:
    """Actualiza score de un lead por teléfono. Usado por webhook Chatwoot."""
    if not _available() or score not in ("caliente", "tibio", "frio"):
        return False
    tel = re.sub(r'\D', '', telefono)
    score_num = {"caliente": 12, "tibio": 7, "frio": 3}.get(score, 0)
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE leads
            SET score=%s, score_numerico=%s, fecha_ultimo_contacto=now()
            WHERE tenant_slug=%s AND telefono=%s
        """, (score, score_num, TENANT, tel))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        if ok:
            print(f"[DB] Score actualizado desde Chatwoot: {tel} → {score}")
        return ok
    except Exception as e:
        print(f"[DB] Error actualizar_score_por_telefono: {e}")
        return False


def update_lead(record_id: str, campos: dict) -> bool:
    """Actualiza un lead por ID."""
    if not _available():
        return False
    # record_id viene como "pg_123" — extraer el número
    pg_id = int(record_id.replace("pg_", "")) if record_id.startswith("pg_") else record_id

    # Mapear campos Airtable-like a columnas PostgreSQL
    col_map = {
        "Nombre": "nombre", "Apellido": "apellido", "Telefono": "telefono",
        "Email": "email", "Operacion": "operacion", "Tipo_Propiedad": "tipo_propiedad",
        "Presupuesto": "presupuesto", "Zona": "zona", "Estado": "estado",
        "Notas_Bot": "notas_bot", "Fuente": "fuente", "Ciudad": "ciudad",
        "Propiedad_Interes": "propiedad_interes", "Fuente_Detalle": "fuente_detalle",
        # Sprint 1 — Campos universales multi-subnicho
        "Asesor_Asignado": "asesor_asignado", "Tipo_Cliente": "tipo_cliente",
        "Propiedad_Interes_Id": "propiedad_interes_id",
    }

    sets = []
    values = []
    for k, v in campos.items():
        col = col_map.get(k, k.lower())
        sets.append(f"{col}=%s")
        values.append(v)

    if not sets:
        return False

    values.append(pg_id)
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id=%s", values)
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[DB] Error update_lead: {e}")
        return False


def create_lead(campos: dict) -> dict:
    """Crea un lead nuevo."""
    if not _available():
        return {"error": "DB no disponible"}

    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO leads (tenant_slug, telefono, nombre, apellido, email,
                operacion, tipo_propiedad, presupuesto, zona, estado,
                notas_bot, fuente, ciudad, sub_nicho, fecha_whatsapp, llego_whatsapp)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            TENANT,
            campos.get("Telefono", ""),
            campos.get("Nombre", ""),
            campos.get("Apellido", ""),
            campos.get("Email", ""),
            campos.get("Operacion", ""),
            campos.get("Tipo_Propiedad", ""),
            campos.get("Presupuesto", ""),
            campos.get("Zona", ""),
            campos.get("Estado", "no_contactado"),
            campos.get("Notas_Bot", ""),
            campos.get("Fuente", "whatsapp_directo"),
            campos.get("Ciudad", ""),
            campos.get("Sub_nicho", ""),
            date.today(),
            campos.get("Llego_WhatsApp", True),
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"id": f"pg_{new_id}"}
    except Exception as e:
        print(f"[DB] Error create_lead: {e}")
        return {"error": str(e)}


# ── DELETE LEADS ─────────────────────────────────────────────────────────────

def delete_lead(record_id: str) -> bool:
    if not _available():
        return False
    pg_id = int(record_id.replace("pg_", "")) if record_id.startswith("pg_") else record_id
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM leads WHERE id=%s AND tenant_slug=%s", (pg_id, TENANT))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[DB] Error delete_lead: {e}")
        return False


# ── CRUD PROPIEDADES ────────────────────────────────────────────────────────

def create_propiedad(campos: dict) -> dict:
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO propiedades (
                tenant_slug, titulo, descripcion, tipo, operacion,
                zona, precio, moneda, presupuesto, disponible,
                dormitorios, banios, metros_cubiertos, metros_terreno,
                imagen_url, maps_url, direccion
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            TENANT,
            campos.get("titulo") or campos.get("Titulo", ""),
            campos.get("descripcion") or campos.get("Descripcion", ""),
            campos.get("tipo") or campos.get("Tipo", ""),
            campos.get("operacion") or campos.get("Operacion", ""),
            campos.get("zona") or campos.get("Zona", ""),
            campos.get("precio") or campos.get("Precio") or None,
            campos.get("moneda") or campos.get("Moneda", "USD"),
            campos.get("presupuesto") or campos.get("Presupuesto", ""),
            campos.get("disponible") or campos.get("Disponible", "✅ Disponible"),
            campos.get("dormitorios") or campos.get("Dormitorios") or None,
            campos.get("banios") or campos.get("Banios") or None,
            campos.get("metros_cubiertos") or campos.get("Metros_Cubiertos") or None,
            campos.get("metros_terreno") or campos.get("Metros_Terreno") or None,
            campos.get("imagen_url") or campos.get("Imagen", ""),
            campos.get("maps_url") or campos.get("Maps", ""),
            campos.get("direccion") or campos.get("Direccion", ""),
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"id": f"pg_{new_id}"}
    except Exception as e:
        print(f"[DB] Error create_propiedad: {e}")
        return {"error": str(e)}


def update_propiedad(record_id: str, campos: dict) -> bool:
    if not _available():
        return False
    pg_id = int(record_id.replace("pg_", "")) if record_id.startswith("pg_") else record_id

    col_map = {
        "Titulo": "titulo", "Nombre": "titulo", "Descripcion": "descripcion",
        "Tipo": "tipo", "Operacion": "operacion", "Zona": "zona",
        "Precio": "precio", "Moneda": "moneda", "Presupuesto": "presupuesto",
        "Disponible": "disponible", "Dormitorios": "dormitorios",
        "Banios": "banios", "Metros_Cubiertos": "metros_cubiertos",
        "Metros_Terreno": "metros_terreno", "Imagen": "imagen_url",
        "Maps": "maps_url", "Direccion": "direccion",
        # Sprint 1 — Campos universales multi-subnicho
        "Propietario_Nombre": "propietario_nombre",
        "Propietario_Telefono": "propietario_telefono",
        "Propietario_Email": "propietario_email",
        "Comision_Pct": "comision_pct",
        "Tipo_Cartera": "tipo_cartera",
        "Asesor_Asignado": "asesor_asignado",
        "Loteo": "loteo",
        "Numero_Lote": "numero_lote",
        "Propietario_Id": "propietario_id",
    }
    sets, values = [], []
    for k, v in campos.items():
        col = col_map.get(k, k.lower())
        sets.append(f"{col}=%s")
        values.append(v)
    if not sets:
        return False
    values.append(pg_id)
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(f"UPDATE propiedades SET {', '.join(sets)} WHERE id=%s", values)
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[DB] Error update_propiedad: {e}")
        return False


def delete_propiedad(record_id: str) -> bool:
    if not _available():
        return False
    pg_id = int(record_id.replace("pg_", "")) if record_id.startswith("pg_") else record_id
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM propiedades WHERE id=%s AND tenant_slug=%s", (pg_id, TENANT))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[DB] Error delete_propiedad: {e}")
        return False


# ── CRUD ACTIVOS ─────────────────────────────────────────────────────────────

def create_activo(campos: dict) -> dict:
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clientes_activos (
                tenant_slug, nombre, apellido, telefono, email,
                propiedad, estado_pago, monto_cuota, cuotas_pagadas,
                cuotas_total, proximo_vencimiento, notas
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            TENANT,
            campos.get("nombre") or campos.get("Nombre", ""),
            campos.get("apellido") or campos.get("Apellido", ""),
            campos.get("telefono") or campos.get("Telefono", ""),
            campos.get("email") or campos.get("Email", ""),
            campos.get("propiedad") or campos.get("Propiedad", ""),
            campos.get("estado_pago") or campos.get("Estado_Pago", "al_dia"),
            campos.get("monto_cuota") or campos.get("Monto_Cuota") or None,
            campos.get("cuotas_pagadas") or campos.get("Cuotas_Pagadas") or 0,
            campos.get("cuotas_total") or campos.get("Cuotas_Total") or 0,
            campos.get("proximo_vencimiento") or campos.get("Proximo_Vencimiento") or None,
            campos.get("notas") or campos.get("Notas", ""),
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"id": f"pg_{new_id}"}
    except Exception as e:
        return {"error": str(e)}


def update_activo(record_id: str, campos: dict) -> bool:
    if not _available():
        return False
    pg_id = int(record_id.replace("pg_", "")) if record_id.startswith("pg_") else record_id
    col_map = {
        "Nombre": "nombre", "Apellido": "apellido", "Telefono": "telefono",
        "Email": "email", "Propiedad": "propiedad", "Estado_Pago": "estado_pago",
        "Monto_Cuota": "monto_cuota", "Cuotas_Pagadas": "cuotas_pagadas",
        "Cuotas_Total": "cuotas_total", "Proximo_Vencimiento": "proximo_vencimiento",
        "Notas": "notas",
    }
    sets, values = [], []
    for k, v in campos.items():
        col = col_map.get(k, k.lower())
        sets.append(f"{col}=%s")
        values.append(v)
    if not sets:
        return False
    values.append(pg_id)
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(f"UPDATE clientes_activos SET {', '.join(sets)} WHERE id=%s", values)
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        return False


def delete_activo(record_id: str) -> bool:
    if not _available():
        return False
    pg_id = int(record_id.replace("pg_", "")) if record_id.startswith("pg_") else record_id
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM clientes_activos WHERE id=%s AND tenant_slug=%s", (pg_id, TENANT))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        return False


# ── MÉTRICAS ─────────────────────────────────────────────────────────────────

def get_metricas() -> dict:
    """Retorna métricas del pipeline."""
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT count(*) as total FROM leads WHERE tenant_slug=%s", (TENANT,))
        total = cur.fetchone()["total"]

        cur.execute("""
            SELECT estado, count(*) as cnt
            FROM leads WHERE tenant_slug=%s GROUP BY estado
        """, (TENANT,))
        por_estado = {r["estado"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT count(*) as cnt FROM leads WHERE tenant_slug=%s AND fecha_cita IS NOT NULL", (TENANT,))
        con_cita = cur.fetchone()["cnt"]

        cur.execute("SELECT count(*) as cnt FROM leads WHERE tenant_slug=%s AND estado='cerrado_ganado'", (TENANT,))
        cerrados = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT
                sum(CASE WHEN score_numerico >= 12 THEN 1 ELSE 0 END) as caliente,
                sum(CASE WHEN score_numerico >= 7 AND score_numerico < 12 THEN 1 ELSE 0 END) as tibio,
                sum(CASE WHEN score_numerico < 7 THEN 1 ELSE 0 END) as frio
            FROM leads WHERE tenant_slug=%s
        """, (TENANT,))
        scores = cur.fetchone()

        cur.execute("""
            SELECT fuente, count(*) as cnt
            FROM leads WHERE tenant_slug=%s GROUP BY fuente
        """, (TENANT,))
        fuentes = {r["fuente"]: r["cnt"] for r in cur.fetchall()}

        cur.close()
        conn.close()

        tasa_citas = round((con_cita / total) * 100, 1) if total > 0 else 0
        tasa_cierre = round((cerrados / total) * 100, 1) if total > 0 else 0

        return {
            "total": total,
            "por_estado": por_estado,
            "scores": {"caliente": scores["caliente"] or 0, "tibio": scores["tibio"] or 0, "frio": scores["frio"] or 0},
            "fuentes": fuentes,
            "con_cita": con_cita,
            "cerrados_ganados": cerrados,
            "tasa_citas": tasa_citas,
            "tasa_cierre": tasa_cierre,
        }
    except Exception as e:
        print(f"[DB] Error get_metricas: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# CRM COMPLETO MULTI-SUBNICHO — Sprints 3-8
# ═══════════════════════════════════════════════════════════════════════════

def _crud_generico(tabla: str, accion: str, campos: dict = None, record_id: int = None) -> dict:
    """Helper genérico para CRUD de tablas simples del CRM completo."""
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if accion == "list":
            cur.execute(f"SELECT * FROM {tabla} WHERE tenant_slug=%s ORDER BY created_at DESC", (TENANT,))
            rows = cur.fetchall()
            result = []
            for r in rows:
                row_dict = dict(r)
                # Convertir tipos no-JSON-serializables
                for k, v in row_dict.items():
                    if hasattr(v, 'isoformat'):
                        row_dict[k] = v.isoformat()
                    elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                        row_dict[k] = float(v)
                result.append(row_dict)
            cur.close()
            conn.close()
            return {"items": result, "total": len(result)}

        elif accion == "create":
            keys = list(campos.keys())
            placeholders = ", ".join(["%s"] * (len(keys) + 1))
            cols = ", ".join(["tenant_slug"] + keys)
            values = [TENANT] + list(campos.values())
            cur.execute(f"INSERT INTO {tabla} ({cols}) VALUES ({placeholders}) RETURNING id", values)
            new_id = cur.fetchone()["id"]
            conn.commit()
            cur.close()
            conn.close()
            return {"id": new_id, "ok": True}

        elif accion == "update":
            sets = ", ".join([f"{k}=%s" for k in campos.keys()])
            values = list(campos.values()) + [record_id, TENANT]
            cur.execute(f"UPDATE {tabla} SET {sets} WHERE id=%s AND tenant_slug=%s", values)
            ok = cur.rowcount > 0
            conn.commit()
            cur.close()
            conn.close()
            return {"ok": ok}

        elif accion == "delete":
            cur.execute(f"DELETE FROM {tabla} WHERE id=%s AND tenant_slug=%s", (record_id, TENANT))
            ok = cur.rowcount > 0
            conn.commit()
            cur.close()
            conn.close()
            return {"ok": ok}

        cur.close()
        conn.close()
        return {"error": "acción inválida"}
    except Exception as e:
        print(f"[DB] Error _crud_generico {tabla}/{accion}: {e}")
        return {"error": str(e)}


# ── Asesores (Sprint 3) ─────────────────────────────────────────────────────
def get_all_asesores():
    return _crud_generico("asesores", "list")
def create_asesor(campos: dict):
    return _crud_generico("asesores", "create", campos=campos)
def update_asesor(record_id: int, campos: dict):
    return _crud_generico("asesores", "update", campos=campos, record_id=record_id)
def delete_asesor(record_id: int):
    return _crud_generico("asesores", "delete", record_id=record_id)


# ── Propietarios (Sprint 4) ─────────────────────────────────────────────────
def get_all_propietarios():
    return _crud_generico("propietarios", "list")
def create_propietario(campos: dict):
    return _crud_generico("propietarios", "create", campos=campos)
def update_propietario(record_id: int, campos: dict):
    return _crud_generico("propietarios", "update", campos=campos, record_id=record_id)
def delete_propietario(record_id: int):
    return _crud_generico("propietarios", "delete", record_id=record_id)


# ── Loteos (Sprint 5) ───────────────────────────────────────────────────────
def get_all_loteos():
    return _crud_generico("loteos", "list")
def create_loteo(campos: dict):
    return _crud_generico("loteos", "create", campos=campos)
def update_loteo(record_id: int, campos: dict):
    return _crud_generico("loteos", "update", campos=campos, record_id=record_id)
def delete_loteo(record_id: int):
    return _crud_generico("loteos", "delete", record_id=record_id)


# ── Lotes Mapa (Sprint 5) ───────────────────────────────────────────────────
def get_lotes_mapa(loteo_id: int = None):
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if loteo_id:
            cur.execute("SELECT * FROM lotes_mapa WHERE tenant_slug=%s AND loteo_id=%s ORDER BY numero_lote",
                       (TENANT, loteo_id))
        else:
            cur.execute("SELECT * FROM lotes_mapa WHERE tenant_slug=%s ORDER BY loteo_id, numero_lote", (TENANT,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
                elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                    row[k] = float(v)
            result.append(row)
        cur.close()
        conn.close()
        return {"items": result, "total": len(result)}
    except Exception as e:
        return {"error": str(e)}

def create_lote_mapa(campos: dict):
    return _crud_generico("lotes_mapa", "create", campos=campos)
def update_lote_mapa(record_id: int, campos: dict):
    return _crud_generico("lotes_mapa", "update", campos=campos, record_id=record_id)
def delete_lote_mapa(record_id: int):
    return _crud_generico("lotes_mapa", "delete", record_id=record_id)


# ── Contratos (Sprint 6) ────────────────────────────────────────────────────
def get_all_contratos():
    return _crud_generico("contratos", "list")
def create_contrato(campos: dict):
    return _crud_generico("contratos", "create", campos=campos)
def update_contrato(record_id: int, campos: dict):
    return _crud_generico("contratos", "update", campos=campos, record_id=record_id)
def delete_contrato(record_id: int):
    return _crud_generico("contratos", "delete", record_id=record_id)


# ── Visitas / Agenda (Sprint 8) ─────────────────────────────────────────────
def get_all_visitas():
    return _crud_generico("visitas", "list")
def create_visita(campos: dict):
    return _crud_generico("visitas", "create", campos=campos)
def update_visita(record_id: int, campos: dict):
    return _crud_generico("visitas", "update", campos=campos, record_id=record_id)
def delete_visita(record_id: int):
    return _crud_generico("visitas", "delete", record_id=record_id)


# ── Reportes (Sprint 7) ─────────────────────────────────────────────────────
def get_reportes(fecha_desde: str = None, fecha_hasta: str = None):
    """Reportes agregados para el dashboard."""
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Cierres por asesor
        cur.execute("""
            SELECT COALESCE(asesor_asignado, 'Sin asignar') as asesor,
                   count(*) FILTER (WHERE estado = 'cerrado_ganado') as ganados,
                   count(*) as total_leads
            FROM leads WHERE tenant_slug=%s
            GROUP BY asesor_asignado
            ORDER BY ganados DESC
        """, (TENANT,))
        por_asesor = [dict(r) for r in cur.fetchall()]

        # Conversión por fuente
        cur.execute("""
            SELECT fuente,
                   count(*) as total,
                   count(*) FILTER (WHERE estado = 'cerrado_ganado') as ganados,
                   count(*) FILTER (WHERE fecha_cita IS NOT NULL) as con_cita
            FROM leads WHERE tenant_slug=%s
            GROUP BY fuente
            ORDER BY total DESC
        """, (TENANT,))
        por_fuente = [dict(r) for r in cur.fetchall()]

        # Ventas por mes (últimos 6 meses)
        cur.execute("""
            SELECT to_char(date_trunc('month', updated_at), 'YYYY-MM') as mes,
                   count(*) as ventas
            FROM leads
            WHERE tenant_slug=%s AND estado='cerrado_ganado'
              AND updated_at > now() - interval '6 months'
            GROUP BY mes
            ORDER BY mes
        """, (TENANT,))
        por_mes = [dict(r) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return {
            "por_asesor": por_asesor,
            "por_fuente": por_fuente,
            "ventas_por_mes": por_mes,
        }
    except Exception as e:
        print(f"[DB] Error get_reportes: {e}")
        return {"error": str(e)}
