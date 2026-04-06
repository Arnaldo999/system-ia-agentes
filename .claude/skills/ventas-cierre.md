---
name: ventas-cierre
description: Cerrar un lead después de la presentación. Generar la propuesta formal, el seguimiento post-llamada y el brief para pasarle a Dev. Usar cuando el lead mostró interés y hay que convertirlo en cliente.
---

# SKILL: Cierre de Ventas — Post Presentación

## El momento del cierre

El cierre no es un momento, es el resultado natural de una buena presentación.
Si el lead dice "me interesa" o hace preguntas de implementación, el cierre ya empezó.

---

## Paso 1 — Propuesta formal (enviar dentro de las 24hs de la llamada)

Generar una propuesta personalizada para ESE negocio, no genérica.

### Estructura de la propuesta

**Encabezado:**
```
PROPUESTA: [Nombre del negocio]
Preparada por: System IA — Arnaldo Ayala & Micaela Colmenares
Fecha: [fecha]
Válida hasta: [fecha + 7 días]
```

**Sección 1 — Lo que entendimos de tu negocio**
Resumir en 3-4 líneas el dolor principal que mencionó el lead.
Usar SUS palabras. Que cuando lo lea diga "esto es exactamente lo que me pasa".

**Sección 2 — La solución específica para vos**
Describir qué se va a automatizar, sin tecnicismos:
- ❌ "Implementaremos un webhook con FastAPI conectado a Evolution API"
- ✅ "Tu WhatsApp va a responder automáticamente reservas, consultas y pedidos las 24 horas, sin que vos o tu equipo tengan que hacer nada"

**Sección 3 — Qué cambia en tu operación**
3-5 bullets concretos de beneficios:
- "Ya no perdés reservas por no atender el teléfono a las 11pm"
- "Tus clientes reciben confirmación automática — los no-shows bajan hasta un 80%"
- "Sabés en tiempo real cuántas reservas tenés, sin revisar el WhatsApp"

**Sección 4 — Inversión**
| | |
|--|--|
| Setup (configuración inicial) | USD [X] — pago único |
| Mantenimiento mensual | USD [X]/mes |
| Incluye | Soporte, actualizaciones, cambios menores |

Siempre agregar:
> "El setup incluye configuración completa, pruebas y capacitación. Vos no tenés que hacer nada técnico."

**Sección 5 — Próximo paso**
> "Para arrancar, necesito 30 minutos de tu tiempo para darte acceso a WhatsApp Business y completar el perfil del negocio. Del resto nos encargamos nosotros. ¿Arrancamos esta semana?"

---

## Paso 2 — Seguimiento si no responde

### Día 1 después de la llamada (WhatsApp a Micaela para que lo envíe)
> "Hola [nombre]! Te mando la propuesta que prometimos. [adjuntar propuesta] Cualquier duda estamos. ¿La podés ver antes del [día]?"

### Día 3 sin respuesta
> "Hola [nombre], ¿tuviste oportunidad de ver la propuesta? Si tenés alguna duda o querés ajustar algo, con gusto la conversamos."

### Día 7 sin respuesta
> "Hola [nombre], sé que andás ocupado. La propuesta vence el [fecha]. Si no es el momento, sin problema — podemos hablar cuando quieras. ¿Preferís que te contacte la semana que viene?"

**Regla:** máximo 3 seguimientos. Si no responde al tercero, el lead pasa a "frío" en el CRM.

---

## Paso 3 — Cuando el lead dice SÍ

### Información a recopilar para el brief técnico

Completar `handoff/brief-[nombre-cliente].md` con:

```markdown
# BRIEF: [Nombre del Negocio]
**Fecha:** [fecha]
**Contacto:** [nombre, WhatsApp, email]
**Nicho:** [gastronomia / salud / comercio / automotriz / servicios]

## Servicio contratado
- [ ] Bot WhatsApp (reservas / pedidos / consultas / menú)
- [ ] Agendamiento Cal.com + WhatsApp
- [ ] Redes sociales (publicación automática)
- [ ] Redes sociales (respuesta a comentarios IG/FB)
- [ ] RAG / Base de conocimiento
- [ ] Sitio web / Landing

## Detalles del negocio
- Nombre comercial:
- Servicio principal:
- Tono de voz del bot: [formal / cercano / neutro]
- Horarios de atención:
- Cosas que el bot NO debe decir o hacer:

## Canales a conectar
- WhatsApp Business: [número]
- Instagram: [usuario]
- Facebook: [página]
- Otros:

## Presupuesto acordado
- Setup: USD [X]
- Mensual: USD [X]

## Deadline acordado
- Entrega: [fecha]

## Notas importantes
[cualquier particularidad del negocio]
```

### Actualizar ai.context.json
```json
{
  "agente_activo": "orquestador",
  "proyecto_actual_system_ia": {
    "cliente": "[nombre]",
    "tipo_automatizacion": "[tipo]",
    "fase": "brief",
    "estado": "en_progreso"
  }
}
```

---

## Precios de referencia (orientativos)

| Servicio | Setup | Mensual |
|---------|-------|---------|
| Bot WhatsApp básico (1 flujo) | USD 300 | USD 80 |
| Bot WhatsApp completo (reservas + pedidos + menú) | USD 600 | USD 120 |
| Agendamiento Cal.com + WhatsApp | USD 250 | USD 60 |
| Redes sociales publicación automática | USD 200 | USD 50 |
| Redes sociales publicación + respuesta comentarios | USD 400 | USD 100 |
| Pack completo (WhatsApp + Redes) | cotizar | cotizar |

**Descuento de lanzamiento:** para primeros clientes se puede ofrecer hasta 20% off en el setup.
**Nunca** bajar el mensual — es el ingreso recurrente de la agencia.

---

## Señales de alerta — cuándo NO cerrar

- El lead pide "hacerlo gratis para ver cómo funciona" → no. Ofrecerle la demo, no un proyecto gratuito.
- El lead quiere pagar solo si "funciona" → definir qué significa "funciona" antes de arrancar, o no arrancar.
- El lead no tiene tiempo para darte 30 minutos de onboarding → el proyecto va a fracasar. Necesita compromiso mínimo.
