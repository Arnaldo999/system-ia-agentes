# Setup Email Automation — Recordatorios Estudio Jurídico Demo

> Pedido de Mica (2026-04-26): "Fíjate de poder también automatizar el envío de correos electrónicos cada cierto día"

## Caso de uso

Cuando se envía una **Comunicación de Oposición** a un cliente y este NO responde en X días, el sistema debe enviar **recordatorios automáticos por email** hasta que responda o venza el plazo.

Misma lógica aplica a:
- Propuestas Pendientes sin respuesta del cliente
- Trámites con vencimiento próximo (DJUM, Renovación)
- Marcas con plazo de oposición vencido

## Stack propuesto

```
Coolify (Hostinger Arnaldo)
  ├─ FastAPI backend (Python)  ← endpoint /crm/email-recordatorio/dispatch
  └─ n8n (n8n.arnaldoayalaestratega.cloud)
       └─ Workflow "Recordatorios Estudio Marcas"
            ├─ Schedule cron: cada 24hs a las 09:00 ART
            ├─ HTTP Request → backend /comunicaciones?estado=Enviada&sin_respuesta_dias=3
            ├─ Loop cada item
            ├─ Send Email (SMTP del estudio)
            └─ HTTP Request → backend /comunicaciones/{id}/marcar-recordatorio-enviado
```

## Tabla nueva sugerida en Airtable: `Email_Recordatorios`

| Campo | Tipo |
|-------|------|
| Comunicación origen | Link to Comunicaciones_Oposicion |
| Cliente | Link to Clientes_Estudio |
| Email destinatario | Email |
| Tipo recordatorio | Single select (Sin respuesta 3d / 7d / 15d / Plazo vence en 5d) |
| Fecha envío | Date/time |
| Asunto | Single line text |
| Cuerpo enviado | Long text |
| Estado | Single select (Enviado / Abierto / Falló) |

## Reglas de envío

| Días sin respuesta | Acción |
|--------------------|--------|
| 3 días | Recordatorio amable: "Tu opinión es importante para que avancemos" |
| 7 días | Recordatorio con urgencia: "Plazo legal vence en X días" |
| 15 días | Aviso final + copia al abogado responsable |
| Sin acción 30+ días | Marcar comunicación como "Sin respuesta" + alerta WhatsApp al estudio |

## Endpoint backend a crear

```python
@router.get("/crm/comunicaciones/sin-respuesta")
def comunicaciones_sin_respuesta(dias: int = Query(3, ge=1, le=60)):
    formula = f"AND({{Estado}}='Enviada',IS_BEFORE({{Fecha Envío}},DATEADD(NOW(),-{dias},'days')),NOT({{Fecha Respuesta}}))"
    items = _list(TABLE_COMUNICACIONES, filterByFormula=formula)
    return {"comunicaciones": items}
```

## Workflow n8n a crear

ID propuesto: `juridico-recordatorios-email`
Schedule: `0 12 * * *` (UTC, = 09:00 ART)
Nodos:
1. **Cron Trigger**: cada día a las 09:00 ART
2. **HTTP Request**: GET `/clientes/system_ia/demos/juridico/crm/comunicaciones/sin-respuesta?dias=3`
3. **Loop Over Items**
4. **Code (JS)**: armar asunto + cuerpo HTML según `dias_sin_respuesta`
5. **Send Email** (SMTP - configurar credencial del estudio)
6. **HTTP Request**: POST a `/crm/email-recordatorios` para registrar envío
7. **Conditional**: si fallo → notificar Telegram al estudio

## Templates de email (placeholders)

### 3 días sin respuesta
```
Subject: Recordatorio: tu marca {{marca_cliente}} requiere tu decisión

Hola {{nombre_cliente}},

Te recordamos que el {{fecha_envio}} te enviamos una comunicación sobre la marca
de un tercero ({{marca_tercero}}) que podría afectar tu marca {{marca_cliente}}.

Esperamos tu respuesta para avanzar con la oposición. Tenés tiempo hasta el
{{fecha_limite}}.

Cualquier duda, respondenos este email o llamanos al {{telefono_estudio}}.

Saludos,
Estudio Demo - Propiedad Intelectual
```

### 7 días sin respuesta (urgencia)
```
Subject: ⚠️ Urgente: tu plazo legal vence pronto - {{marca_cliente}}

Hola {{nombre_cliente}},

Hace 7 días te enviamos información sobre una posible oposición a tu marca
{{marca_cliente}}. El plazo legal para presentarla vence el {{fecha_limite}}.

Si NO respondemos a tiempo, perdés la posibilidad de oponerte y la marca
{{marca_tercero}} podrá registrarse libremente, lo que podría:
- Generar confusión con tu marca
- Limitar tu expansión
- Afectar el valor comercial de tu marca registrada

Necesitamos tu decisión URGENTE. Respondé este email con SI o NO.

Saludos,
{{abogado_responsable}}
Estudio Demo - Propiedad Intelectual
```

## Sub-pasos cuando se vaya a implementar real

- [ ] Conseguir SMTP del estudio (Gmail OAuth o SES)
- [ ] Validar templates con Mica + cliente
- [ ] Crear tabla `Email_Recordatorios` en Airtable
- [ ] Agregar endpoint `/crm/comunicaciones/sin-respuesta` al router
- [ ] Agregar endpoint `POST /crm/email-recordatorios` para bitácora
- [ ] Crear workflow n8n con cron + SMTP
- [ ] Test E2E: enviar a un email del estudio
- [ ] Activar en producción
- [ ] Monitorear primer envío real

## Estado actual

🔴 **NO implementado todavía** — solo está el botón "⚙️ Configurar recordatorios" en la pantalla de Comunicaciones (Mock).

Cuando Mica confirme que avanzamos, la integración toma ~2-3h de trabajo.
