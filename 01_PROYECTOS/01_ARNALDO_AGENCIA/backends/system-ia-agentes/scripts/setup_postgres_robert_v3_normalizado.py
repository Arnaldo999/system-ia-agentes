"""
Setup PostgreSQL — Robert CRM v3 Normalizado
=============================================
Agrega columnas a clientes_activos y crea las tablas nuevas para el
modelo de contratos polimorficos y gestion de agencia (alquiler).

Tablas y columnas nuevas:
  - clientes_activos: documento, lead_id, origen_creacion, fecha_alta
  - contratos: modelo polimorfigo completo (item_tipo/item_id + cuotas)
  - inmuebles_renta, inquilinos, pagos_alquiler, liquidaciones

IMPORTANTE:
  - Idempotente: usar IF NOT EXISTS / ADD COLUMN IF NOT EXISTS en todo.
  - La tabla contratos ya existe con estructura simplificada — se extiende
    agregando columnas nuevas. Las columnas existentes (tipo, titulo, monto,
    fecha_firma, archivo_url, estado, notas, etc.) se conservan intactas.
  - NO se borra nada. Los datos legacy quedan en pie.

Uso:
  python setup_postgres_robert_v3_normalizado.py

Variables de entorno leidas (mismo .env del backend):
  LOVBOT_PG_HOST, LOVBOT_PG_PORT, LOVBOT_PG_DB, LOVBOT_PG_USER, LOVBOT_PG_PASS
"""

import os
import re
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env del backend si existe
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

DB_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc")
DB_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
DB_NAME = os.environ.get("LOVBOT_PG_DB", "lovbot_crm_modelo")
DB_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
DB_PASS = os.environ.get("LOVBOT_PG_PASS", "")


MIGRACION_SQL = """

-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 0 — Garantizar columnas base en tablas legacy de produccion
--           (robert_crm puede haber sido creada antes de que estas columnas
--            existieran en el schema. IF NOT EXISTS hace esto idempotente.)
-- ═══════════════════════════════════════════════════════════════════════════

-- clientes_activos: en produccion legacy puede no tener tenant_slug
ALTER TABLE clientes_activos ADD COLUMN IF NOT EXISTS tenant_slug VARCHAR(50) DEFAULT 'robert';

-- contratos: en produccion legacy puede no tener tenant_slug ni cliente_activo_id
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS tenant_slug VARCHAR(50) DEFAULT 'robert';
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS cliente_activo_id INTEGER REFERENCES clientes_activos(id) ON DELETE SET NULL;

-- inmuebles_renta, inquilinos, pagos_alquiler, liquidaciones:
-- si fueron creadas por ampliar-schema-agencia (sin tenant_slug) hay que agregarlo
-- antes de que los indices de la PARTE 3-6 intenten usarlo.
-- Usamos DO $$ para proteger el ALTER con EXISTS check (no hay ALTER TABLE IF EXISTS en PG).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='inmuebles_renta') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='inmuebles_renta' AND column_name='tenant_slug') THEN
            ALTER TABLE inmuebles_renta ADD COLUMN tenant_slug VARCHAR(50) DEFAULT 'demo';
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='inquilinos') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='inquilinos' AND column_name='tenant_slug') THEN
            ALTER TABLE inquilinos ADD COLUMN tenant_slug VARCHAR(50) DEFAULT 'demo';
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='pagos_alquiler') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='pagos_alquiler' AND column_name='tenant_slug') THEN
            ALTER TABLE pagos_alquiler ADD COLUMN tenant_slug VARCHAR(50) DEFAULT 'demo';
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='liquidaciones') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='liquidaciones' AND column_name='tenant_slug') THEN
            ALTER TABLE liquidaciones ADD COLUMN tenant_slug VARCHAR(50) DEFAULT 'demo';
        END IF;
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 1 — Extender clientes_activos con trazabilidad y documento
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE clientes_activos ADD COLUMN IF NOT EXISTS documento VARCHAR(30);
ALTER TABLE clientes_activos ADD COLUMN IF NOT EXISTS lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL;
ALTER TABLE clientes_activos ADD COLUMN IF NOT EXISTS origen_creacion VARCHAR(30) DEFAULT 'manual_directo';
ALTER TABLE clientes_activos ADD COLUMN IF NOT EXISTS fecha_alta DATE DEFAULT CURRENT_DATE;


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 2 — Extender tabla contratos (ya existe) con campos polimorficos
--           y de cuotas. Se agregan solo las columnas faltantes.
-- ═══════════════════════════════════════════════════════════════════════════

-- Relacion poliformica: que item es el contrato
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS item_tipo VARCHAR(30);
-- item_tipo valores: lote | propiedad | inmueble_renta
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS item_id INTEGER;

-- Campos de cuotas / financiacion
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS cuotas_total INTEGER DEFAULT 0;
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS cuotas_pagadas INTEGER DEFAULT 0;
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS monto_cuota DECIMAL(15,2);
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS proximo_vencimiento DATE;
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS estado_pago VARCHAR(30) DEFAULT 'al_dia';
-- estado_pago: al_dia | atrasado | cancelado | finalizado

-- Moneda (puede no existir en la tabla vieja — la tabla tiene "moneda" en la
-- definicion original; se deja el IF NOT EXISTS por seguridad)
ALTER TABLE contratos ADD COLUMN IF NOT EXISTS moneda VARCHAR(5) DEFAULT 'USD';

-- Indices de clientes_activos — van despues de TODOS los ALTER de esa tabla
-- (garantiza que tenant_slug y origen_creacion ya existen antes de indexar)
CREATE INDEX IF NOT EXISTS idx_clientes_activos_tenant ON clientes_activos(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_clientes_activos_lead_id ON clientes_activos(lead_id);
CREATE INDEX IF NOT EXISTS idx_clientes_activos_origen ON clientes_activos(tenant_slug, origen_creacion);

-- Indices de contratos — van despues de TODOS los ALTER de esa tabla
-- (garantiza que tenant_slug, estado_pago, item_tipo, item_id ya existen)
CREATE INDEX IF NOT EXISTS idx_contratos_cliente ON contratos(cliente_activo_id);
CREATE INDEX IF NOT EXISTS idx_contratos_item ON contratos(item_tipo, item_id);
CREATE INDEX IF NOT EXISTS idx_contratos_estado_pago ON contratos(tenant_slug, estado_pago);
CREATE INDEX IF NOT EXISTS idx_contratos_vencimiento ON contratos(proximo_vencimiento);


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 3 — INMUEBLES_RENTA (subnicho agencia: propiedades para alquilar)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inmuebles_renta (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,

    titulo VARCHAR(200) NOT NULL,
    tipo VARCHAR(50),           -- depto, casa, local, oficina, ph, otro
    zona VARCHAR(100),
    direccion VARCHAR(250),
    descripcion TEXT,

    propietario_id INTEGER REFERENCES propietarios(id) ON DELETE SET NULL,

    precio_alquiler DECIMAL(15,2),
    expensas DECIMAL(15,2),
    moneda VARCHAR(5) DEFAULT 'ARS',

    ambientes INTEGER,
    dormitorios INTEGER,
    banios INTEGER,
    metros_cubiertos DECIMAL(8,2),
    metros_totales DECIMAL(8,2),

    disponible BOOLEAN DEFAULT TRUE,
    fecha_disponibilidad DATE,

    imagen_url TEXT,
    maps_url TEXT,
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inmuebles_renta_tenant ON inmuebles_renta(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_inmuebles_renta_disponible ON inmuebles_renta(tenant_slug, disponible);
CREATE INDEX IF NOT EXISTS idx_inmuebles_renta_propietario ON inmuebles_renta(propietario_id);


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 4 — INQUILINOS (personas que alquilan un inmueble_renta)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inquilinos (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,

    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100),
    telefono VARCHAR(30),
    email VARCHAR(150),
    documento VARCHAR(30),

    inmueble_renta_id INTEGER REFERENCES inmuebles_renta(id) ON DELETE SET NULL,

    fecha_inicio_contrato DATE,
    fecha_fin_contrato DATE,
    monto_alquiler_actual DECIMAL(15,2),

    estado VARCHAR(30) DEFAULT 'activo',    -- activo, deuda, finalizado
    garante_nombre VARCHAR(200),
    garante_telefono VARCHAR(30),
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inquilinos_tenant ON inquilinos(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_inquilinos_inmueble ON inquilinos(inmueble_renta_id);
CREATE INDEX IF NOT EXISTS idx_inquilinos_estado ON inquilinos(tenant_slug, estado);
CREATE INDEX IF NOT EXISTS idx_inquilinos_telefono ON inquilinos(telefono);


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 5 — PAGOS_ALQUILER (registro mensual de cobros)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pagos_alquiler (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,

    inquilino_id INTEGER REFERENCES inquilinos(id) ON DELETE CASCADE,
    inmueble_renta_id INTEGER REFERENCES inmuebles_renta(id) ON DELETE SET NULL,

    mes_anio VARCHAR(7) NOT NULL,           -- "2026-04" (YYYY-MM)
    monto DECIMAL(15,2) NOT NULL,
    fecha_pago DATE,
    fecha_vencimiento DATE,
    metodo VARCHAR(50),                     -- efectivo, transferencia, cheque, otro
    estado VARCHAR(30) DEFAULT 'pendiente', -- pagado, pendiente, atrasado
    comprobante_url TEXT,
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pagos_alquiler_tenant ON pagos_alquiler(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_pagos_alquiler_inquilino ON pagos_alquiler(inquilino_id);
CREATE INDEX IF NOT EXISTS idx_pagos_alquiler_estado ON pagos_alquiler(tenant_slug, estado);
CREATE INDEX IF NOT EXISTS idx_pagos_alquiler_mes ON pagos_alquiler(mes_anio);


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 6 — LIQUIDACIONES (rendicion mensual a propietarios)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS liquidaciones (
    id SERIAL PRIMARY KEY,
    tenant_slug VARCHAR(50) NOT NULL,

    propietario_id INTEGER REFERENCES propietarios(id) ON DELETE SET NULL,
    inmueble_renta_id INTEGER REFERENCES inmuebles_renta(id) ON DELETE SET NULL,

    mes_anio VARCHAR(7) NOT NULL,           -- "2026-04" (YYYY-MM)
    bruto DECIMAL(15,2),                    -- lo que cobro el inquilino
    comision_agencia DECIMAL(15,2),         -- parte de la agencia
    neto_propietario DECIMAL(15,2),         -- lo que le toca al dueno
    fecha_liquidacion DATE,
    estado VARCHAR(30) DEFAULT 'pendiente', -- pendiente, liquidado, en_disputa
    comprobante_url TEXT,
    notas TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_liquidaciones_tenant ON liquidaciones(tenant_slug);
CREATE INDEX IF NOT EXISTS idx_liquidaciones_propietario ON liquidaciones(propietario_id);
CREATE INDEX IF NOT EXISTS idx_liquidaciones_estado ON liquidaciones(tenant_slug, estado);
CREATE INDEX IF NOT EXISTS idx_liquidaciones_mes ON liquidaciones(mes_anio);


-- ═══════════════════════════════════════════════════════════════════════════
-- PARTE 7 — Triggers updated_at para las tablas nuevas
-- ═══════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_inmuebles_renta_updated') THEN
        CREATE TRIGGER trg_inmuebles_renta_updated
        BEFORE UPDATE ON inmuebles_renta
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_inquilinos_updated') THEN
        CREATE TRIGGER trg_inquilinos_updated
        BEFORE UPDATE ON inquilinos
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_pagos_alquiler_updated') THEN
        CREATE TRIGGER trg_pagos_alquiler_updated
        BEFORE UPDATE ON pagos_alquiler
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_liquidaciones_updated') THEN
        CREATE TRIGGER trg_liquidaciones_updated
        BEFORE UPDATE ON liquidaciones
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

"""


MIGRACION_CONTRATOS_LEGACY_SQL = """
-- Este bloque se ejecuta separado, como funcion (ver abajo).
-- Se hace via Python para poder loguear cada fila procesada.
"""


def _conn(db_name=None):
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=db_name or DB_NAME,
        user=DB_USER, password=DB_PASS,
        connect_timeout=10,
    )


def migrar_contratos_legacy(conn):
    """
    Para cada cliente activo con campo 'propiedad' tipo 'San Ignacio · L-5':
    1. Parsea nombre_loteo + numero_lote
    2. Busca en lotes_mapa el match
    3. Crea registro en contratos con tipo='venta_lote', item_tipo='lote'
    4. Deja el campo propiedad intacto (backward compat)
    5. Loguea si no matchea — NO falla
    """
    print("\n[migrar_legacy] Iniciando migracion de contratos desde campo propiedad...")
    cur = conn.cursor()

    # Obtener todos los clientes_activos con campo propiedad no nulo
    cur.execute("""
        SELECT ca.id, ca.tenant_slug, ca.nombre, ca.apellido, ca.propiedad,
               ca.estado_pago, ca.monto_cuota, ca.cuotas_pagadas, ca.cuotas_total,
               ca.proximo_vencimiento
        FROM clientes_activos ca
        WHERE ca.propiedad IS NOT NULL AND ca.propiedad != ''
    """)
    clientes = cur.fetchall()
    print(f"[migrar_legacy] {len(clientes)} clientes con propiedad no nula")

    creados = 0
    skipped = 0

    for row in clientes:
        (ca_id, tenant_slug, nombre, apellido, propiedad_str,
         estado_pago, monto_cuota, cuotas_pagadas, cuotas_total, proximo_venc) = row

        # Verificar si ya tiene contrato asociado (no duplicar)
        cur.execute(
            "SELECT id FROM contratos WHERE cliente_activo_id=%s AND tenant_slug=%s AND item_tipo='lote'",
            (ca_id, tenant_slug)
        )
        if cur.fetchone():
            print(f"  [skip] cliente_activo #{ca_id} ya tiene contrato de lote — omitiendo")
            skipped += 1
            continue

        # Intentar parsear "Nombre Loteo · L-5" o "Nombre Loteo · Mz2-L5"
        # El separador es ' · ' (punto medio unicode) o ' - ' o solo espacio
        # Estrategia: todo antes de '·' es el loteo, despues es el numero
        match_unicode = re.match(r'^(.+?)\s*[·•\-]{1}\s*(.+)$', propiedad_str.strip())
        if not match_unicode:
            print(f"  [LOG] No se pudo parsear propiedad '{propiedad_str}' para cliente #{ca_id}")
            skipped += 1
            continue

        nombre_loteo = match_unicode.group(1).strip()
        numero_lote = match_unicode.group(2).strip()

        # Buscar loteo por nombre (ILIKE)
        cur.execute(
            "SELECT id FROM loteos WHERE tenant_slug=%s AND nombre ILIKE %s LIMIT 1",
            (tenant_slug, f"%{nombre_loteo}%")
        )
        loteo_row = cur.fetchone()

        lote_id = None
        loteo_id = None
        if loteo_row:
            loteo_id = loteo_row[0]
            # Buscar lote por numero_lote dentro del loteo
            cur.execute(
                "SELECT id FROM lotes_mapa WHERE tenant_slug=%s AND loteo_id=%s AND numero_lote ILIKE %s LIMIT 1",
                (tenant_slug, loteo_id, f"%{numero_lote}%")
            )
            lote_row = cur.fetchone()
            if lote_row:
                lote_id = lote_row[0]

        if not lote_id:
            print(f"  [LOG] Sin match en lotes_mapa para '{propiedad_str}' (cliente #{ca_id}) — loteo='{nombre_loteo}', lote='{numero_lote}'")
            skipped += 1
            continue

        # Crear contrato
        cur.execute("""
            INSERT INTO contratos (
                tenant_slug, cliente_activo_id,
                tipo, item_tipo, item_id,
                estado_pago, monto_cuota, cuotas_pagadas, cuotas_total,
                proximo_vencimiento, estado,
                notas,
                created_at, updated_at
            ) VALUES (
                %s, %s,
                'venta_lote', 'lote', %s,
                %s, %s, %s, %s,
                %s, 'firmado',
                'Migrado automaticamente desde campo propiedad legacy',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """, (
            tenant_slug, ca_id,
            lote_id,
            estado_pago or 'al_dia',
            monto_cuota,
            cuotas_pagadas or 0,
            cuotas_total or 0,
            proximo_venc,
        ))
        print(f"  [OK] Contrato creado para cliente #{ca_id} ({nombre} {apellido}) → lote_id={lote_id} ('{propiedad_str}')")
        creados += 1

    conn.commit()
    cur.close()
    print(f"\n[migrar_legacy] Resultado: {creados} contratos creados, {skipped} omitidos")
    return {"creados": creados, "skipped": skipped}


def setup():
    print(f"[setup] Conectando a PostgreSQL {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    try:
        conn = _conn()
        conn.autocommit = True
        cur = conn.cursor()

        print("[setup] Aplicando migracion v3 normalizado...")
        cur.execute(MIGRACION_SQL)
        print("[setup] Migracion DDL completada")

        # Verificar tablas
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' ORDER BY table_name
        """)
        tablas = [r[0] for r in cur.fetchall()]
        print(f"\n[setup] Tablas en DB: {tablas}")

        # Verificar columnas nuevas en clientes_activos
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='clientes_activos'
            ORDER BY ordinal_position
        """)
        cols = [r[0] for r in cur.fetchall()]
        print(f"\n[setup] Columnas clientes_activos: {cols}")

        # Verificar columnas nuevas en contratos
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='contratos'
            ORDER BY ordinal_position
        """)
        cols_contratos = [r[0] for r in cur.fetchall()]
        print(f"\n[setup] Columnas contratos: {cols_contratos}")

        cur.close()

        # Ejecutar migracion de datos legacy
        conn.autocommit = False
        resultado = migrar_contratos_legacy(conn)

        conn.close()
        print("\n[setup] Migracion v3 completada exitosamente")
        return {
            "ok": True,
            "tablas": tablas,
            "contratos_migrados": resultado,
        }

    except Exception as e:
        import traceback
        print(f"[setup] ERROR: {e}")
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    # Permitir pasar DB como argumento: python setup... lovbot_crm_modelo
    if len(sys.argv) > 1:
        DB_NAME = sys.argv[1]
        print(f"[setup] Usando DB: {DB_NAME}")
    resultado = setup()
    print(f"\n[setup] Resultado final: {resultado}")
