"""
Lead matcher cross-channel
===========================
Busca y reconoce leads en Postgres por número de teléfono normalizado,
sin importar el canal de origen (WhatsApp `wa_id` o voz `caller_id`).

Diferencial de producto: si un cliente habla por WhatsApp y al día siguiente
llama por voz, el agente lo reconoce y carga su contexto BANT previo en
lugar de arrancar de cero.

Funciones:
    normalize_phone(raw)    → solo dígitos
    find_lead_by_phone(p)   → dict lead o None
    upsert_lead(p, **data)  → registra/actualiza lead con canal de origen
"""

import re
from typing import Optional


def normalize_phone(raw: str) -> str:
    """Normaliza a solo dígitos (descarta +, espacios, guiones, paréntesis).

    Cal.com / Twilio entregan formato distinto a Meta WhatsApp. Esto los unifica.
    """
    if not raw:
        return ""
    return re.sub(r"\D", "", str(raw))


def find_lead_by_phone(phone: str) -> Optional[dict]:
    """Busca un lead por teléfono normalizado.

    Hace match si los últimos 10 dígitos coinciden (tolera prefijos país
    distintos: '5493764999999' y '93764999999' deberían matchear si solo
    '3764999999' está en BD).

    Returns:
        dict con campos del lead, o None si no existe.
    """
    digits = normalize_phone(phone)
    if not digits:
        return None
    from workers.demos.inmobiliaria import db_postgres as db
    if not db._available():
        return None
    last10 = digits[-10:] if len(digits) >= 10 else digits
    try:
        conn = db._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, nombre, apellido, telefono, email, score, estado,
                   tipo_propiedad, zona, operacion, ciudad, presupuesto,
                   notas_bot, fuente, fuente_detalle, fecha_ultimo_contacto
            FROM leads
            WHERE tenant_slug = %s
              AND RIGHT(REGEXP_REPLACE(telefono, '\\D', '', 'g'), 10) = %s
            ORDER BY fecha_ultimo_contacto DESC NULLS LAST
            LIMIT 1
            """,
            (db.TENANT, last10),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        cols = ["id", "nombre", "apellido", "telefono", "email", "score", "estado",
                "tipo_propiedad", "zona", "operacion", "ciudad", "presupuesto",
                "notas_bot", "fuente", "fuente_detalle", "fecha_ultimo_contacto"]
        return dict(zip(cols, row))
    except Exception as e:
        print(f"[LEAD_MATCHER] error: {e}")
        return None


def upsert_lead_voice(phone: str, name: str = "", email: str = "",
                      score: str = "", notes: str = "") -> None:
    """Registra o actualiza lead desde canal voz.

    Usa la misma función `registrar_lead` del demo (fuente_detalle marca
    el canal para reportería).
    """
    from workers.demos.inmobiliaria import db_postgres as db
    digits = normalize_phone(phone)
    if not digits:
        return
    db.registrar_lead(
        telefono=digits,
        nombre=name,
        score=score or "tibio",
        notas=notes,
        fuente_detalle="canal:voz_elevenlabs",
    )
    if email:
        db.guardar_email(digits, email)
