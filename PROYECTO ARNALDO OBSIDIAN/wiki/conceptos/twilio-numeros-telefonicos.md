---
title: "Twilio — números telefónicos AR/MX para bots de voz"
tags: [voz, twilio, telefonia, kyc, stack-tecnico]
source_count: 1
proyectos_aplicables: [arnaldo, robert, mica]
---

# Twilio — números telefónicos para bots de voz

## Definición

Provider cloud de telefonía. En este ecosistema lo usamos **únicamente**
para comprar números entrantes que conectamos al agente de
[[elevenlabs-conversational-ai]].

**Decisión firme: Twilio antes que SIM físico** salvo casos extremos.
Los SIM físicos requieren gateway GSM, módem 24/7, y no escalan a
múltiples clientes.

## Quién lo usa

A futuro: cada cliente que contrate bot de voz (paga el cliente, no
nosotros).

Los 3 ecosistemas (Arnaldo / Robert / Mica) usan Twilio independiente
— **no compartimos cuenta Twilio** entre clientes porque el KYC y la
facturación son por cliente.

## Cómo comprar número AR

### Requisitos KYC Argentina

Argentina es uno de los países más estrictos de Twilio. Para comprar
número con prefijo argentino:

- DNI o CUIT del titular
- Comprobante de domicilio AR (servicio reciente)
- Justificación de uso ("agente de IA para atención al cliente
  inmobiliario")
- Aprobación: **3-10 días hábiles**

### Pasos

1. https://www.twilio.com → sign up
2. Console → Phone Numbers → Buy a number
3. Country: **Argentina**
4. Capabilities mínimas: **Voice**
5. Subir documentos KYC
6. Esperar aprobación
7. Confirmar pago + activar

### Costo esperado

| Concepto | USD/mes |
|----------|---------|
| Número AR | 1-3 |
| Voice incoming | 0.04 / minuto |
| SMS opcional | 0.02 / mensaje |

## Cómo comprar número MX

México es más rápido que AR (1-3 días):

- RFC mexicano del titular
- Identificación oficial
- Justificación de uso
- Aprobación: 1-3 días

Costo similar a AR.

## Conexión Twilio ↔ ElevenLabs

Una vez aprobado el número:

1. ElevenLabs → Agent → Phone Numbers → Add Number → Twilio
2. Pegar Twilio Account SID + Auth Token (los da Twilio en su console)
3. Seleccionar el número comprado
4. Verificar marcando al número desde otro celular

Si falla:
- Verificar que el agente ElevenLabs esté en estado "active"
- Verificar que el número Twilio tenga capability "Voice"
- Revisar logs en Twilio Console → Monitor → Logs

## Limitaciones conocidas

- **No usar Twilio Trial para producción**: el trial agrega un mensaje
  pre-grabado que arruina la UX.
- **Outbound desde AR**: Twilio AR a veces bloquea calls salientes
  internacionales por defecto.
- **WhatsApp via Twilio**: Twilio también es Tech Provider Meta. Si
  Robert algún día quiere unificar WhatsApp + voz al mismo número
  Twilio se puede, pero hoy WhatsApp Robert usa Meta Graph directo.

## Alternativas a Twilio

Solo evaluar si Twilio rechaza KYC o no tiene cobertura:
- **Plivo** — muy similar, peor latencia en AR
- **Vonage / Nexmo** — más caro
- **MessageBird** — buen soporte EU, débil en LATAM

## Relaciones

- Provider voz para → [[elevenlabs-conversational-ai]]
- Playbook que lo aplica → [[playbooks/worker-voz-elevenlabs]]
- Comparado con → SIM físico + gateway GSM (rechazado por overhead operativo)
