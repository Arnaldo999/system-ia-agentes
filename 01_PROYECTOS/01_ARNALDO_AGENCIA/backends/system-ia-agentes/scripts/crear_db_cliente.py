"""
Crear DB PostgreSQL dedicada para un cliente inmobiliario
==========================================================
Crea una DB nueva en el PostgreSQL de Lovbot (Hetzner) para un cliente
específico. Cada cliente tiene su propia DB (como Airtable: cada cliente
su propia base), con las mismas tablas del CRM completo.

Uso (CLI):
    python crear_db_cliente.py --db robert_crm [--from-tenant robert]

Parámetros:
    --db          Nombre de la DB nueva (ej: robert_crm, maria_crm)
    --from-tenant Slug del tenant en lovbot_crm para copiar datos (opcional)

Flujo:
    1. Conecta a PostgreSQL como superuser
    2. CREATE DATABASE <db>
    3. Aplica setup_postgres_crm_completo (tablas, índices, triggers)
    4. Si --from-tenant: copia datos de lovbot_crm WHERE tenant_slug=X
"""

import os
import sys
import argparse
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PG_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "9C7i82bFVoscycGCF6f7XPbZyNpWvEXa")

# SQL de tablas base (leads, propiedades, clientes_activos) + triggers
# Replica el contenido de setup_postgres_lovbot.py + setup_postgres_crm_completo.py
SCHEMA_BASE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL DEFAULT 'demo',
    telefono VARCHAR(20) NOT NULL,
    nombre VARCHAR(100), apellido VARCHAR(100), email VARCHAR(150),
    ciudad VARCHAR(100), operacion VARCHAR(20), tipo_propiedad VARCHAR(50),
    zona VARCHAR(100), presupuesto VARCHAR(30),
    score VARCHAR(15), score_numerico INTEGER DEFAULT 0,
    estado VARCHAR(30) DEFAULT 'no_contactado',
    sub_nicho VARCHAR(50), notas_bot TEXT,
    fuente VARCHAR(50) DEFAULT 'whatsapp_directo',
    fuente_detalle VARCHAR(200),
    propiedad_interes VARCHAR(200),
    fecha_whatsapp DATE, fecha_cita DATE,
    fecha_ultimo_contacto TIMESTAMP,
    llego_whatsapp BOOLEAN DEFAULT TRUE,
    estado_seguimiento VARCHAR(20) DEFAULT 'pendiente',
    cantidad_seguimientos INTEGER DEFAULT 0,
    proximo_seguimiento DATE,
    ultimo_contacto_bot TIMESTAMP,
    asesor_asignado VARCHAR(100),
    tipo_cliente VARCHAR(30),
    propiedad_interes_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_slug, telefono)
);
CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_leads_telefono ON leads(telefono);
CREATE INDEX IF NOT EXISTS idx_leads_estado ON leads(tenant_slug, estado);
CREATE INDEX IF NOT EXISTS idx_leads_seguimiento ON leads(estado_seguimiento, proximo_seguimiento);

CREATE TABLE IF NOT EXISTS propiedades (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL DEFAULT 'demo',
    titulo VARCHAR(200), descripcion TEXT,
    tipo VARCHAR(50), operacion VARCHAR(20),
    zona VARCHAR(100), precio DECIMAL(15, 2), moneda VARCHAR(5) DEFAULT 'USD',
    presupuesto VARCHAR(30), disponible VARCHAR(30) DEFAULT '✅ Disponible',
    dormitorios INTEGER, banios INTEGER,
    metros_cubiertos DECIMAL(10, 2), metros_terreno DECIMAL(10, 2),
    imagen_url TEXT, maps_url TEXT, direccion VARCHAR(200),
    propietario_nombre VARCHAR(150), propietario_telefono VARCHAR(30),
    propietario_email VARCHAR(150), comision_pct DECIMAL(5,2),
    tipo_cartera VARCHAR(30) DEFAULT 'propia',
    asesor_asignado VARCHAR(100), loteo VARCHAR(100), numero_lote VARCHAR(20),
    propietario_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_props_tenant ON propiedades(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_props_tipo ON propiedades(tenant_slug, tipo);
CREATE INDEX IF NOT EXISTS idx_props_zona ON propiedades(tenant_slug, zona);

CREATE TABLE IF NOT EXISTS clientes_activos (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL DEFAULT 'demo',
    nombre VARCHAR(100), apellido VARCHAR(100),
    telefono VARCHAR(20), email VARCHAR(150),
    propiedad VARCHAR(200), estado_pago VARCHAR(30) DEFAULT 'al_dia',
    monto_cuota DECIMAL(12, 2),
    cuotas_pagadas INTEGER DEFAULT 0, cuotas_total INTEGER DEFAULT 0,
    proximo_vencimiento DATE, notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_activos_tenant ON clientes_activos(tenant_slug);

CREATE TABLE IF NOT EXISTS asesores (
    id SERIAL PRIMARY KEY, tenant_slug VARCHAR(50) NOT NULL,
    nombre VARCHAR(100) NOT NULL, apellido VARCHAR(100),
    email VARCHAR(150), telefono VARCHAR(30), foto_url TEXT,
    rol VARCHAR(50) DEFAULT 'asesor', comision_pct DECIMAL(5,2),
    activo BOOLEAN DEFAULT TRUE, notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_slug, email)
);
CREATE INDEX IF NOT EXISTS idx_asesores_tenant ON asesores(tenant_slug);

CREATE TABLE IF NOT EXISTS propietarios (
    id SERIAL PRIMARY KEY, tenant_slug VARCHAR(50) NOT NULL,
    nombre VARCHAR(150) NOT NULL, telefono VARCHAR(30),
    email VARCHAR(150), dni_cuit VARCHAR(30), direccion VARCHAR(200),
    comision_pactada DECIMAL(5,2), cantidad_propiedades INTEGER DEFAULT 0,
    notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_propietarios_tenant ON propietarios(tenant_slug);

CREATE TABLE IF NOT EXISTS loteos (
    id SERIAL PRIMARY KEY, tenant_slug VARCHAR(50) NOT NULL,
    nombre VARCHAR(100) NOT NULL, slug VARCHAR(50) NOT NULL,
    descripcion TEXT, ubicacion VARCHAR(200), ciudad VARCHAR(100),
    mapa_svg_url TEXT,
    total_lotes INTEGER DEFAULT 0, lotes_disponibles INTEGER DEFAULT 0,
    lotes_reservados INTEGER DEFAULT 0, lotes_vendidos INTEGER DEFAULT 0,
    precio_desde DECIMAL(15,2), moneda VARCHAR(5) DEFAULT 'USD',
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_slug, slug)
);
CREATE INDEX IF NOT EXISTS idx_loteos_tenant ON loteos(tenant_slug);

CREATE TABLE IF NOT EXISTS lotes_mapa (
    id SERIAL PRIMARY KEY, tenant_slug VARCHAR(50) NOT NULL,
    loteo_id INTEGER REFERENCES loteos(id) ON DELETE CASCADE,
    numero_lote VARCHAR(20) NOT NULL, manzana VARCHAR(20),
    estado VARCHAR(20) DEFAULT 'disponible',
    coord_x DECIMAL(8,2), coord_y DECIMAL(8,2),
    precio DECIMAL(15,2),
    propiedad_id INTEGER REFERENCES propiedades(id) ON DELETE SET NULL,
    cliente_id INTEGER REFERENCES clientes_activos(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_slug, loteo_id, numero_lote)
);
CREATE INDEX IF NOT EXISTS idx_lotes_mapa_loteo ON lotes_mapa(loteo_id);

CREATE TABLE IF NOT EXISTS contratos (
    id SERIAL PRIMARY KEY, tenant_slug VARCHAR(50) NOT NULL,
    tipo VARCHAR(30) NOT NULL, titulo VARCHAR(200),
    lead_id INTEGER,
    propiedad_id INTEGER REFERENCES propiedades(id) ON DELETE SET NULL,
    cliente_activo_id INTEGER REFERENCES clientes_activos(id) ON DELETE SET NULL,
    asesor_id INTEGER REFERENCES asesores(id) ON DELETE SET NULL,
    archivo_url TEXT,
    monto DECIMAL(15,2), moneda VARCHAR(5) DEFAULT 'USD',
    fecha_firma DATE, fecha_vencimiento DATE,
    estado VARCHAR(30) DEFAULT 'pendiente', notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_contratos_tenant ON contratos(tenant_slug);

CREATE TABLE IF NOT EXISTS visitas (
    id SERIAL PRIMARY KEY, tenant_slug VARCHAR(50) NOT NULL,
    lead_id INTEGER,
    propiedad_id INTEGER REFERENCES propiedades(id) ON DELETE SET NULL,
    asesor_id INTEGER REFERENCES asesores(id) ON DELETE SET NULL,
    fecha_visita TIMESTAMP NOT NULL,
    duracion_minutos INTEGER DEFAULT 60,
    estado VARCHAR(30) DEFAULT 'agendada',
    calcom_booking_id VARCHAR(100),
    notas_pre TEXT, notas_post TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_visitas_tenant ON visitas(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_visitas_fecha ON visitas(tenant_slug, fecha_visita);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_leads_updated') THEN
        CREATE TRIGGER trg_leads_updated BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_props_updated') THEN
        CREATE TRIGGER trg_props_updated BEFORE UPDATE ON propiedades FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_activos_updated') THEN
        CREATE TRIGGER trg_activos_updated BEFORE UPDATE ON clientes_activos FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_asesores_updated') THEN
        CREATE TRIGGER trg_asesores_updated BEFORE UPDATE ON asesores FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_propietarios_updated') THEN
        CREATE TRIGGER trg_propietarios_updated BEFORE UPDATE ON propietarios FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_loteos_updated') THEN
        CREATE TRIGGER trg_loteos_updated BEFORE UPDATE ON loteos FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_lotes_mapa_updated') THEN
        CREATE TRIGGER trg_lotes_mapa_updated BEFORE UPDATE ON lotes_mapa FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_contratos_updated') THEN
        CREATE TRIGGER trg_contratos_updated BEFORE UPDATE ON contratos FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_visitas_updated') THEN
        CREATE TRIGGER trg_visitas_updated BEFORE UPDATE ON visitas FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;
"""

TABLAS_COPIABLES = [
    "leads", "propiedades", "clientes_activos",
    "asesores", "propietarios", "loteos", "lotes_mapa",
    "contratos", "visitas"
]


def crear_db(db_nombre: str) -> dict:
    """Crea la DB si no existe. Conecta a 'postgres' (DB admin default)."""
    print(f"[crear_db] Conectando a PostgreSQL admin...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname="postgres",
                            user=PG_USER, password=PG_PASS)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db_nombre,))
    existe = cur.fetchone() is not None

    if existe:
        print(f"[crear_db] DB '{db_nombre}' ya existe — skip CREATE")
    else:
        print(f"[crear_db] Creando DB '{db_nombre}'...")
        cur.execute(f'CREATE DATABASE "{db_nombre}"')
        print(f"[crear_db] ✅ DB '{db_nombre}' creada")

    cur.close()
    conn.close()
    return {"db": db_nombre, "existia": existe}


def aplicar_schema(db_nombre: str) -> dict:
    """Aplica el schema completo en la DB indicada."""
    print(f"[schema] Conectando a {db_nombre}...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db_nombre,
                            user=PG_USER, password=PG_PASS)
    conn.autocommit = True
    cur = conn.cursor()

    print(f"[schema] Aplicando schema...")
    cur.execute(SCHEMA_BASE_SQL)

    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    tablas = [r[0] for r in cur.fetchall()]
    print(f"[schema] ✅ Tablas en {db_nombre}: {tablas}")

    cur.close()
    conn.close()
    return {"tablas": tablas}


def copiar_datos(db_origen: str, db_destino: str, tenant_slug: str) -> dict:
    """Copia todos los datos de tenant_slug desde db_origen → db_destino."""
    print(f"[copiar] Copiando datos de tenant '{tenant_slug}': {db_origen} → {db_destino}")

    src = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db_origen,
                          user=PG_USER, password=PG_PASS)
    dst = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db_destino,
                          user=PG_USER, password=PG_PASS)
    dst.autocommit = True

    resumen = {}

    for tabla in TABLAS_COPIABLES:
        try:
            src_cur = src.cursor()
            src_cur.execute(f"SELECT * FROM {tabla} WHERE tenant_slug=%s", (tenant_slug,))
            rows = src_cur.fetchall()

            if not rows:
                resumen[tabla] = 0
                src_cur.close()
                continue

            # Columnas
            cols = [d[0] for d in src_cur.description]
            # Excluir 'id' para que PostgreSQL genere uno nuevo (evitar conflictos)
            cols_sin_id = [c for c in cols if c != "id"]
            idx_sin_id = [cols.index(c) for c in cols_sin_id]

            placeholders = ", ".join(["%s"] * len(cols_sin_id))
            cols_str = ", ".join(cols_sin_id)

            dst_cur = dst.cursor()
            insertados = 0
            errores = 0
            for row in rows:
                values = tuple(row[i] for i in idx_sin_id)
                try:
                    dst_cur.execute(
                        f"INSERT INTO {tabla} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                        values
                    )
                    insertados += dst_cur.rowcount
                except Exception as e:
                    errores += 1
                    print(f"[copiar] Error row {tabla}: {e}")

            print(f"[copiar]   {tabla}: {insertados}/{len(rows)} copiados ({errores} errores)")
            resumen[tabla] = insertados
            dst_cur.close()
            src_cur.close()
        except Exception as e:
            print(f"[copiar] Error tabla {tabla}: {e}")
            resumen[tabla] = f"error: {e}"

    src.close()
    dst.close()
    print(f"[copiar] ✅ Resumen: {resumen}")
    return resumen


def crear_db_cliente(db_nombre: str, copiar_desde_tenant: str = None, db_origen: str = "lovbot_crm") -> dict:
    """
    Flujo completo:
    1. Crear DB si no existe
    2. Aplicar schema
    3. Opcionalmente, copiar datos desde db_origen WHERE tenant_slug=X
    """
    print(f"\n════════════════════════════════════════════════════════════════")
    print(f"  Crear DB cliente: {db_nombre}")
    if copiar_desde_tenant:
        print(f"  Copiar datos de tenant: {copiar_desde_tenant}")
        print(f"  DB origen: {db_origen}")
    print(f"════════════════════════════════════════════════════════════════\n")

    resultado = {"db": db_nombre, "db_origen": db_origen if copiar_desde_tenant else None}

    # Paso 1: crear DB
    r1 = crear_db(db_nombre)
    resultado["crear"] = r1

    # Paso 2: aplicar schema
    r2 = aplicar_schema(db_nombre)
    resultado["schema"] = r2

    # Paso 3: copiar datos (opcional)
    if copiar_desde_tenant:
        r3 = copiar_datos(db_origen, db_nombre, copiar_desde_tenant)
        resultado["copia"] = r3

    print(f"\n✅ Completado: {db_nombre}")
    return resultado


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Nombre de la DB nueva (ej: robert_crm)")
    ap.add_argument("--from-tenant", default=None, help="Slug del tenant a copiar desde lovbot_crm")
    args = ap.parse_args()

    crear_db_cliente(args.db, args.from_tenant)
