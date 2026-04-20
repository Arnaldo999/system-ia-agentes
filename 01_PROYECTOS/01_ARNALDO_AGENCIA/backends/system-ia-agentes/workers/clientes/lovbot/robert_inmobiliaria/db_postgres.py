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
    fuente = "meta_ads" if fuente_detalle and fuente_detalle.startswith("ad:") else "whatsapp_directo"

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

def get_lead_by_telefono(telefono: str) -> dict | None:
    """Busca un lead por teléfono. Devuelve dict con todos los campos o None.
    Usado para detectar 'lead recurrente' que vuelve a escribir tras tiempo
    ausente o tras haber sido calificado.

    Tolerante a + al inicio (algunos leads tienen '+5493...' otros '5493...').
    Match por sufijo: usa los últimos 10 dígitos para evitar problemas con
    código de país inconsistente.
    """
    if not _available():
        return None
    import re as _re
    tel_solo_digitos = _re.sub(r'\D', '', telefono)
    if not tel_solo_digitos:
        return None
    sufijo = tel_solo_digitos[-10:]  # últimos 10 dígitos = número local
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Match por sufijo (cubre +549... vs 549... vs 9...)
        cur.execute(
            "SELECT * FROM leads WHERE tenant_slug=%s AND telefono LIKE %s ORDER BY fecha_ultimo_contacto DESC NULLS LAST LIMIT 1",
            (TENANT, f"%{sufijo}")
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"[DB] Error get_lead_by_telefono ({telefono}): {e}")
        return None


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

def _recalc_contadores_loteo(loteo_id: int):
    """Recalcula lotes_disponibles/reservados/vendidos en la tabla loteos.

    Se ejecuta luego de crear/editar/eliminar un lote_mapa para mantener
    los contadores sincronizados con el estado real de lotes_mapa.
    """
    if not _available() or not loteo_id:
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE loteos l SET
              lotes_disponibles = COALESCE(s.disp, 0),
              lotes_reservados  = COALESCE(s.res, 0),
              lotes_vendidos    = COALESCE(s.vend, 0),
              updated_at        = CURRENT_TIMESTAMP
            FROM (
              SELECT
                COUNT(*) FILTER (WHERE estado='disponible') AS disp,
                COUNT(*) FILTER (WHERE estado='reservado')  AS res,
                COUNT(*) FILTER (WHERE estado='vendido')    AS vend
              FROM lotes_mapa
              WHERE tenant_slug=%s AND loteo_id=%s
            ) s
            WHERE l.id=%s AND l.tenant_slug=%s
            """,
            (TENANT, loteo_id, loteo_id, TENANT),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error _recalc_contadores_loteo({loteo_id}): {e}")


def _sincronizar_propiedad_cliente(cliente_id: int, loteo_id: int, numero_lote: str, estado: str):
    """Actualiza el campo `propiedad` de clientes_activos cuando un lote se asigna.

    Si estado in (reservado, vendido) → escribe "{Nombre loteo} · {numero_lote}".
    Si estado == disponible → limpia la propiedad.

    Espejo inverso del flujo Maicol/Airtable donde el campo `propiedad` del
    cliente refleja la unidad asignada.
    """
    if not _available() or not cliente_id:
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        if estado in ("reservado", "vendido"):
            cur.execute("SELECT nombre FROM loteos WHERE id=%s AND tenant_slug=%s",
                        (loteo_id, TENANT))
            row = cur.fetchone()
            nombre_loteo = row[0] if row else f"Loteo #{loteo_id}"
            propiedad = f"{nombre_loteo} · {numero_lote}"
            cur.execute(
                "UPDATE clientes_activos SET propiedad=%s, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=%s AND tenant_slug=%s",
                (propiedad, cliente_id, TENANT),
            )
        else:
            # estado disponible → liberar cliente (opcional, solo si el cliente
            # tenía exactamente ese lote asignado, para no borrar otra propiedad)
            pass
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error _sincronizar_propiedad_cliente(c={cliente_id}, l={loteo_id}): {e}")


def _liberar_cliente_anterior_si_hay(record_id: int, nuevo_cliente_id):
    """Si el lote cambió de cliente, limpia el campo propiedad del cliente anterior."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT cliente_id FROM lotes_mapa WHERE id=%s AND tenant_slug=%s",
                    (record_id, TENANT))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            anterior = row[0]
            if anterior and anterior != nuevo_cliente_id:
                conn2 = _conn()
                cur2 = conn2.cursor()
                cur2.execute(
                    "UPDATE clientes_activos SET propiedad=NULL, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=%s AND tenant_slug=%s",
                    (anterior, TENANT),
                )
                conn2.commit()
                cur2.close()
                conn2.close()
    except Exception as e:
        print(f"[DB] Error _liberar_cliente_anterior_si_hay: {e}")


def create_lote_mapa(campos: dict):
    loteo_id = campos.get("loteo_id")
    result = _crud_generico("lotes_mapa", "create", campos=campos)
    if result.get("ok") and loteo_id:
        _recalc_contadores_loteo(int(loteo_id))
        # Sincronizar propiedad del cliente si se asignó
        cliente_id = campos.get("cliente_id")
        if cliente_id:
            _sincronizar_propiedad_cliente(
                int(cliente_id), int(loteo_id),
                campos.get("numero_lote", ""),
                campos.get("estado", "disponible"),
            )
    return result

def update_lote_mapa(record_id: int, campos: dict):
    # Guardar cliente anterior antes de update (para liberarlo si cambió)
    nuevo_cliente_id = campos.get("cliente_id")
    if "cliente_id" in campos:
        _liberar_cliente_anterior_si_hay(record_id, nuevo_cliente_id)

    result = _crud_generico("lotes_mapa", "update", campos=campos, record_id=record_id)
    # Buscar loteo_id del registro (puede venir en campos o consultarlo)
    loteo_id = campos.get("loteo_id")
    numero_lote = campos.get("numero_lote")
    estado = campos.get("estado")
    if not loteo_id or not numero_lote or not estado:
        try:
            conn = _conn()
            cur = conn.cursor()
            cur.execute("SELECT loteo_id, numero_lote, estado FROM lotes_mapa WHERE id=%s AND tenant_slug=%s",
                        (record_id, TENANT))
            row = cur.fetchone()
            if row:
                loteo_id = loteo_id or row[0]
                numero_lote = numero_lote or row[1]
                estado = estado or row[2]
            cur.close()
            conn.close()
        except Exception:
            pass
    if loteo_id:
        _recalc_contadores_loteo(int(loteo_id))
        # Sincronizar propiedad del cliente si hay asignación
        if nuevo_cliente_id:
            _sincronizar_propiedad_cliente(
                int(nuevo_cliente_id), int(loteo_id),
                numero_lote or "", estado or "disponible",
            )
    return result

def delete_lote_mapa(record_id: int):
    # Consultar loteo_id + cliente_id antes de eliminar
    loteo_id = None
    cliente_id = None
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT loteo_id, cliente_id FROM lotes_mapa WHERE id=%s AND tenant_slug=%s",
                    (record_id, TENANT))
        row = cur.fetchone()
        if row:
            loteo_id = row[0]
            cliente_id = row[1]
        cur.close()
        conn.close()
    except Exception:
        pass
    result = _crud_generico("lotes_mapa", "delete", record_id=record_id)
    if loteo_id:
        _recalc_contadores_loteo(int(loteo_id))
    # Si el lote tenía cliente asignado, liberar su campo propiedad
    if cliente_id:
        try:
            conn = _conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE clientes_activos SET propiedad=NULL, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=%s AND tenant_slug=%s",
                (cliente_id, TENANT),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[DB] Error liberando cliente tras delete lote: {e}")
    return result


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


# ── BOT SESSIONS (persistencia de conversaciones entre deploys) ───────────────

def setup_bot_sessions():
    """Crea la tabla bot_sessions si no existe. Llamar al iniciar el worker."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_sessions (
                telefono     TEXT PRIMARY KEY,
                tenant       TEXT NOT NULL DEFAULT 'robert',
                sesion_data  JSONB NOT NULL DEFAULT '{}',
                historial    JSONB NOT NULL DEFAULT '[]',
                updated_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_sessions_tenant
            ON bot_sessions(tenant)
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("[DB] Tabla bot_sessions lista.")
    except Exception as e:
        print(f"[DB] Error setup_bot_sessions: {e}")


def get_bot_session(telefono: str) -> dict:
    """Carga sesión y historial desde PostgreSQL. Retorna {} si no existe."""
    if not _available():
        return {}
    try:
        import json
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT sesion_data, historial FROM bot_sessions WHERE telefono = %s AND tenant = %s",
            (telefono, TENANT),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {}
        sesion = row["sesion_data"] if isinstance(row["sesion_data"], dict) else json.loads(row["sesion_data"])
        historial = row["historial"] if isinstance(row["historial"], list) else json.loads(row["historial"])
        return {"sesion": sesion, "historial": historial}
    except Exception as e:
        print(f"[DB] Error get_bot_session ({telefono}): {e}")
        return {}


def save_bot_session(telefono: str, sesion: dict, historial: list) -> None:
    """Upsert de sesión y historial. Llamar en background thread."""
    if not _available():
        return
    try:
        import json
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bot_sessions (telefono, tenant, sesion_data, historial, updated_at)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, NOW())
            ON CONFLICT (telefono) DO UPDATE SET
                sesion_data = EXCLUDED.sesion_data,
                historial   = EXCLUDED.historial,
                updated_at  = NOW()
        """, (telefono, TENANT, json.dumps(sesion), json.dumps(historial)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error save_bot_session ({telefono}): {e}")


def delete_bot_session(telefono: str) -> None:
    """Elimina sesión cuando el lead se califica o cierra."""
    if not _available():
        return
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM bot_sessions WHERE telefono = %s AND tenant = %s",
            (telefono, TENANT),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error delete_bot_session ({telefono}): {e}")


# ── RESÚMENES DE CONVERSACIÓN ────────────────────────────────────────────────

def crear_tabla_resumenes() -> dict:
    """Crea la tabla resumenes_conversacion si no existe."""
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS resumenes_conversacion (
                id SERIAL PRIMARY KEY,
                tenant_slug VARCHAR(50) NOT NULL,
                lead_id INT,
                telefono VARCHAR(50) NOT NULL,
                nombre VARCHAR(200),
                resumen TEXT,
                presupuesto VARCHAR(100),
                zona VARCHAR(100),
                urgencia VARCHAR(50),
                financiamiento VARCHAR(100),
                score INT DEFAULT 3,
                cantidad_mensajes INT DEFAULT 0,
                duracion_minutos INT DEFAULT 0,
                fecha_conversacion TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(tenant_slug, telefono)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_resumenes_tenant_fecha ON resumenes_conversacion(tenant_slug, fecha_conversacion DESC)")
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "mensaje": "Tabla resumenes_conversacion creada"}
    except Exception as e:
        return {"error": str(e)}


def get_leads_con_cita(solo_sin_resumen: bool = False) -> list[dict]:
    """Devuelve leads con fecha_cita, opcionalmente solo los que no tienen resumen aún."""
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if solo_sin_resumen:
            cur.execute("""
                SELECT l.* FROM leads l
                LEFT JOIN resumenes_conversacion r
                    ON r.tenant_slug = l.tenant_slug AND r.telefono = l.telefono
                WHERE l.tenant_slug = %s AND l.fecha_cita IS NOT NULL AND r.id IS NULL
            """, (TENANT,))
        else:
            cur.execute("""
                SELECT * FROM leads
                WHERE tenant_slug = %s AND fecha_cita IS NOT NULL
                ORDER BY fecha_cita DESC
            """, (TENANT,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] Error get_leads_con_cita: {e}")
        return []


def guardar_resumen(data: dict) -> dict:
    """Guarda o actualiza un resumen (upsert por tenant+telefono)."""
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO resumenes_conversacion (
                tenant_slug, lead_id, telefono, nombre, resumen,
                presupuesto, zona, urgencia, financiamiento,
                score, cantidad_mensajes, duracion_minutos, fecha_conversacion
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s, NOW()))
            ON CONFLICT (tenant_slug, telefono) DO UPDATE SET
                lead_id = EXCLUDED.lead_id,
                nombre = EXCLUDED.nombre,
                resumen = EXCLUDED.resumen,
                presupuesto = EXCLUDED.presupuesto,
                zona = EXCLUDED.zona,
                urgencia = EXCLUDED.urgencia,
                financiamiento = EXCLUDED.financiamiento,
                score = EXCLUDED.score,
                cantidad_mensajes = EXCLUDED.cantidad_mensajes,
                duracion_minutos = EXCLUDED.duracion_minutos,
                fecha_conversacion = COALESCE(EXCLUDED.fecha_conversacion, resumenes_conversacion.fecha_conversacion)
            RETURNING id
        """, (
            TENANT,
            data.get("lead_id"),
            data.get("telefono"),
            data.get("nombre"),
            data.get("resumen"),
            data.get("presupuesto"),
            data.get("zona"),
            data.get("urgencia"),
            data.get("financiamiento"),
            data.get("score") or 3,
            data.get("cantidad_mensajes") or 0,
            data.get("duracion_minutos") or 0,
            data.get("fecha_conversacion"),
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "id": new_id}
    except Exception as e:
        return {"error": str(e)}


# ── NURTURING 24H ────────────────────────────────────────────────────────────

def obtener_leads_sin_cita_24h() -> list[dict]:
    """Devuelve leads calificados (BANT completo) que:
    - estado IN ('calificado', 'contactado')
    - fecha_cita IS NULL
    - fecha_ultimo_contacto < NOW() - INTERVAL '24 hours' (o updated_at si no hay fecha_ultimo_contacto)
    - nurturing_24h_enviado IS NOT TRUE
    Solo para el tenant activo.
    """
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, telefono, nombre, apellido, ciudad,
                   tipo_propiedad, operacion, presupuesto,
                   score, estado, fecha_ultimo_contacto, updated_at
            FROM leads
            WHERE tenant_slug = %s
              AND estado IN ('calificado', 'contactado')
              AND fecha_cita IS NULL
              AND COALESCE(nurturing_24h_enviado, FALSE) = FALSE
              AND COALESCE(fecha_ultimo_contacto, updated_at, created_at) < NOW() - INTERVAL '24 hours'
            ORDER BY COALESCE(fecha_ultimo_contacto, updated_at) ASC
        """, (TENANT,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            row = dict(r)
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
            result.append(row)
        print(f"[DB] Nurturing 24h: {len(result)} leads elegibles")
        return result
    except Exception as e:
        print(f"[DB] Error obtener_leads_sin_cita_24h: {e}")
        return []


def marcar_nurturing_enviado(lead_id: int) -> bool:
    """Marca el flag nurturing_24h_enviado=TRUE para evitar reenvíos.
    Idempotente: si ya estaba marcado, no falla.
    """
    if not _available():
        return False
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE leads
            SET nurturing_24h_enviado = TRUE,
                nurturing_24h_fecha = NOW()
            WHERE id = %s AND tenant_slug = %s
        """, (lead_id, TENANT))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        if ok:
            print(f"[DB] Nurturing marcado: lead_id={lead_id}")
        return ok
    except Exception as e:
        print(f"[DB] Error marcar_nurturing_enviado (id={lead_id}): {e}")
        return False


def setup_nurturing_columns() -> dict:
    """Agrega las columnas nurturing_24h_enviado y nurturing_24h_fecha a la tabla leads
    si no existen. Idempotente — seguro llamar múltiples veces.
    """
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            ALTER TABLE leads
            ADD COLUMN IF NOT EXISTS nurturing_24h_enviado BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS nurturing_24h_fecha   TIMESTAMPTZ
        """)
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "mensaje": "Columnas nurturing_24h_enviado y nurturing_24h_fecha verificadas"}
    except Exception as e:
        print(f"[DB] Error setup_nurturing_columns: {e}")
        return {"error": str(e)}


def listar_resumenes(limit: int = 20, score_min: int = None,
                      desde: str = None, search: str = None) -> list[dict]:
    """Lista resúmenes con filtros opcionales."""
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        sql = "SELECT * FROM resumenes_conversacion WHERE tenant_slug = %s"
        params = [TENANT]
        if score_min is not None:
            sql += " AND score >= %s"
            params.append(score_min)
        if desde:
            sql += " AND fecha_conversacion >= %s"
            params.append(desde)
        if search:
            sql += " AND (nombre ILIKE %s OR resumen ILIKE %s OR zona ILIKE %s)"
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard, wildcard])
        sql += " ORDER BY fecha_conversacion DESC LIMIT %s"
        params.append(min(limit, 100))
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] Error listar_resumenes: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════
# WABA CLIENTS — Tech Provider onboarding (Fase 1)
# Tabla global (sin tenant_slug): un registro por cliente externo de Robert
# ═══════════════════════════════════════════════════════════════════════════

def setup_waba_clients_table() -> dict:
    """Crea la tabla waba_clients si no existe. Idempotente."""
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS waba_clients (
                id                  SERIAL PRIMARY KEY,
                client_name         TEXT NOT NULL,
                client_slug         TEXT UNIQUE NOT NULL,
                waba_id             TEXT UNIQUE NOT NULL,
                phone_number_id     TEXT UNIQUE NOT NULL,
                display_phone_number TEXT,
                access_token        TEXT NOT NULL,
                worker_url          TEXT,
                estado              TEXT DEFAULT 'onboarded',
                webhook_subscrito   BOOLEAN DEFAULT FALSE,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW(),
                metadata            JSONB DEFAULT '{}'::jsonb,
                agencia_origen      TEXT DEFAULT 'lovbot',
                meta_user_id        TEXT
            )
        """)
        # Migration para tablas existentes (agrega columnas si no estan)
        cur.execute("""
            ALTER TABLE waba_clients
            ADD COLUMN IF NOT EXISTS agencia_origen TEXT DEFAULT 'lovbot'
        """)
        cur.execute("""
            ALTER TABLE waba_clients
            ADD COLUMN IF NOT EXISTS meta_user_id TEXT
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_waba_phone_id
            ON waba_clients(phone_number_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_waba_slug
            ON waba_clients(client_slug)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_waba_agencia
            ON waba_clients(agencia_origen)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_waba_meta_user
            ON waba_clients(meta_user_id)
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("[DB] Tabla waba_clients lista (con agencia_origen + meta_user_id).")
        return {"ok": True, "mensaje": "Tabla waba_clients verificada/creada (multi-agencia)"}
    except Exception as e:
        print(f"[DB] Error setup_waba_clients_table: {e}")
        return {"error": str(e)}


def registrar_waba_client(
    client_name: str,
    client_slug: str,
    waba_id: str,
    phone_number_id: str,
    access_token: str,
    worker_url: str = None,
    display_phone: str = None,
    agencia_origen: str = "lovbot",
    meta_user_id: str = None,
) -> dict:
    """UPSERT de cliente WABA por phone_number_id.

    agencia_origen: 'arnaldo' | 'mica' | 'lovbot' — qué agencia vendió este cliente.
    meta_user_id: ID del user Meta que hizo el Embedded Signup (viene del webhook
                  deauthorize para identificar a qué tenant pertenece el evento).
    """
    if not _available():
        return {"error": "DB no disponible"}
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO waba_clients
                (client_name, client_slug, waba_id, phone_number_id,
                 display_phone_number, access_token, worker_url,
                 agencia_origen, meta_user_id, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (phone_number_id) DO UPDATE SET
                client_name          = EXCLUDED.client_name,
                client_slug          = EXCLUDED.client_slug,
                waba_id              = EXCLUDED.waba_id,
                display_phone_number = COALESCE(EXCLUDED.display_phone_number, waba_clients.display_phone_number),
                access_token         = EXCLUDED.access_token,
                worker_url           = COALESCE(EXCLUDED.worker_url, waba_clients.worker_url),
                agencia_origen       = COALESCE(EXCLUDED.agencia_origen, waba_clients.agencia_origen),
                meta_user_id         = COALESCE(EXCLUDED.meta_user_id, waba_clients.meta_user_id),
                updated_at           = NOW()
            RETURNING id, client_slug, phone_number_id, agencia_origen
        """, (
            client_name, client_slug, waba_id, phone_number_id,
            display_phone, access_token, worker_url,
            agencia_origen, meta_user_id,
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "id": row["id"], "client_slug": row["client_slug"],
                "phone_number_id": row["phone_number_id"],
                "agencia_origen": row["agencia_origen"]}
    except Exception as e:
        print(f"[DB] Error registrar_waba_client: {e}")
        return {"error": str(e)}


def obtener_waba_client_por_phone(phone_number_id: str) -> dict | None:
    """SELECT de un cliente WABA por phone_number_id. Retorna dict o None."""
    if not _available():
        return None
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM waba_clients WHERE phone_number_id = %s",
            (phone_number_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        result = dict(row)
        for k, v in result.items():
            if hasattr(v, "isoformat"):
                result[k] = v.isoformat()
        return result
    except Exception as e:
        print(f"[DB] Error obtener_waba_client_por_phone: {e}")
        return None


def marcar_webhook_subscrito(phone_number_id: str) -> bool:
    """Marca webhook_subscrito=TRUE para un cliente WABA."""
    if not _available():
        return False
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE waba_clients
            SET webhook_subscrito = TRUE, updated_at = NOW()
            WHERE phone_number_id = %s
        """, (phone_number_id,))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        if ok:
            print(f"[DB] webhook_subscrito marcado para phone_id={phone_number_id}")
        return ok
    except Exception as e:
        print(f"[DB] Error marcar_webhook_subscrito: {e}")
        return False


def actualizar_waba_worker_url(phone_number_id: str, nuevo_url: str) -> bool:
    """Actualiza worker_url de un cliente WABA. Usado para mover clientes
    a un worker dedicado despues del onboarding inicial."""
    if not _available():
        return False
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE waba_clients
            SET worker_url = %s, updated_at = NOW()
            WHERE phone_number_id = %s
        """, (nuevo_url, phone_number_id))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        if ok:
            print(f"[DB] worker_url actualizado para phone_id={phone_number_id} -> {nuevo_url}")
        return ok
    except Exception as e:
        print(f"[DB] Error actualizar_waba_worker_url: {e}")
        return False


def listar_waba_clients() -> list[dict]:
    """SELECT todos los waba_clients (para admin/debug)."""
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM waba_clients ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            row = dict(r)
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
            result.append(row)
        return result
    except Exception as e:
        print(f"[DB] Error listar_waba_clients: {e}")
        return []


def listar_waba_clients_por_agencia(agencia: str) -> list[dict]:
    """SELECT waba_clients filtrado por agencia_origen (arnaldo/mica/lovbot).

    Usado por panels admin de cada agencia para ver solo SUS clientes.
    """
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM waba_clients WHERE agencia_origen = %s ORDER BY created_at DESC",
            (agencia,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            row = dict(r)
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
            result.append(row)
        return result
    except Exception as e:
        print(f"[DB] Error listar_waba_clients_por_agencia: {e}")
        return []


def actualizar_agencia_origen(phone_number_id: str, nueva_agencia: str) -> bool:
    """Cambia la agencia_origen de un tenant. Usado para reclasificar tenants
    legacy (ej: test_arnaldo que era 'lovbot' por default debe ser 'arnaldo')."""
    if not _available():
        return False
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE waba_clients
            SET agencia_origen = %s, updated_at = NOW()
            WHERE phone_number_id = %s
        """, (nueva_agencia, phone_number_id))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        if ok:
            print(f"[DB] agencia_origen actualizada: phone_id={phone_number_id} -> {nueva_agencia}")
        return ok
    except Exception as e:
        print(f"[DB] Error actualizar_agencia_origen: {e}")
        return False


def eliminar_waba_client(phone_number_id: str) -> bool:
    """Elimina un cliente WABA por phone_number_id. Solo para limpieza/testing."""
    if not _available():
        return False
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM waba_clients WHERE phone_number_id = %s", (phone_number_id,))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        if ok:
            print(f"[DB] waba_client eliminado: phone_id={phone_number_id}")
        return ok
    except Exception as e:
        print(f"[DB] Error eliminar_waba_client: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# META COMPLIANCE LOGS — deauthorize + data_deletion (GDPR/LGPD)
# ═══════════════════════════════════════════════════════════════════════════════

def setup_meta_compliance_logs_table() -> bool:
    """Crea tabla meta_compliance_logs si no existe. Idempotente."""
    if not _available():
        return False
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meta_compliance_logs (
                id              SERIAL PRIMARY KEY,
                event_type      VARCHAR(32) NOT NULL,
                user_id         VARCHAR(64),
                algorithm       VARCHAR(32),
                issued_at       BIGINT,
                signature_valid BOOLEAN NOT NULL,
                raw_payload     JSONB,
                client_slug     VARCHAR(128),
                action_taken    TEXT,
                confirmation_code VARCHAR(64),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_meta_compliance_user ON meta_compliance_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_meta_compliance_type ON meta_compliance_logs(event_type);
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("[DB] meta_compliance_logs: tabla OK")
        return True
    except Exception as e:
        print(f"[DB] Error setup_meta_compliance_logs_table: {e}")
        return False


def log_meta_compliance_event(
    event_type: str,
    user_id: str | None,
    algorithm: str | None,
    issued_at: int | None,
    signature_valid: bool,
    raw_payload: dict,
    client_slug: str | None,
    action_taken: str,
    confirmation_code: str | None,
) -> int | None:
    """Registra evento de compliance (deauthorize/data_deletion). Retorna id del row."""
    if not _available():
        return None
    try:
        import json as _json
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO meta_compliance_logs
            (event_type, user_id, algorithm, issued_at, signature_valid,
             raw_payload, client_slug, action_taken, confirmation_code)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            RETURNING id
        """, (
            event_type,
            user_id,
            algorithm,
            issued_at,
            signature_valid,
            _json.dumps(raw_payload or {}),
            client_slug,
            action_taken,
            confirmation_code,
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return new_id
    except Exception as e:
        print(f"[DB] Error log_meta_compliance_event: {e}")
        return None


def marcar_waba_revoked_por_user(user_id: str) -> list[str]:
    """
    Marca como revoked todos los waba_clients que tienen ese user_id asociado.
    Retorna lista de client_slugs afectados. No borra datos — solo marca estado.
    El borrado físico lo hace data_deletion.
    """
    if not _available():
        return []
    try:
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            UPDATE waba_clients
            SET webhook_subscrito = FALSE, updated_at = NOW()
            WHERE meta_user_id = %s
            RETURNING client_slug
        """, (user_id,))
        rows = cur.fetchall()
        conn.commit()
        cur.close()
        conn.close()
        return [r["client_slug"] for r in rows]
    except Exception as e:
        # Si la columna meta_user_id no existe todavía, devolver vacío sin romper.
        print(f"[DB] Error marcar_waba_revoked_por_user: {e}")
        return []


def eliminar_datos_por_user(user_id: str) -> dict:
    """
    Borra físicamente los datos asociados a un user_id de Meta.
    Retorna resumen de lo borrado. Si meta_user_id no existe como columna,
    solo retorna 0 y registra el evento igual (compliance por log).
    """
    if not _available():
        return {"waba_clients_eliminados": 0, "error": "DB no disponible"}
    deleted = {"waba_clients_eliminados": 0}
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM waba_clients WHERE meta_user_id = %s",
            (user_id,),
        )
        deleted["waba_clients_eliminados"] = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Error eliminar_datos_por_user: {e}")
        deleted["error"] = str(e)
    return deleted
