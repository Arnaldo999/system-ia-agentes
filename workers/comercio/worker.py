import os
import json
import requests
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from openai import OpenAI

router = APIRouter(prefix="/comercio", tags=["Comercio WhatsApp"])

# La API key se tomará del entorno de Easypanel
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Instanciamos el cliente de OpenAI.
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

class MensajeWhatsApp(BaseModel):
    mensaje: str
    es_admin: bool
    airtable_api_key: str
    airtable_base_id: str
    airtable_table: str


# =========================================================================
# FUNCIONES AUXILIARES DE AIRTABLE (Usa la API nativa sin SDK externos)
# =========================================================================
def leer_catalogo_airtable(api_key: str, base_id: str, table: str):
    url = f"https://api.airtable.com/v0/{base_id}/{table}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("records", [])
    return []

def guardar_producto_airtable(api_key: str, base_id: str, table: str, datos: dict):
    url = f"https://api.airtable.com/v0/{base_id}/{table}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"records": [{"fields": datos}]}
    resp = requests.post(url, headers=headers, json=payload)
    return resp.status_code == 200

def actualizar_producto_airtable(api_key: str, base_id: str, table: str, record_id: str, datos: dict):
    url = f"https://api.airtable.com/v0/{base_id}/{table}/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"fields": {"Disponible": datos.get("Disponible")}}
    resp = requests.patch(url, headers=headers, json=payload)
    return resp.status_code == 200


# =========================================================================
# RUTAS DE COMERCIO (ÚNICO ENDPOINT ORQUESTADOR)
# =========================================================================
@router.post("/procesar-whatsapp")
async def procesar_whatsapp(entrada: MensajeWhatsApp):
    """
    Recibe TODO desde n8n (El Pasamanos).
    Actúa como Orquestador Maestro decidiendo si es dueño o cliente, y leyendo/escribiendo en Airtable.
    Retorna la respuesta literal para enviar por WhatsApp.
    """
    if not client:
        return {"status": "error", "mensaje": "Falta OPENAI_API_KEY en Easypanel."}

    catalogo_records = leer_catalogo_airtable(entrada.airtable_api_key, entrada.airtable_base_id, entrada.airtable_table)
    
    # -------------------------------------------------------------
    # RUTA A: ES EL DUEÑO GESTIONANDO EL CATÁLOGO
    # -------------------------------------------------------------
    if entrada.es_admin:
        # 1. GPT-4o extrae la intención del dueño
        prompt_admin = f"""El dueño de la tienda envía este mensaje para gestionar su catálogo (Airtable).
        NO usamos stock numérico, solo estado "Disponible" o "No Disponible".

        MENSAJE DEL DUEÑO: "{entrada.mensaje}"

        Extrae la información en JSON estricto:
        {{
          "accion": "crear_producto" | "actualizar_disponibilidad" | "desconocida",
          "datos": {{
            "Producto": "Nombre claro del producto",
            "Precio": 120 (numero, opcional),
            "Disponible": "Disponible" | "No Disponible" (string exactamente así)
          }}
        }}"""
        
        try:
            resp_openai = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt_admin}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            data_gpt = json.loads(resp_openai.choices[0].message.content)
            accion = data_gpt.get("accion")
            datos_producto = data_gpt.get("datos", {})
            producto_nombre = datos_producto.get("Producto", "").lower()

            if accion == "crear_producto":
                guardar_producto_airtable(entrada.airtable_api_key, entrada.airtable_base_id, entrada.airtable_table, datos_producto)
                return {"status": "success", "respuesta_whatsapp": f"✅ Producto '{datos_producto.get('Producto')}' guardado en el catálogo como {datos_producto.get('Disponible')}."}
            
            elif accion == "actualizar_disponibilidad":
                # Buscar producto en el catálogo actual para obtener su ID
                record_id_encontrado = None
                for record in catalogo_records:
                    if producto_nombre in record["fields"].get("Producto", "").lower():
                        record_id_encontrado = record["id"]
                        break
                
                if record_id_encontrado:
                    actualizar_producto_airtable(entrada.airtable_api_key, entrada.airtable_base_id, entrada.airtable_table, record_id_encontrado, datos_producto)
                    return {"status": "success", "respuesta_whatsapp": f"✅ Stock actualizado. '{datos_producto.get('Producto')}' ahora está {datos_producto.get('Disponible')}."}
                else:
                    return {"status": "success", "respuesta_whatsapp": f"❌ No encontré '{datos_producto.get('Producto')}' en el catálogo para actualizarlo."}
            else:
                return {"status": "success", "respuesta_whatsapp": "🤖 No entendí qué quieres hacer con el catálogo."}
        
        except Exception as e:
            return {"status": "error", "respuesta_whatsapp": f"Error interno: {str(e)}"}

    # -------------------------------------------------------------
    # RUTA B: ES EL CLIENTE REALIZANDO CONSULTAS
    # -------------------------------------------------------------
    else:
        # Simplificar el catálogo para que GPT-4o lo lea fácil (lista de diccionarios)
        catalogo_limpio = [r["fields"] for r in catalogo_records]
        catalogo_str = json.dumps(catalogo_limpio, indent=2, ensure_ascii=False)

        prompt_sistema = f"""Eres el mejor vendedor por WhatsApp de un comercio local.
        Responde corto y directo para WhatsApp. Usa emojis con moderación.

        REGLAS ESTRICTAS:
        1. SOLO ofrece lo que está "Disponible" en este Catálogo Oficial.
        2. Si un cliente pide algo que es "No Disponible" o no existe, dile amablemente que no hay y ofrece una alternativa que SÍ exista.

        CATÁLOGO OFICIAL:
        {catalogo_str}"""

        prompt_usuario = f"Cliente dice: '{entrada.mensaje}'"

        try:
            resp_openai = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario}
                ],
                temperature=0.7
            )
            return {
                "status": "success",
                "respuesta_whatsapp": resp_openai.choices[0].message.content
            }
        except Exception as e:
            return {"status": "error", "respuesta_whatsapp": "Perdón, tengo problemas técnicos."}
