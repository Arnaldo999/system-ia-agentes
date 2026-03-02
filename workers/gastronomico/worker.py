"""
Worker Gastronómico — SaaS para Restaurantes, Bares y Cafés
============================================================
Endpoints:
  POST /gastronomico/basic/reserva      → Plan BASIC (sin pasarela de pago)
  POST /gastronomico/pro/reserva        → Plan PROFESIONAL (con seña MercadoPago/Stripe)
  POST /gastronomico/premium/fidelizar  → Plan PREMIUM (cumpleaños + eventos)

Integración: n8n Webhook → HTTP POST aquí → CrewAI → JSON Response → n8n envía WhatsApp
"""

import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from crewai import Agent, Task, Crew

router = APIRouter(prefix="/gastronomico", tags=["SaaS Gastronómico"])

MODELO = os.environ.get("CREWAI_MODEL", "gemini/gemini-2.5-flash")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE DATOS (Pydantic) — Lo que n8n envía en el body del POST
# ─────────────────────────────────────────────────────────────────────────────

class DatosRestauranteBasic(BaseModel):
    nombre_local: str
    cvu_alias: str
    horario_atencion: str
    menu_del_dia: Optional[str] = ""


class PayloadBasic(BaseModel):
    mensaje_cliente: str
    restaurante: DatosRestauranteBasic


class DatosRestaurantePro(BaseModel):
    nombre_local: str
    alias_pago: str
    pasarela: str = "MercadoPago"
    monto_sena_porcentaje: int = 30
    precio_promedio_cubierto: float
    horario_atencion: str
    mesas_disponibles: List[str] = []


class PayloadPro(BaseModel):
    nombre_cliente: str
    telefono: str
    mensaje_cliente: str
    restaurante: DatosRestaurantePro


class PerfilCliente(BaseModel):
    nombre: str
    fecha_cumpleanios: str
    visitas_totales: int = 0
    ultima_visita: Optional[str] = ""
    plato_favorito: Optional[str] = ""
    dias_para_cumpleanios: int = 0
    tiene_reserva_activa: bool = False
    canal_preferido: str = "WhatsApp"


class EventoProximo(BaseModel):
    nombre: str
    fecha: str
    descripcion: str


class DatosRestaurantePremium(BaseModel):
    nombre_local: str
    tipo_cocina: str
    obsequio_cumpleanios: str
    descuento_especial: str
    link_reserva: str
    evento_proximo: Optional[EventoProximo] = None


class PayloadPremium(BaseModel):
    perfil_cliente: PerfilCliente
    restaurante: DatosRestaurantePremium


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1: PLAN BASIC — Toma de Reservas y Confirmación de CVU
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/basic/reserva", summary="Plan BASIC: Tomar reserva y confirmar CVU")
async def reserva_basic(payload: PayloadBasic):
    """
    Recibe el mensaje de un cliente por WhatsApp y extrae los datos de reserva.
    Devuelve el mensaje de confirmación listo para enviar por WhatsApp via n8n.

    Flujo n8n: Webhook → POST /gastronomico/basic/reserva → WhatsApp (Evolution API)
    """
    r = payload.restaurante

    recepcionista = Agent(
        role="Recepcionista Virtual del Restaurante",
        goal=(
            "Extraer de forma precisa todos los datos de reserva de un cliente "
            "(nombre, cantidad de personas, fecha y horario) desde un mensaje de WhatsApp. "
            "Si falta algún dato, identificar cuál es y preparar la pregunta para solicitarlo cortésmente."
        ),
        backstory=(
            f"Eres el asistente digital del restaurante '{r.nombre_local}'. "
            f"Horario de atención: {r.horario_atencion}. "
            "Hablas en español con tono amigable y profesional."
        ),
        llm=MODELO,
        verbose=False
    )

    confirmador = Agent(
        role="Confirmador de Reservas y Asistente de Delivery",
        goal=(
            "Redactar el mensaje final de confirmación de reserva con todos los datos del cliente, "
            "incluyendo el CVU/Alias del local para confirmar pagos de delivery si aplica."
        ),
        backstory=(
            f"Eres el sistema de backend del restaurante '{r.nombre_local}'. "
            f"CVU/Alias del local para transferencias: {r.cvu_alias}. "
            f"Menú del día disponible: {r.menu_del_dia or 'consultar en el local'}. "
            "Redactas mensajes de WhatsApp breves (máximo 5 líneas) y claros."
        ),
        llm=MODELO,
        verbose=False
    )

    tarea_extraccion = Task(
        description=(
            f"El cliente envió: '{payload.mensaje_cliente}'. "
            "Extrae: nombre, personas, fecha, horario. "
            "Indica si todos los datos están presentes o cuál falta."
        ),
        expected_output="Diccionario con: nombre, personas, fecha, horario, estado (completo/incompleto), dato_faltante si aplica.",
        agent=recepcionista
    )

    tarea_confirmacion = Task(
        description=(
            "Con los datos extraídos, redacta el mensaje de confirmación de WhatsApp. "
            f"Restaurante: {r.nombre_local}. "
            "Si el cliente mencionó delivery, incluye el alias de pago. Máximo 5 líneas."
        ),
        expected_output="Texto exacto del mensaje de WhatsApp listo para enviar.",
        agent=confirmador,
        context=[tarea_extraccion]
    )

    try:
        crew = Crew(agents=[recepcionista, confirmador], tasks=[tarea_extraccion, tarea_confirmacion], verbose=False)
        resultado = crew.kickoff()
        return {
            "plan": "BASIC",
            "restaurante": r.nombre_local,
            "mensaje_cliente_original": payload.mensaje_cliente,
            "respuesta_bot_whatsapp": str(resultado),
            "estado": "reserva_procesada"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en CrewAI Basic: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2: PLAN PROFESIONAL — Reserva con Seña + Pasarela de Pago
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/pro/reserva", summary="Plan PROFESIONAL: Reserva con seña automática vía MercadoPago/Stripe")
async def reserva_pro(payload: PayloadPro):
    """
    Confirma reserva, calcula la seña, genera N° de reserva y link de pago.
    La mesa se asigna automáticamente desde la lista de disponibles.

    Flujo n8n: Webhook → POST /gastronomico/pro/reserva → WhatsApp Cloud API (Meta)
    """
    r = payload.restaurante

    # Calcular seña antes de pasar al Crew
    total_estimado = r.precio_promedio_cubierto * 6  # Estimado base; en prod vendría del msg
    monto_sena = int(total_estimado * r.monto_sena_porcentaje / 100)
    nro_reserva = f"RSV-{str(uuid.uuid4())[:6].upper()}"
    mesa_asignada = r.mesas_disponibles[0] if r.mesas_disponibles else "Mesa por asignar"
    link_pago = f"https://mp.com/checkout/v1/redirect?pref_id={nro_reserva}"

    recepcionista_pro = Agent(
        role="Recepcionista Digital Premium",
        goal="Verificar los datos de reserva y confirmar disponibilidad de mesa.",
        backstory=(
            f"Asistente del restaurante '{r.nombre_local}'. "
            f"Horario: {r.horario_atencion}. "
            f"Mesas disponibles: {', '.join(r.mesas_disponibles)}. "
            "Hablas en español, tono sofisticado y breve."
        ),
        llm=MODELO,
        verbose=False
    )

    notificador_pro = Agent(
        role="Redactor de Confirmaciones Premium con Instrucción de Pago",
        goal=(
            "Redactar el mensaje de WhatsApp de confirmación con N° de reserva, "
            "mesa, monto de seña, link de pago y alias. Máximo 8 líneas."
        ),
        backstory=(
            f"Sistema de backend de pagos de '{r.nombre_local}'. "
            f"Pasarela: {r.pasarela}. Alias: {r.alias_pago}. "
            f"Seña calculada: ${monto_sena} ARS. N° reserva: {nro_reserva}. Mesa: {mesa_asignada}."
        ),
        llm=MODELO,
        verbose=False
    )

    tarea_verificacion = Task(
        description=(
            f"El cliente {payload.nombre_cliente} envió: '{payload.mensaje_cliente}'. "
            "Verifica que tenga nombre, personas, fecha y horario completos. "
            f"Confirma si el horario está dentro del horario del local: {r.horario_atencion}."
        ),
        expected_output="Resumen: datos de reserva confirmados, horario válido o no, mesa sugerida.",
        agent=recepcionista_pro
    )

    tarea_mensaje_pago = Task(
        description=(
            f"Con los datos verificados, redacta el mensaje de confirmación para {payload.nombre_cliente}. "
            f"Incluir: fecha/hora/personas, N° reserva ({nro_reserva}), mesa ({mesa_asignada}), "
            f"seña (${monto_sena} ARS), link de pago ({link_pago}), alias ({r.alias_pago})."
        ),
        expected_output="Texto exacto del mensaje de WhatsApp de confirmación con todos los datos de pago.",
        agent=notificador_pro,
        context=[tarea_verificacion]
    )

    try:
        crew = Crew(agents=[recepcionista_pro, notificador_pro], tasks=[tarea_verificacion, tarea_mensaje_pago], verbose=False)
        resultado = crew.kickoff()
        return {
            "plan": "PROFESIONAL",
            "restaurante": r.nombre_local,
            "cliente": payload.nombre_cliente,
            "telefono": payload.telefono,
            "nro_reserva": nro_reserva,
            "mesa_asignada": mesa_asignada,
            "monto_sena_ars": monto_sena,
            "link_pago_generado": link_pago,
            "respuesta_bot_whatsapp": str(resultado),
            "estado": "sena_pendiente_de_pago"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en CrewAI Pro: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 3: PLAN PREMIUM — Motor de Fidelización (Cumpleaños + Eventos)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/premium/fidelizar", summary="Plan PREMIUM: Generador de mensajes de cumpleaños y eventos")
async def fidelizar_premium(payload: PayloadPremium):
    """
    Trigger: CRON Job diario en n8n detecta clientes con cumpleaños hoy.
    Genera el mensaje de felicitación personalizado con obsequio, descuento y evento del local.

    Flujo n8n: Schedule Trigger → Airtable CRM → POST /gastronomico/premium/fidelizar → WhatsApp
    """
    c = payload.perfil_cliente
    r = payload.restaurante

    analista = Agent(
        role="Analista de Perfil de Fidelización",
        goal="Determinar el nivel del cliente (VIP/Regular) y la estrategia de comunicación ideal.",
        backstory=(
            f"Sistema CRM de '{r.nombre_local}'. "
            f"El cliente {c.nombre} tiene {c.visitas_totales} visitas. "
            "Más de 5 visitas = cliente VIP con trato diferencial."
        ),
        llm=MODELO,
        verbose=False
    )

    copywriter = Agent(
        role="Copywriter de Felicitaciones de Cumpleaños",
        goal=(
            "Redactar un mensaje de felicitación de cumpleaños personalizado para WhatsApp. "
            "Máximo 7 líneas. Emojis con moderación. Tono cálido y elegante."
        ),
        backstory=(
            f"Escritor creativo de '{r.nombre_local}' ({r.tipo_cocina}). "
            f"Obsequio de la casa: {r.obsequio_cumpleanios}. "
            f"Descuento especial: {r.descuento_especial}. "
            f"Link de reserva: {r.link_reserva}. "
            f"Plato favorito del cliente: {c.plato_favorito or 'no registrado'}."
        ),
        llm=MODELO,
        verbose=False
    )

    tarea_analisis = Task(
        description=(
            f"Analiza el perfil: {c.visitas_totales} visitas totales, última visita {c.ultima_visita}. "
            f"¿Es hoy su cumpleaños? ('dias_para_cumpleanios' = {c.dias_para_cumpleanios}). "
            f"¿Tiene reserva activa? {c.tiene_reserva_activa}. "
            "Define: nivel del cliente, tono del mensaje, si incluir link de reserva."
        ),
        expected_output="Resumen estratégico: nivel, tono recomendado, incluir reserva true/false.",
        agent=analista
    )

    descripcion_evento = ""
    if r.evento_proximo:
        descripcion_evento = (
            f"Si el cliente es VIP y no tiene reserva activa, añade al final una invitación al evento: "
            f"'{r.evento_proximo.nombre}' el {r.evento_proximo.fecha}. "
            f"({r.evento_proximo.descripcion}). Máximo 2 líneas extra."
        )

    tarea_mensaje = Task(
        description=(
            f"Redacta el mensaje de cumpleaños para {c.nombre}. "
            f"Restaurante: {r.nombre_local}. "
            f"Plato favorito: {c.plato_favorito}. "
            f"Obsequio: {r.obsequio_cumpleanios}. Descuento: {r.descuento_especial}. "
            f"Link reserva: {r.link_reserva}. "
            f"{descripcion_evento}"
        ),
        expected_output="Texto final del mensaje de WhatsApp listo para enviar.",
        agent=copywriter,
        context=[tarea_analisis]
    )

    try:
        crew = Crew(agents=[analista, copywriter], tasks=[tarea_analisis, tarea_mensaje], verbose=False)
        resultado = crew.kickoff()
        return {
            "plan": "PREMIUM",
            "tipo_disparo": "cumpleanios",
            "restaurante": r.nombre_local,
            "cliente": c.nombre,
            "canal": c.canal_preferido,
            "mensaje_generado": str(resultado),
            "obsequio_incluido": r.obsequio_cumpleanios,
            "descuento_incluido": r.descuento_especial,
            "evento_promovido": r.evento_proximo.nombre if r.evento_proximo else None,
            "estado": "listo_para_envio"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en CrewAI Premium: {str(e)}")
