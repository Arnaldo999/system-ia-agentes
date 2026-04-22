"""
Migracion: total_lotes → registros individuales en lotes_mapa
=============================================================
Para cada loteo que tenga total_lotes > 0 y 0 lotes en lotes_mapa:
  - Divide en manzanas de 8 lotes (mismo criterio del JS anterior).
  - Inserta un registro lotes_mapa por lote con estado='libre'.
  - Manzanas nombradas A, B, C... (hasta Z, despues AA, AB...)

Idempotente: si un loteo ya tiene lotes, lo omite.

Ademas agrega el UNIQUE constraint si no existe todavia.

Uso:
  python migrar_lotes_individuales.py
  (requiere env vars LOVBOT_PG_*)
"""

import os
import sys
import psycopg2

PG_HOST = os.environ.get("LOVBOT_PG_HOST", "localhost")
PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
PG_DB   = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")
TENANT  = os.environ.get("LOVBOT_TENANT_SLUG", "demo")


def _conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
        connect_timeout=10,
    )


def _nombre_manzana(idx: int) -> str:
    """0→A, 1→B ... 25→Z, 26→AA, 27→AB ..."""
    letras = []
    n = idx
    while True:
        letras.append(chr(65 + (n % 26)))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(letras))


def _dividir_en_manzanas(total: int):
    """Misma logica que el JS: manzanas de 8 (o 4/6 si total es pequeno)."""
    t = int(total)
    if t <= 0:
        return []
    lotes_por_manzana = 4 if t <= 16 else (6 if t <= 40 else 8)
    manzanas = []
    contador = 1
    while contador <= t:
        hasta = min(contador + lotes_por_manzana - 1, t)
        manzanas.append(list(range(contador, hasta + 1)))
        contador = hasta + 1
    return manzanas


def asegurar_unique_constraint(cur):
    """Agrega el UNIQUE(tenant_slug, loteo_id, numero_lote) si no existe."""
    cur.execute("""
        SELECT COUNT(*)
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'lotes_mapa'
          AND c.contype = 'u'
          AND array_to_string(
                ARRAY(SELECT a.attname FROM pg_attribute a
                      WHERE a.attrelid = c.conrelid
                        AND a.attnum = ANY(c.conkey)
                      ORDER BY a.attnum),
                ','
              ) LIKE '%tenant_slug%'
          AND array_to_string(
                ARRAY(SELECT a.attname FROM pg_attribute a
                      WHERE a.attrelid = c.conrelid
                        AND a.attnum = ANY(c.conkey)
                      ORDER BY a.attnum),
                ','
              ) LIKE '%numero_lote%'
    """)
    existe = cur.fetchone()[0] > 0
    if not existe:
        print("[MIGRAR] Creando UNIQUE constraint en lotes_mapa...")
        cur.execute("""
            ALTER TABLE lotes_mapa
            ADD CONSTRAINT uq_lotes_mapa_loteo_nro
            UNIQUE (tenant_slug, loteo_id, numero_lote)
        """)
        print("[MIGRAR] UNIQUE constraint creado.")
    else:
        print("[MIGRAR] UNIQUE constraint ya existe — OK.")


def migrar():
    if not PG_PASS:
        print("[MIGRAR] ERROR: LOVBOT_PG_PASS no configurado.")
        sys.exit(1)

    conn = _conn()
    cur = conn.cursor()

    # 1. Asegurar constraint
    try:
        asegurar_unique_constraint(cur)
        conn.commit()
    except Exception as e:
        print(f"[MIGRAR] WARN al crear constraint (puede ya existir): {e}")
        conn.rollback()

    # 2. Listar loteos del tenant
    cur.execute(
        "SELECT id, nombre, total_lotes FROM loteos WHERE tenant_slug=%s ORDER BY id",
        (TENANT,),
    )
    loteos = cur.fetchall()
    print(f"[MIGRAR] Tenant='{TENANT}' — {len(loteos)} loteos encontrados.")

    total_generados = 0
    total_omitidos  = 0

    for loteo_id, nombre, total_lotes in loteos:
        total_lotes = int(total_lotes or 0)

        # Contar lotes existentes en lotes_mapa
        cur.execute(
            "SELECT COUNT(*) FROM lotes_mapa WHERE tenant_slug=%s AND loteo_id=%s",
            (TENANT, loteo_id),
        )
        existentes = cur.fetchone()[0]

        if existentes > 0:
            print(f"  [{loteo_id}] {nombre}: ya tiene {existentes} lotes — OMITIENDO.")
            total_omitidos += 1
            continue

        if total_lotes <= 0:
            print(f"  [{loteo_id}] {nombre}: total_lotes=0 — OMITIENDO.")
            total_omitidos += 1
            continue

        manzanas = _dividir_en_manzanas(total_lotes)
        insertados = 0
        for mz_idx, lotes in enumerate(manzanas):
            mz_nombre = _nombre_manzana(mz_idx)
            for nro_lote in lotes:
                try:
                    cur.execute(
                        """INSERT INTO lotes_mapa
                             (tenant_slug, loteo_id, manzana, numero_lote, estado)
                           VALUES (%s, %s, %s, %s, 'disponible')
                           ON CONFLICT (tenant_slug, loteo_id, numero_lote) DO NOTHING""",
                        (TENANT, loteo_id, mz_nombre, str(nro_lote)),
                    )
                    insertados += 1
                except Exception as ex:
                    print(f"    WARN insertar lote {nro_lote}: {ex}")

        conn.commit()
        print(f"  [{loteo_id}] {nombre}: generados {insertados} lotes en {len(manzanas)} manzanas.")
        total_generados += insertados

    # 3. Recalcular contadores en loteos
    print("[MIGRAR] Recalculando contadores lotes_disponibles/reservados/vendidos...")
    cur.execute(
        """
        UPDATE loteos l SET
          lotes_disponibles = COALESCE(s.disp, 0),
          lotes_reservados  = COALESCE(s.res, 0),
          lotes_vendidos    = COALESCE(s.vend, 0),
          updated_at        = CURRENT_TIMESTAMP
        FROM (
          SELECT loteo_id,
            COUNT(*) FILTER (WHERE estado IN ('libre','disponible')) AS disp,
            COUNT(*) FILTER (WHERE estado='reservado')              AS res,
            COUNT(*) FILTER (WHERE estado='vendido')                AS vend
          FROM lotes_mapa
          WHERE tenant_slug=%s
          GROUP BY loteo_id
        ) s
        WHERE l.id = s.loteo_id AND l.tenant_slug=%s
        """,
        (TENANT, TENANT),
    )
    conn.commit()
    print("[MIGRAR] Contadores actualizados.")

    cur.close()
    conn.close()

    print(f"\n[MIGRAR] Listo — {total_generados} lotes generados, {total_omitidos} loteos omitidos.")


if __name__ == "__main__":
    migrar()
