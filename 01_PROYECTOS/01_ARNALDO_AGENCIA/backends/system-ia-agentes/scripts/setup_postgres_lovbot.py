"""
Setup PostgreSQL — Lovbot CRM
==============================
Crea las tablas para el CRM inmobiliario de Robert/Lovbot.
Replica la estructura de Airtable pero en PostgreSQL.

Conexión interna (Docker): lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc:5432
Conexión externa (SSH tunnel): 5.161.235.99:5433

Uso:
  python setup_postgres_lovbot.py
"""

import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Conexión — interno Docker o externo
DB_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc")
DB_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
DB_NAME = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
DB_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
DB_PASS = os.environ.get("LOVBOT_PG_PASS", "9C7i82bFVoscycGCF6f7XPbZyNpWvEXa")

TABLAS_SQL = """

-- ── Tabla: leads (equivalente a Clientes en Airtable) ─────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL DEFAULT 'demo',
    telefono VARCHAR(20) NOT NULL,
    nombre VARCHAR(100),
    apellido VARCHAR(100),
    email VARCHAR(150),
    ciudad VARCHAR(100),
    operacion VARCHAR(20),  -- venta, alquiler
    tipo_propiedad VARCHAR(50),  -- casa, departamento, terreno, otro
    zona VARCHAR(100),
    presupuesto VARCHAR(30),  -- hata_50k, 50k_100k, 100k_200k, mas_200k
    score VARCHAR(15),  -- caliente, tibio, frio
    score_numerico INTEGER DEFAULT 0,
    estado VARCHAR(30) DEFAULT 'no_contactado',
    sub_nicho VARCHAR(50),
    notas_bot TEXT,
    fuente VARCHAR(50) DEFAULT 'whatsapp_directo',
    fuente_detalle VARCHAR(200),
    propiedad_interes VARCHAR(200),
    fecha_whatsapp DATE,
    fecha_cita DATE,
    fecha_ultimo_contacto TIMESTAMP,
    llego_whatsapp BOOLEAN DEFAULT TRUE,

    -- Seguimiento automático
    estado_seguimiento VARCHAR(20) DEFAULT 'pendiente',  -- activo, pausado, dormido, completado
    cantidad_seguimientos INTEGER DEFAULT 0,
    proximo_seguimiento DATE,
    ultimo_contacto_bot TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_slug, telefono)
);

CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_leads_telefono ON leads(telefono);
CREATE INDEX IF NOT EXISTS idx_leads_estado ON leads(tenant_slug, estado);
CREATE INDEX IF NOT EXISTS idx_leads_seguimiento ON leads(estado_seguimiento, proximo_seguimiento);


-- ── Tabla: propiedades (equivalente a Propiedades en Airtable) ────────────
CREATE TABLE IF NOT EXISTS propiedades (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL DEFAULT 'demo',
    titulo VARCHAR(200),
    descripcion TEXT,
    tipo VARCHAR(50),  -- casa, departamento, terreno, local, oficina
    operacion VARCHAR(20),  -- venta, alquiler
    zona VARCHAR(100),
    precio DECIMAL(15, 2),
    moneda VARCHAR(5) DEFAULT 'USD',
    presupuesto VARCHAR(30),  -- hata_50k, 50k_100k, etc.
    disponible VARCHAR(30) DEFAULT '✅ Disponible',
    dormitorios INTEGER,
    banios INTEGER,
    metros_cubiertos DECIMAL(10, 2),
    metros_terreno DECIMAL(10, 2),
    imagen_url TEXT,
    maps_url TEXT,
    direccion VARCHAR(200),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_props_tenant ON propiedades(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_props_tipo ON propiedades(tenant_slug, tipo);
CREATE INDEX IF NOT EXISTS idx_props_zona ON propiedades(tenant_slug, zona);
CREATE INDEX IF NOT EXISTS idx_props_disponible ON propiedades(tenant_slug, disponible);


-- ── Tabla: clientes_activos (equivalente a CLIENTES_ACTIVOS en Airtable) ──
CREATE TABLE IF NOT EXISTS clientes_activos (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL DEFAULT 'demo',
    nombre VARCHAR(100),
    apellido VARCHAR(100),
    telefono VARCHAR(20),
    email VARCHAR(150),
    propiedad VARCHAR(200),
    estado_pago VARCHAR(30) DEFAULT 'al_dia',
    monto_cuota DECIMAL(12, 2),
    cuotas_pagadas INTEGER DEFAULT 0,
    cuotas_total INTEGER DEFAULT 0,
    proximo_vencimiento DATE,
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activos_tenant ON clientes_activos(tenant_slug);


-- ── Función: updated_at automático ────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_leads_updated') THEN
        CREATE TRIGGER trg_leads_updated BEFORE UPDATE ON leads
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_props_updated') THEN
        CREATE TRIGGER trg_props_updated BEFORE UPDATE ON propiedades
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_activos_updated') THEN
        CREATE TRIGGER trg_activos_updated BEFORE UPDATE ON clientes_activos
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

"""


def setup():
    print(f"[setup] Conectando a PostgreSQL {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASS,
        )
        conn.autocommit = True
        cur = conn.cursor()

        print("[setup] Creando tablas...")
        cur.execute(TABLAS_SQL)

        # Verificar
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tablas = [r[0] for r in cur.fetchall()]
        print(f"[setup] Tablas creadas: {tablas}")

        for tabla in tablas:
            cur.execute(f"SELECT count(*) FROM {tabla}")
            count = cur.fetchone()[0]
            print(f"  {tabla}: {count} registros")

        cur.close()
        conn.close()
        print("[setup] Setup completado exitosamente")
        return {"ok": True, "tablas": tablas}

    except Exception as e:
        print(f"[setup] ERROR: {e}")
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    setup()
