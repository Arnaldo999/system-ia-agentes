"""
Seguimiento Automático de Leads — Robert / Lovbot Inmobiliaria
==============================================================
Ejecuta la secuencia de 6 puntos de contacto según el PDF "Agente AI Inmobiliario".

Secuencia:
  1. Inmediato       → respuesta inicial (bot lo hace)
  2. +24 horas       → seguimiento suave
  3. +3 días         → valor (ficha / info zona)
  4. +7 días         → nuevas opciones
  5. +14 días        → reactivación
  6. +30 días        → último intento → mover a "lead dormido"

Campos Airtable usados:
  - Estado_Seguimiento: activo / pausado / dormido / completado
  - Cantidad_Seguimientos: 0-6
  - Proximo_Seguimiento: fecha ISO
  - Ultimo_Contacto_Bot: fecha ISO del último mensaje automático

Uso:
  python seguimiento_leads.py

Cron (Coolify scheduled task):
  0 14 * * * cd /app/scripts && python seguimiento_leads.py
  (14:00 UTC = 11:00 ARG — después de la auditoría diaria)
"""

import os
import re
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Config ───────────────────────────────────────────────────────────────────
AIRTABLE_TOKEN  = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE   = os.environ.get("ROBERT_AIRTABLE_BASE", "")
AIRTABLE_TABLE  = os.environ.get("ROBERT_TABLE_CLIENTES", "")
META_TOKEN      = os.environ.get("META_ACCESS_TOKEN", "")
META_PHONE_ID   = os.environ.get("META_PHONE_NUMBER_ID", "")
TELEGRAM_BOT    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")
NOMBRE_EMPRESA  = os.environ.get("INMO_DEMO_NOMBRE", "Lovbot — Inmobiliaria")
NOMBRE_ASESOR   = os.environ.get("INMO_DEMO_ASESOR", "Roberto")

AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
REQUEST_TIMEOUT = 10

# ── Mensajes de seguimiento ──────────────────────────────────────────────────
# {nombre} y {asesor} se reemplazan dinámicamente

MENSAJES_SEGUIMIENTO = {
    1: (
        "Hola *{nombre}* 👋\n\n"
        "Soy el asistente de *{empresa}*. Ayer conversamos sobre propiedades "
        "que podrían interesarte.\n\n"
        "¿Pudiste ver las opciones que te envié? Estoy para ayudarte con cualquier duda. 🏡"
    ),
    2: (
        "Hola *{nombre}* 🏡\n\n"
        "Te comparto información adicional sobre las propiedades que vimos. "
        "Si te interesa alguna en particular, puedo enviarte la ficha completa "
        "con fotos, planos y detalles de financiamiento.\n\n"
        "¿Te gustaría agendar una visita? 📅"
    ),
    3: (
        "Hola *{nombre}* 👋\n\n"
        "Tenemos *nuevas propiedades* que coinciden con lo que buscás. "
        "¿Te gustaría que te las muestre?\n\n"
        "Escribí *Sí* y te envío las mejores opciones actualizadas. 🏠"
    ),
    4: (
        "Hola *{nombre}* 🏡\n\n"
        "Solo quería saber si seguís buscando propiedad. "
        "Hay novedades en la zona que te interesaba y algunas opciones "
        "con muy buena relación precio-calidad.\n\n"
        "¿Te interesa que te cuente? *{asesor}* está disponible para asesorarte. 📞"
    ),
    5: (
        "Hola *{nombre}* 👋\n\n"
        "Hace un tiempo conversamos sobre tu búsqueda de propiedad. "
        "Quería hacerte saber que seguimos a tu disposición.\n\n"
        "Si en algún momento retomás la búsqueda, escribinos y te ayudamos "
        "con las mejores opciones del momento. ¡Éxitos! 🙌"
    ),
}


# ── WhatsApp ─────────────────────────────────────────────────────────────────
def enviar_whatsapp(telefono: str, mensaje: str) -> bool:
    if not META_TOKEN or not META_PHONE_ID:
        print(f"[seguimiento] Sin token Meta. Msg: {mensaje[:60]}")
        return False
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{META_PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": re.sub(r'\D', '', telefono),
                "type": "text",
                "text": {"body": mensaje, "preview_url": False},
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            return True
        print(f"[seguimiento] Error WhatsApp {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[seguimiento] Excepción WhatsApp: {e}")
        return False


# ── Airtable ─────────────────────────────────────────────────────────────────
def obtener_leads_pendientes() -> list[dict]:
    """Busca leads con Estado_Seguimiento='activo' y Proximo_Seguimiento <= hoy."""
    hoy = datetime.date.today().isoformat()
    formula = (
        "AND("
        "{Estado_Seguimiento}='activo',"
        f"IS_BEFORE({{Proximo_Seguimiento}}, '{hoy}T23:59:59.000Z')"
        ")"
    )
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}"
    try:
        r = requests.get(url, headers=AT_HEADERS,
                         params={"filterByFormula": formula, "maxRecords": 50},
                         timeout=REQUEST_TIMEOUT)
        return r.json().get("records", [])
    except Exception as e:
        print(f"[seguimiento] Error Airtable GET: {e}")
        return []


def actualizar_lead(record_id: str, campos: dict) -> bool:
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}/{record_id}"
    try:
        r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=REQUEST_TIMEOUT)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[seguimiento] Error Airtable PATCH: {e}")
        return False


# ── Calcular próximo seguimiento ─────────────────────────────────────────────
DIAS_SEGUIMIENTO = {
    1: 1,    # +24h después del primer contacto
    2: 3,    # +3 días
    3: 7,    # +7 días
    4: 14,   # +14 días
    5: 30,   # +30 días
}


def calcular_proximo(cantidad_actual: int) -> str | None:
    """Retorna fecha ISO del próximo seguimiento, o None si ya completó los 5."""
    siguiente = cantidad_actual + 1
    if siguiente > 5:
        return None  # completó toda la secuencia
    dias = DIAS_SEGUIMIENTO.get(siguiente, 7)
    return (datetime.date.today() + datetime.timedelta(days=dias)).isoformat()


# ── Telegram ─────────────────────────────────────────────────────────────────
def enviar_telegram(mensaje: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": mensaje, "parse_mode": "HTML"},
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as e:
        print(f"[seguimiento] Error Telegram: {e}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not AIRTABLE_BASE or not AIRTABLE_TABLE:
        print("[seguimiento] Airtable no configurado — saliendo")
        return

    leads = obtener_leads_pendientes()
    print(f"[seguimiento] {len(leads)} leads pendientes de seguimiento")

    enviados = 0
    dormidos = 0
    errores = 0

    for record in leads:
        fields = record.get("fields", {})
        record_id = record["id"]
        telefono = fields.get("Telefono", "")
        nombre = fields.get("Nombre", "Cliente")
        cantidad = int(fields.get("Cantidad_Seguimientos", 0))

        if not telefono:
            continue

        # Determinar qué mensaje enviar
        numero_mensaje = cantidad + 1

        if numero_mensaje > 5:
            # Completó la secuencia → mover a dormido
            actualizar_lead(record_id, {
                "Estado_Seguimiento": "dormido",
                "Estado": "seguimiento",
            })
            dormidos += 1
            print(f"[seguimiento] {nombre} ({telefono}) → dormido (completó 5 seguimientos)")
            continue

        # Enviar mensaje
        plantilla = MENSAJES_SEGUIMIENTO.get(numero_mensaje, MENSAJES_SEGUIMIENTO[5])
        mensaje = plantilla.format(
            nombre=nombre.split()[0] if nombre else "Cliente",
            asesor=NOMBRE_ASESOR,
            empresa=NOMBRE_EMPRESA,
        )

        ok = enviar_whatsapp(telefono, mensaje)
        if ok:
            proximo = calcular_proximo(numero_mensaje)
            campos_update = {
                "Cantidad_Seguimientos": numero_mensaje,
                "Ultimo_Contacto_Bot": datetime.datetime.utcnow().isoformat() + "Z",
            }
            if proximo:
                campos_update["Proximo_Seguimiento"] = proximo
            else:
                campos_update["Estado_Seguimiento"] = "dormido"
                campos_update["Estado"] = "seguimiento"
                dormidos += 1

            actualizar_lead(record_id, campos_update)
            enviados += 1
            print(f"[seguimiento] ✅ {nombre} — mensaje #{numero_mensaje} enviado")
        else:
            errores += 1
            print(f"[seguimiento] ❌ {nombre} — error enviando mensaje #{numero_mensaje}")

    # Reporte
    print(f"[seguimiento] Resultado: {enviados} enviados, {dormidos} dormidos, {errores} errores")

    if enviados > 0 or dormidos > 0:
        fecha = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=-3))
        ).strftime("%d/%m/%Y %H:%M ARG")
        enviar_telegram(
            f"🔄 <b>Seguimiento Leads — Lovbot</b> — {fecha}\n\n"
            f"📤 Mensajes enviados: {enviados}\n"
            f"😴 Movidos a dormido: {dormidos}\n"
            f"❌ Errores: {errores}\n"
            f"📊 Total procesados: {len(leads)}"
        )


if __name__ == "__main__":
    main()
