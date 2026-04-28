# Planes y servicios — Lovbot Inmobiliaria

> Documento complementario para la Knowledge Base del agente de voz.
> Describe los servicios que la inmobiliaria ofrece y cómo el agente
> puede mencionarlos sin inventar nada.

---

## Servicios principales

### 1. Venta de propiedades

Casa, departamento, PH, lote, local comercial. El agente busca en el
catálogo en tiempo real con `buscar_propiedad` filtrando por:

- Tipo
- Operación = `venta`
- Zona
- Bucket de presupuesto

Cada propiedad devuelta incluye precio, dormitorios, metros, dirección,
imagen y mapa.

### 2. Alquileres

Operación = `alquiler`. Mismo flujo que venta, pero el rango de precio
suele ser mensual en moneda local. Trabajamos contratos con índice
IPC, ICL o UVA según la propiedad.

### 3. Loteos / desarrollos

Para clientes que sean desarrolladores inmobiliarios, el catálogo
incluye lotes individuales con coordenadas en mapa (`lotes_mapa`) y
estados (disponible / reservado / vendido).

### 4. Visitas guiadas

Agendadas con Cal.com (cuenta compartida de Arnaldo). El agente reserva
el horario y el asesor humano hace la visita presencial.

### 5. Tasaciones

El agente NO tasa propiedades. Si el cliente pregunta:

> "Las tasaciones las hace nuestro equipo después de visitar la
> propiedad. ¿Te coordino una visita con un tasador?"

---

## Lo que vendemos como agencia

(esto es lo que **Lovbot ofrece a inmobiliarias**, no lo que la inmobiliaria
vende a sus clientes finales — solo es relevante si el cliente que llama
está interesado en contratar el sistema, no en comprar propiedad)

- Bot WhatsApp + bot voz integrados al CRM
- CRM web con catálogo, leads, visitas, scoring BANT
- Panel de gestión para asesores
- Integración con Cal.com para agendamiento
- Notificaciones automáticas al equipo
- Reportes mensuales de leads y conversiones

Si alguien llama preguntando por contratar el sistema, el agente debe:

> "Para temas de contratación del sistema te paso con el equipo
> comercial. ¿Me dejás tu nombre y un correo?"

Y agenda llamada / toma datos.

---

## Rangos típicos de precio (para referencia interna del agente)

Estos son rangos del mercado argentino general — el agente NO los cita
como precios de la inmobiliaria. Solo le sirven para entender el
contexto cuando un cliente dice "tengo 80 mil".

| Tipo | Venta | Alquiler mensual |
|------|-------|------------------|
| Departamento 2 amb usado | USD 35.000 - 80.000 | ARS 200.000 - 500.000 |
| Departamento 3 amb | USD 60.000 - 150.000 | ARS 300.000 - 700.000 |
| Casa con terreno | USD 80.000 - 250.000 | ARS 400.000 - 1.500.000 |
| Lote urbanizado | USD 15.000 - 60.000 | — |
| Lote en pozo | USD 8.000 - 25.000 | — |

Estos rangos son aproximados y dependen mucho de zona, antigüedad,
amenities. **El precio real siempre lo da el catálogo en tiempo real.**

---

## Comisiones y honorarios

El agente NO discute comisiones por teléfono. Si el cliente pregunta:

> "Nuestras comisiones son las que marca el COCIRMI / colegio
> profesional, los detalles te los explica el asesor en la visita."

(COCIRMI = Colegio de Corredores Inmobiliarios de Misiones; el agente
puede ajustar el nombre del colegio según provincia del cliente real.)

---

## Documentación que pedimos al cliente

Para **comprar**:
- DNI vigente
- Constancia de CUIL/CUIT
- Justificación de fondos (en operaciones grandes)

Para **alquilar**:
- DNI
- Recibos de sueldo (últimos 3) o monotributo
- Garantía propietaria de la provincia, garante o seguro de caución
- Antecedentes laborales

El agente toma nota de qué tiene el cliente y lo manda como contexto
al asesor humano. NO valida documentación.
