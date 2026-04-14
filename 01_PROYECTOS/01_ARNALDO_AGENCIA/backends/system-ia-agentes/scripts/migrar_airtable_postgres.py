"""
Migrar datos de Airtable → PostgreSQL (Lovbot)
================================================
Lee leads y propiedades de Airtable y los inserta en PostgreSQL.
Ejecutar UNA SOLA VEZ para migración inicial.

Uso:
  python migrar_airtable_postgres.py
"""

import os
import json
import requests
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Airtable
AT_TOKEN = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AT_BASE  = os.environ.get("ROBERT_AIRTABLE_BASE", "appPSAVCmDgHOlRDp")
AT_LEADS = os.environ.get("ROBERT_TABLE_CLIENTES", "tblonoyIMAM5kl2ue")
AT_PROPS = os.environ.get("ROBERT_TABLE_PROPS", "tbly67z1oY8EFQoFj")
AT_ACTIVOS = os.environ.get("ROBERT_TABLE_ACTIVOS", "tblpfSE6qkGCV6e99")
AT_HEADERS = {"Authorization": f"Bearer {AT_TOKEN}"}

# PostgreSQL
PG_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-p8s8kcgckgoc484wwo4w8wck")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_DB   = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "9C7i82bFVoscycGCF6f7XPbZyNpWvEXa")

TENANT = os.environ.get("LOVBOT_TENANT_SLUG", "demo")


def at_fetch_all(table_id):
    """Fetch all records from Airtable table."""
    records = []
    offset = None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(f"https://api.airtable.com/v0/{AT_BASE}/{table_id}",
                        headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def migrate():
    print(f"[migrar] Conectando a PostgreSQL {PG_HOST}:{PG_PORT}/{PG_DB}...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
    conn.autocommit = True
    cur = conn.cursor()

    # ── Migrar Leads ─────────────────────────────────────────────────────
    print("[migrar] Leyendo leads de Airtable...")
    at_leads = at_fetch_all(AT_LEADS)
    print(f"[migrar] {len(at_leads)} leads encontrados")

    leads_ok = 0
    for rec in at_leads:
        f = rec.get("fields", {})
        tel = f.get("Telefono", "")
        if not tel:
            continue

        # Mapear score numérico a texto
        score_num = f.get("Score", 0) or 0
        if score_num >= 12:
            score_txt = "caliente"
        elif score_num >= 7:
            score_txt = "tibio"
        else:
            score_txt = "frio"

        try:
            cur.execute("""
                INSERT INTO leads (
                    tenant_slug, telefono, nombre, apellido, email, ciudad,
                    operacion, tipo_propiedad, zona, presupuesto,
                    score, score_numerico, estado, sub_nicho, notas_bot,
                    fuente, fecha_whatsapp, llego_whatsapp,
                    fecha_ultimo_contacto, fecha_cita,
                    estado_seguimiento, cantidad_seguimientos
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_slug, telefono) DO UPDATE SET
                    nombre=EXCLUDED.nombre, apellido=EXCLUDED.apellido,
                    estado=EXCLUDED.estado, score=EXCLUDED.score,
                    score_numerico=EXCLUDED.score_numerico, notas_bot=EXCLUDED.notas_bot
            """, (
                TENANT, tel,
                f.get("Nombre", ""), f.get("Apellido", ""),
                f.get("Email", ""), f.get("Ciudad", ""),
                f.get("Operacion", ""), f.get("Tipo_Propiedad", ""),
                f.get("Zona", ""), f.get("Presupuesto", ""),
                score_txt, score_num,
                f.get("Estado", "no_contactado"),
                f.get("Sub_nicho", ""), f.get("Notas_Bot", ""),
                f.get("Fuente", "whatsapp_directo"),
                f.get("Fecha_WhatsApp") or None,
                f.get("Llego_WhatsApp", True),
                f.get("fecha_ultimo_contacto") or None,
                f.get("Fecha_Cita") or None,
                f.get("Estado_Seguimiento", "pendiente"),
                f.get("Cantidad_Seguimientos", 0) or 0,
            ))
            leads_ok += 1
        except Exception as e:
            print(f"[migrar] Error lead {tel}: {e}")

    print(f"[migrar] ✅ {leads_ok}/{len(at_leads)} leads migrados")

    # ── Migrar Propiedades ───────────────────────────────────────────────
    print("[migrar] Leyendo propiedades de Airtable...")
    at_props = at_fetch_all(AT_PROPS)
    print(f"[migrar] {len(at_props)} propiedades encontradas")

    props_ok = 0
    for rec in at_props:
        f = rec.get("fields", {})

        # Imagen puede ser array (attachments) o string
        # En Airtable de Robert el campo se llama "Imagen_URL"
        img = ""
        img_field = f.get("Imagen_URL", "") or f.get("Imagen", "") or f.get("Foto", "")
        if isinstance(img_field, list) and img_field:
            # Attachments de Airtable: [{url, thumbnails, ...}]
            img = img_field[0].get("url", "") or img_field[0].get("thumbnails", {}).get("large", {}).get("url", "")
        elif isinstance(img_field, str):
            img = img_field

        # Maps URL
        maps = f.get("Google_Maps_URL", "") or f.get("Maps", "") or f.get("maps_url", "")

        try:
            cur.execute("""
                INSERT INTO propiedades (
                    tenant_slug, titulo, descripcion, tipo, operacion,
                    zona, precio, moneda, presupuesto, disponible,
                    dormitorios, banios, metros_cubiertos, metros_terreno,
                    imagen_url, maps_url, direccion
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                TENANT,
                f.get("Titulo", f.get("Nombre", "")),
                f.get("Descripcion", ""),
                f.get("Tipo", ""),
                f.get("Operacion", ""),
                f.get("Zona", ""),
                f.get("Precio") or None,
                f.get("Moneda", "USD"),
                f.get("Presupuesto", ""),
                f.get("Disponible", "✅ Disponible"),
                f.get("Dormitorios") or None,
                f.get("Banios") or None,
                f.get("Metros_Cubiertos") or None,
                f.get("Metros_Terreno") or None,
                img,
                maps,
                f.get("Direccion", ""),
            ))
            props_ok += 1
        except Exception as e:
            print(f"[migrar] Error prop: {e}")

    print(f"[migrar] ✅ {props_ok}/{len(at_props)} propiedades migradas")

    # ── Migrar Clientes Activos ──────────────────────────────────────────
    print("[migrar] Leyendo clientes activos de Airtable...")
    at_activos = at_fetch_all(AT_ACTIVOS)
    print(f"[migrar] {len(at_activos)} activos encontrados")

    activos_ok = 0
    for rec in at_activos:
        f = rec.get("fields", {})
        try:
            cur.execute("""
                INSERT INTO clientes_activos (
                    tenant_slug, nombre, apellido, telefono, email,
                    propiedad, estado_pago, monto_cuota, cuotas_pagadas,
                    cuotas_total, proximo_vencimiento, notas
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                TENANT,
                f.get("Nombre", ""),
                f.get("Apellido", ""),
                f.get("Telefono", ""),
                f.get("Email", ""),
                f.get("Propiedad", "") or f.get("Loteo", ""),
                f.get("Estado_Pago", "al_dia"),
                f.get("Monto_Cuota") or None,
                f.get("Cuotas_Pagadas") or 0,
                f.get("Cuotas_Total") or 0,
                f.get("Proximo_Vencimiento") or None,
                f.get("Notas", "") or f.get("Observaciones", ""),
            ))
            activos_ok += 1
        except Exception as e:
            print(f"[migrar] Error activo: {e}")

    print(f"[migrar] ✅ {activos_ok}/{len(at_activos)} activos migrados")

    # ── Verificar ────────────────────────────────────────────────────────
    cur.execute("SELECT count(*) FROM leads WHERE tenant_slug=%s", (TENANT,))
    print(f"[migrar] Total leads en PostgreSQL: {cur.fetchone()[0]}")

    cur.execute("SELECT count(*) FROM propiedades WHERE tenant_slug=%s", (TENANT,))
    print(f"[migrar] Total propiedades en PostgreSQL: {cur.fetchone()[0]}")

    cur.execute("SELECT count(*) FROM clientes_activos WHERE tenant_slug=%s", (TENANT,))
    print(f"[migrar] Total clientes activos en PostgreSQL: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    print("[migrar] ✅ Migración completada")


if __name__ == "__main__":
    migrate()
