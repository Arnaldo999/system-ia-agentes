import os
import re
import json
import requests as req
from datetime import datetime, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict

router = APIRouter(prefix="/agenda", tags=["Agendamiento"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

TIPOS_RECORDATORIO = ["confirmacion", "recordatorio_24h", "recordatorio_1h", "reprogramacion"]


class DatosParsearFecha(BaseModel):
    texto: str
    zona_horaria: Optional[str] = "America/Argentina/Buenos_Aires"
    fecha_referencia: Optional[str] = ""  # YYYY-MM-DD; default: hoy


class DatosVerificarSlot(BaseModel):
    fecha_solicitada: str    # YYYY-MM-DD
    hora_solicitada: str     # HH:MM
    duracion_minutos: Optional[int] = 60
    eventos_existentes: Optional[List[Dict]] = []
    # Cada evento: {titulo, inicio: "ISO", fin: "ISO"}


class DatosGenerarRecordatorio(BaseModel):
    cita: Dict
    # cita debe tener: nombre_cliente, fecha, hora, servicio, lugar_o_link
    tipo: Optional[str] = "confirmacion"
    brandbook: Optional[Dict] = {}


def _call_gemini_text(prompt: str, timeout: int = 30) -> str:
    resp = req.post(
        f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json_from_text(texto: str) -> dict:
    match = re.search(r'\{[\s\S]*\}', texto)
    if not match:
        raise ValueError("No se encontró JSON en la respuesta.")
    return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# POST /agenda/parsear-fecha
# ---------------------------------------------------------------------------
@router.post("/parsear-fecha")
async def parsear_fecha(entrada: DatosParsearFecha):
    """
    Convierte lenguaje natural (español LATAM) a fecha/hora estructurada.
    Maneja expresiones relativas: "el martes", "mañana a las 3", "la próxima semana".
    Entrada: texto + zona_horaria + fecha_referencia.
    Salida: {status, fecha, hora, fecha_hora_iso, es_aproximado, confianza,
             texto_interpretado, ambiguo, razon_ambiguedad}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    hoy = entrada.fecha_referencia or datetime.now().strftime("%Y-%m-%d")

    try:
        fecha_obj = datetime.strptime(hoy, "%Y-%m-%d")
        dia_semana_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        dia_semana = dia_semana_es[fecha_obj.weekday()]
    except Exception:
        dia_semana = "desconocido"

    prompt = f"""Extrae la fecha y hora de este texto en español latinoamericano.
Fecha de referencia HOY: {hoy} ({dia_semana})
Zona horaria del usuario: {entrada.zona_horaria}

Texto a interpretar: "{entrada.texto}"

Considera expresiones típicas de LATAM:
- "el jueves" → próximo jueves desde hoy
- "mañana" → {hoy} + 1 día
- "la próxima semana" → siguiente semana
- "a las 3" → 15:00 si es contexto de tarde/trabajo, sino 09:00
- "al mediodía" → 12:00

Responde SOLO con este JSON exacto:
{{
  "fecha": "YYYY-MM-DD",
  "hora": "HH:MM",
  "fecha_hora_iso": "YYYY-MM-DDTHH:MM:00",
  "es_aproximado": false,
  "confianza": "[alta/media/baja]",
  "texto_interpretado": "Cómo interpretaste la expresión en lenguaje natural",
  "ambiguo": false,
  "razon_ambiguedad": ""
}}

Si no hay hora explícita: usa 09:00.
Si el texto no contiene fecha interpretable: todos los campos vacíos y ambiguo: true."""

    try:
        texto = _call_gemini_text(prompt, timeout=20)
        parsed = _parse_json_from_text(texto)
        return {"status": "success", **parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error parseando fecha: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /agenda/verificar-slot
# ---------------------------------------------------------------------------
@router.post("/verificar-slot")
async def verificar_slot(entrada: DatosVerificarSlot):
    """
    Verifica disponibilidad de un horario contra la agenda existente.
    Lógica pura Python — sin IA, rápido y determinista.
    Entrada: fecha_solicitada + hora_solicitada + duracion_minutos + eventos_existentes.
    Salida: {status, disponible, slot_solicitado, conflictos, mensaje}
    """
    try:
        slot_inicio_str = f"{entrada.fecha_solicitada}T{entrada.hora_solicitada}:00"
        slot_inicio = datetime.fromisoformat(slot_inicio_str)
        slot_fin    = slot_inicio + timedelta(minutes=entrada.duracion_minutos)

        conflictos = []

        for evento in entrada.eventos_existentes:
            inicio_str = evento.get("inicio", "")
            fin_str    = evento.get("fin", "")

            if not inicio_str:
                continue

            try:
                ev_inicio = datetime.fromisoformat(inicio_str.replace("Z", "+00:00").replace("+00:00", ""))
                ev_fin = datetime.fromisoformat(fin_str.replace("Z", "+00:00").replace("+00:00", "")) \
                    if fin_str else ev_inicio + timedelta(hours=1)

                # Overlap detection: A overlaps B if A.start < B.end AND A.end > B.start
                if slot_inicio < ev_fin and slot_fin > ev_inicio:
                    conflictos.append({
                        "titulo": evento.get("titulo", "Evento sin título"),
                        "inicio": inicio_str,
                        "fin":    fin_str
                    })
            except Exception:
                continue

        disponible = len(conflictos) == 0

        return {
            "status": "success",
            "disponible": disponible,
            "slot_solicitado": {
                "inicio": slot_inicio.isoformat(),
                "fin":    slot_fin.isoformat()
            },
            "conflictos": conflictos,
            "mensaje": "Slot disponible ✓" if disponible else f"Slot ocupado: {len(conflictos)} conflicto(s)"
        }

    except Exception as e:
        return {"status": "error", "mensaje": f"Error verificando slot: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /agenda/generar-recordatorio
# ---------------------------------------------------------------------------
@router.post("/generar-recordatorio")
async def generar_recordatorio(entrada: DatosGenerarRecordatorio):
    """
    Genera mensajes de WhatsApp para confirmar citas y enviar recordatorios.
    Adapta el mensaje según el tipo: confirmacion, recordatorio_24h, recordatorio_1h.
    Entrada: cita (dict con datos) + tipo + brandbook.
    Salida: {status, mensaje, tipo}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    bb             = entrada.brandbook
    nombre_agencia = bb.get("nombre_agencia", "System IA")
    tono           = bb.get("tono", "amable y profesional")

    cita           = entrada.cita
    nombre_cliente = cita.get("nombre_cliente", "")
    fecha          = cita.get("fecha", "")
    hora           = cita.get("hora", "")
    servicio       = cita.get("servicio", "reunión")
    lugar          = cita.get("lugar_o_link", "a confirmar")
    duracion       = cita.get("duracion_minutos", "")

    proposito_por_tipo = {
        "confirmacion":      "Confirmar que la cita fue agendada exitosamente y dar todos los detalles.",
        "recordatorio_24h":  "Recordar amablemente que mañana tiene una cita. Pedir confirmar asistencia.",
        "recordatorio_1h":   "Avisar que la cita es en 1 hora. Tono más urgente pero amable.",
        "reprogramacion":    "Informar que la cita fue reprogramada con los nuevos datos."
    }
    proposito = proposito_por_tipo.get(entrada.tipo, "Recordatorio de cita")

    duracion_str = f"\n- Duración: {duracion} minutos" if duracion else ""

    prompt = f"""Eres el asistente de {nombre_agencia}.
Tono de voz: {tono}

Propósito del mensaje: {proposito}

DATOS DE LA CITA:
- Cliente: {nombre_cliente}
- Servicio: {servicio}
- Fecha: {fecha}
- Hora: {hora}{duracion_str}
- Lugar / Link: {lugar}

Escribe el mensaje de WhatsApp:
- Personalizado con el nombre del cliente
- Incluye todos los datos relevantes con formato limpio
- Usa saltos de línea para separar la info (no listas con guiones)
- Sin asteriscos ni markdown
- Máximo 5 líneas
- Para recordatorio_1h: transmite urgencia amable sin alarmar
- Para confirmacion: transmite entusiasmo y profesionalismo"""

    try:
        texto = _call_gemini_text(prompt, timeout=30)
        return {
            "status":  "success",
            "mensaje": texto.strip(),
            "tipo":    entrada.tipo
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error generando recordatorio: {str(e)}"}
