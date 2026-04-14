"""
Setup PostgreSQL — CRM Completo Multi-subnicho
================================================
Agrega columnas universales y tablas nuevas para soportar los 3 subnichos:
desarrolladora, agencia, agente. Todas las columnas nuevas son OPCIONALES
— si el cliente no las usa, quedan vacías sin afectar nada.

Idempotente: se puede correr múltiples veces sin romper datos existentes.

Uso:
  python setup_postgres_crm_completo.py
"""

import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DB_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc")
DB_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
DB_NAME = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
DB_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
DB_PASS = os.environ.get("LOVBOT_PG_PASS", "9C7i82bFVoscycGCF6f7XPbZyNpWvEXa")


MIGRACION_SQL = """

-- ═══════════════════════════════════════════════════════════════════════════
-- SPRINT 1 — Campos universales en LEADS y PROPIEDADES
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE leads ADD COLUMN IF NOT EXISTS asesor_asignado VARCHAR(100);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS tipo_cliente VARCHAR(30);  -- comprador, vendedor, inversor
ALTER TABLE leads ADD COLUMN IF NOT EXISTS propiedad_interes_id INTEGER;

ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS propietario_nombre VARCHAR(150);
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS propietario_telefono VARCHAR(30);
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS propietario_email VARCHAR(150);
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS comision_pct DECIMAL(5,2);  -- ej 3.00
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS tipo_cartera VARCHAR(30) DEFAULT 'propia';  -- propia, tercero, consignacion
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS asesor_asignado VARCHAR(100);
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS loteo VARCHAR(100);  -- nombre del loteo/proyecto
ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS numero_lote VARCHAR(20);  -- ej "Mz17-Lote5"


-- ═══════════════════════════════════════════════════════════════════════════
-- SPRINT 3 — Tabla ASESORES (para agencias con equipo)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS asesores (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100),
    email VARCHAR(150),
    telefono VARCHAR(30),
    foto_url TEXT,
    rol VARCHAR(50) DEFAULT 'asesor',  -- asesor, admin, supervisor
    comision_pct DECIMAL(5,2),  -- ej 50.00 (% que le toca de la comisión)
    activo BOOLEAN DEFAULT TRUE,
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_slug, email)
);

CREATE INDEX IF NOT EXISTS idx_asesores_tenant ON asesores(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_asesores_activo ON asesores(tenant_slug, activo);


-- ═══════════════════════════════════════════════════════════════════════════
-- SPRINT 4 — Tabla PROPIETARIOS (para agencias con cartera de terceros)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS propietarios (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    telefono VARCHAR(30),
    email VARCHAR(150),
    dni_cuit VARCHAR(30),
    direccion VARCHAR(200),
    comision_pactada DECIMAL(5,2),  -- % acordado con el propietario
    cantidad_propiedades INTEGER DEFAULT 0,  -- se actualiza con trigger
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_propietarios_tenant ON propietarios(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_propietarios_telefono ON propietarios(telefono);

ALTER TABLE propiedades ADD COLUMN IF NOT EXISTS propietario_id INTEGER REFERENCES propietarios(id) ON DELETE SET NULL;


-- ═══════════════════════════════════════════════════════════════════════════
-- SPRINT 5 — Tabla LOTEOS (para desarrolladoras con mapas SVG)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS loteos (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    slug VARCHAR(50) NOT NULL,  -- "san-ignacio", "apostoles"
    descripcion TEXT,
    ubicacion VARCHAR(200),
    ciudad VARCHAR(100),
    mapa_svg_url TEXT,  -- URL Cloudinary del SVG base
    total_lotes INTEGER DEFAULT 0,
    lotes_disponibles INTEGER DEFAULT 0,
    lotes_reservados INTEGER DEFAULT 0,
    lotes_vendidos INTEGER DEFAULT 0,
    precio_desde DECIMAL(15,2),
    moneda VARCHAR(5) DEFAULT 'USD',
    activo BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_slug, slug)
);

CREATE INDEX IF NOT EXISTS idx_loteos_tenant ON loteos(tenant_slug);


-- Pins del mapa (coordenadas de cada lote sobre el SVG)
CREATE TABLE IF NOT EXISTS lotes_mapa (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,
    loteo_id INTEGER REFERENCES loteos(id) ON DELETE CASCADE,
    numero_lote VARCHAR(20) NOT NULL,  -- "Mz17-L5"
    manzana VARCHAR(20),
    estado VARCHAR(20) DEFAULT 'disponible',  -- disponible, reservado, vendido
    coord_x DECIMAL(8,2),  -- posición X sobre el SVG
    coord_y DECIMAL(8,2),  -- posición Y sobre el SVG
    precio DECIMAL(15,2),
    propiedad_id INTEGER REFERENCES propiedades(id) ON DELETE SET NULL,
    cliente_id INTEGER REFERENCES clientes_activos(id) ON DELETE SET NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_slug, loteo_id, numero_lote)
);

CREATE INDEX IF NOT EXISTS idx_lotes_mapa_loteo ON lotes_mapa(loteo_id);
CREATE INDEX IF NOT EXISTS idx_lotes_mapa_estado ON lotes_mapa(loteo_id, estado);


-- ═══════════════════════════════════════════════════════════════════════════
-- SPRINT 6 — Tabla CONTRATOS / DOCUMENTOS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS contratos (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,
    tipo VARCHAR(30) NOT NULL,  -- reserva, venta, alquiler, boleto, otro
    titulo VARCHAR(200),
    lead_id INTEGER,
    propiedad_id INTEGER REFERENCES propiedades(id) ON DELETE SET NULL,
    cliente_activo_id INTEGER REFERENCES clientes_activos(id) ON DELETE SET NULL,
    asesor_id INTEGER REFERENCES asesores(id) ON DELETE SET NULL,
    archivo_url TEXT,  -- PDF en Cloudinary
    monto DECIMAL(15,2),
    moneda VARCHAR(5) DEFAULT 'USD',
    fecha_firma DATE,
    fecha_vencimiento DATE,
    estado VARCHAR(30) DEFAULT 'pendiente',  -- pendiente, firmado, vencido, cancelado
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contratos_tenant ON contratos(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_contratos_lead ON contratos(lead_id);
CREATE INDEX IF NOT EXISTS idx_contratos_estado ON contratos(tenant_slug, estado);


-- ═══════════════════════════════════════════════════════════════════════════
-- SPRINT 8 — Tabla VISITAS / AGENDA (complementa Cal.com)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS visitas (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,
    lead_id INTEGER,
    propiedad_id INTEGER REFERENCES propiedades(id) ON DELETE SET NULL,
    asesor_id INTEGER REFERENCES asesores(id) ON DELETE SET NULL,
    fecha_visita TIMESTAMP NOT NULL,
    duracion_minutos INTEGER DEFAULT 60,
    estado VARCHAR(30) DEFAULT 'agendada',  -- agendada, realizada, cancelada, no_show
    calcom_booking_id VARCHAR(100),  -- ID de Cal.com si viene de ahí
    notas_pre TEXT,
    notas_post TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_visitas_tenant ON visitas(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_visitas_fecha ON visitas(tenant_slug, fecha_visita);
CREATE INDEX IF NOT EXISTS idx_visitas_asesor ON visitas(asesor_id);


-- ═══════════════════════════════════════════════════════════════════════════
-- TRIGGERS updated_at para tablas nuevas
-- ═══════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_asesores_updated') THEN
        CREATE TRIGGER trg_asesores_updated BEFORE UPDATE ON asesores
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_propietarios_updated') THEN
        CREATE TRIGGER trg_propietarios_updated BEFORE UPDATE ON propietarios
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_loteos_updated') THEN
        CREATE TRIGGER trg_loteos_updated BEFORE UPDATE ON loteos
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_lotes_mapa_updated') THEN
        CREATE TRIGGER trg_lotes_mapa_updated BEFORE UPDATE ON lotes_mapa
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_contratos_updated') THEN
        CREATE TRIGGER trg_contratos_updated BEFORE UPDATE ON contratos
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_visitas_updated') THEN
        CREATE TRIGGER trg_visitas_updated BEFORE UPDATE ON visitas
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

        print("[setup] Ejecutando migración CRM completo...")
        cur.execute(MIGRACION_SQL)

        # Verificar
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        tablas = [r[0] for r in cur.fetchall()]
        print(f"[setup] Tablas en PostgreSQL: {tablas}")

        for tabla in tablas:
            cur.execute(f"SELECT count(*) FROM {tabla}")
            count = cur.fetchone()[0]
            print(f"  {tabla}: {count} registros")

        cur.close()
        conn.close()
        print("[setup] ✅ Migración completada")
        return {"ok": True, "tablas": tablas}

    except Exception as e:
        print(f"[setup] ❌ ERROR: {e}")
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    setup()
