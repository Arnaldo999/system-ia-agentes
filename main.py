from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agente System IA", description="Microservicio base para Flujos Agénticos en n8n")

class AgentRequest(BaseModel):
    mensaje: str
    cliente_id: str = "anonimo"

@app.get("/")
def read_root():
    return {"status": "online", "message": "¡Agente System IA vivo en Easypanel!"}

@app.post("/procesar")
def procesar_mensaje(req: AgentRequest):
    # Aquí iría nuestra lógica pesada de IA (OpenAI, Langchain, etc.)
    # Por ahora solo es una demo:
    respuesta_simulada = f"Recibí el mensaje '{req.mensaje}' del cliente {req.cliente_id}."
    return {"status": "success", "response": respuesta_simulada, "agent_thought": "Este es un mensaje procesado por mi microservicio externo."}
