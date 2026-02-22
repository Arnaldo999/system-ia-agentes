import os
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from openai import OpenAI

router = APIRouter(prefix="/comercio", tags=["Comercio WhatsApp"])

# La API key se tomará del entorno de Easypanel
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Instanciamos el cliente de OpenAI. Si no hay key, fallará en tiempo de ejecución de manera controlada.
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class MensajeVendedor(BaseModel):
    mensaje_audio_o_texto: str

class ConsultaCliente(BaseModel):
    mensaje_cliente: str
    catalogo: List[Dict[str, Any]] # Array que viene de n8n desde Airtable

# =========================================================================
# 1. FLUJO DEL DUEÑO (VENDEDOR) - CARGAR/MODIFICAR PRODUCTO
# =========================================================================
@router.post("/procesar-mensaje-admin")
async def procesar_admin(entrada: MensajeVendedor):
    """
    Recibe un mensaje de voz/texto del dueño y extrae la intención y los datos del producto.
    No maneja stock numérico, solo 'Disponible' o 'No Disponible'.
    """
    if not client:
        return {"status": "error", "mensaje": "Falta OPENAI_API_KEY en las variables de entorno."}

    prompt = f"""Estarás analizando un mensaje del dueño de un comercio.
Su objetivo es gestionar su catálogo de productos.
No usamos stock numérico, solo estado "Disponible" (para vender) o "No Disponible" (agotado).

MENSAJE DEL DUEÑO:
"{entrada.mensaje_audio_o_texto}"

TAREA:
Extrae la información en un JSON estricto con esta estructura:
{{
  "accion": "crear_producto" | "actualizar_disponibilidad" | "actualizar_precio" | "desconocida",
  "datos": {{
    "nombre_producto": "Nombre claro del producto (ej. Zapatillas Nike Negras Talla 40)",
    "precio": 120.00 (solo número, sin moneda, null si no lo menciona),
    "disponible": true | false (true si dice que hay o agrega, false si dice que se agotó o no hay)
  }}
}}
Responde SOLO con el JSON validado.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        resultado_json = json.loads(response.choices[0].message.content)
        return {
            "status": "success",
            "resultado": resultado_json
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error procesando con OpenAI: {str(e)}"}


# =========================================================================
# 2. FLUJO DEL CLIENTE FINAL - ATENCIÓN AUTOMÁTICA
# =========================================================================
@router.post("/atender-cliente")
async def atender_cliente(entrada: ConsultaCliente):
    """
    Recibe la pregunta del cliente y TODO el catálogo desde Airtable.
    Actúa como vendedor experto y responde usando SOLO la información del catálogo.
    """
    if not client:
        return {"status": "error", "mensaje": "Falta OPENAI_API_KEY en las variables de entorno."}

    # Convertimos el catálogo a un string bonito para el RAG de GPT-4o
    catalogo_str = json.dumps(entrada.catalogo, indent=2, ensure_ascii=False)

    prompt_sistema = f"""Eres el mejor y más amable vendedor por WhatsApp de un comercio local.
Tu trabajo es responder las consultas de los clientes de manera cordial, persuasiva y siempre orientada a cerrar la venta.

REGLAS ESTRICTAS (Si rompes una, serás penalizado):
1. SOLO puedes vender u ofrecer lo que está en este Catálogo Oficial.
2. Si un cliente pide algo que NO está en el catálogo, dile amablemente que no lo tienes y ofrécele la alternativa más similar que SÍ tengas.
3. PRESTA ATENCIÓN A LA DISPONIBILIDAD. Nunca ofrezcas o prometas un producto cuyo campo 'disponible' sea false (Agotado). Si preguntan por uno agotado, diles que de momento se quedaron sin stock de ese, pero ofréceles otro.
4. Responde corto y directo para WhatsApp (máximo 3 párrafos cortos). Usa emojis con moderación.

CATÁLOGO OFICIAL ACTUAL:
{catalogo_str}
"""

    prompt_usuario = f"Cliente dice: '{entrada.mensaje_cliente}'"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7 # Un poco de creatividad para que suene humano y persuasivo
        )
        
        respuesta_vendedor = response.choices[0].message.content
        return {
            "status": "success",
            "respuesta_whatsapp": respuesta_vendedor
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error respondiendo al cliente: {str(e)}"}
