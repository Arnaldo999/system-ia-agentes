# FAQ — Lovbot Inmobiliaria (Knowledge Base ElevenLabs)

> Documento que se sube a la **Knowledge Base** del agente de voz en
> ElevenLabs. Cubre las preguntas más frecuentes que aparecen al hablar
> con un cliente real, sintetizadas del comportamiento del bot WhatsApp
> demo (`workers/demos/inmobiliaria/`) y del worker Robert.

---

## Sobre la empresa

**Nombre comercial**: Lovbot Inmobiliaria (placeholder — se reemplaza por
el del cliente real cuando se duplique el agente).

**Ciudad principal**: Posadas, Misiones, Argentina (ajustable por cliente).

**Asesor a cargo**: Roberto (ajustable por cliente).

**Horario de atención humana**: lunes a viernes de 9 a 18 hs, hora
Argentina. Fuera de ese horario el agente toma datos y un humano
devuelve el contacto al día siguiente hábil.

**Canales disponibles**:
- WhatsApp (bot conversacional)
- Llamada telefónica (este agente de voz)
- Visita presencial agendada vía Cal.com

---

## Tipos de propiedades en cartera

El catálogo se consulta en tiempo real desde la base de datos. Las
categorías estándar son:

- **Casa** — vivienda unifamiliar
- **Departamento** — unidad en edificio
- **PH** — propiedad horizontal con entrada independiente
- **Lote / Terreno** — sin construcción, generalmente en loteos
- **Local comercial** — fondo de comercio o local a estrenar

**Operaciones**:
- **Venta** — compra definitiva
- **Alquiler** — contrato mensual con índice IPC/ICL/UVA según el caso

---

## Zonas que cubrimos

Las zonas exactas dependen del cliente (vienen en la variable
`INMO_DEMO_ZONAS`). Para Lovbot demo principal: Posadas Centro,
Posadas Sur, Garupá, Candelaria, alrededores de la capital misionera.

Si el cliente pregunta por una zona que no manejamos, el agente debe
proponer alternativas cercanas o tomar el dato y derivar.

---

## Rangos de precio (usados como filtros internos)

| Bucket | Rango USD |
|--------|-----------|
| `hata_50k` | hasta 50.000 |
| `50k_100k` | 50.000 a 100.000 |
| `100k_200k` | 100.000 a 200.000 |
| `mas_200k` | más de 200.000 |

Para alquileres, los rangos son en moneda local mensual y se conversa
caso por caso.

---

## Proceso de compra (alto nivel)

1. **Selección de propiedad** — cliente elige entre el catálogo o pide
   al agente que filtre por sus criterios.
2. **Visita presencial** — se agenda con Cal.com. El agente confirma
   día, hora y manda confirmación por correo.
3. **Reserva** — seña inicial (en Argentina típicamente 5-10% del
   precio de venta).
4. **Boleto de compraventa** — firma con escribano designado por
   alguna de las partes.
5. **Escritura** — entre 30 y 60 días posteriores al boleto.

El agente NO maneja precios definitivos ni firma documentos. Toma
intención, agenda visita y deriva al asesor humano para todo lo
contractual.

---

## Proceso de alquiler (alto nivel)

1. **Selección** — el cliente filtra por zona, tipo, presupuesto.
2. **Visita** — agendada con Cal.com igual que en venta.
3. **Documentación** — DNI, recibos de sueldo, garantía propietaria
   o seguro de caución.
4. **Firma de contrato** — escribano / corredor.
5. **Entrega de llaves** — fecha pactada.

---

## Preguntas frecuentes (respuestas que el agente puede usar tal cual)

### "¿Tienen disponibilidad para visitar mañana?"

> "Déjame consultar la agenda un segundo."
>
> *(El agente llama a `disponibilidad`. Lee los 2-3 horarios más
> cercanos de los slots devueltos.)*

### "¿Cuánto cuesta el departamento que vi en su web?"

> El agente NO inventa precios. Pide más detalles (zona, dormitorios)
> para llamar a `buscar_propiedad` y recién ahí cita el precio que
> retorna el catálogo.

### "¿Aceptan financiación / crédito hipotecario?"

> "Trabajamos con compradores que vienen con financiación de su banco
> y también ayudamos a coordinar tasaciones cuando hace falta. ¿Querés
> que te derive con un asesor para ver tu caso particular?"

### "¿Dónde están ubicados? / ¿Tienen oficina física?"

> "Nuestra oficina está en [CIUDAD]. Si querés acercarte te coordino
> un horario con un asesor."

### "¿Quién me va a atender después de esta llamada?"

> "Te va a atender [NOMBRE_ASESOR] o un asesor del equipo. Te llega un
> correo con la confirmación de la visita y los datos de contacto."

### "No puedo en ese horario, ¿hay otro?"

> El agente vuelve a llamar `disponibilidad` con `dias=14` para ampliar
> el rango.

### "¿Aceptan dólares para reserva?"

> "Sí, las reservas en venta generalmente son en dólares billete o
> transferencia. Para los detalles del pago te conviene hablar con un
> asesor."

### "¿Tienen propiedades en pozo / preventa?"

> "Sí, en algunos loteos manejamos lotes en pozo. Decime qué zona te
> interesa y te muestro qué hay disponible."

### "Quiero hablar con una persona real."

> "Perfecto, te tomo los datos rápido y te llamamos en horario hábil.
> ¿Cuál es tu nombre completo?"
>
> *(Toma nombre + email + motivo + agenda visita o callback)*

---

## Reglas de tono (importante para el system prompt)

- Hablar **vos**, no usted (Argentina). Si detecta acento mexicano,
  cambia a "tú".
- Frases cortas: voz no tolera párrafos largos.
- Confirmar email **letra por letra** siempre.
- Confirmar fecha y hora antes de agendar.
- Si el cliente está apurado o molesto: ofrecer derivar a humano.
- Nunca inventar precios, disponibilidad ni datos del cliente.
- No prometer cierres comerciales (eso lo hace el asesor humano).

---

## Lo que el agente NO debe hacer

- Cerrar venta o alquiler (eso es del asesor humano).
- Citar precios sin haber consultado el catálogo (vía tool
  `buscar_propiedad`).
- Aceptar reservas o pagos por teléfono.
- Comprometer condiciones contractuales.
- Hablar de comisiones, honorarios o impuestos en detalle (deriva).
- Discutir con el cliente — siempre proponer derivar a humano si la
  conversación se traba.

---

## Datos a capturar siempre antes de cerrar la llamada

Ordenado por importancia:

1. **Nombre completo**
2. **Teléfono de contacto** (idealmente el `caller_id` ya lo tenemos)
3. **Email** (deletreado letra por letra y confirmado)
4. **Tipo de propiedad** (casa / depto / lote / etc.)
5. **Operación** (venta / alquiler)
6. **Zona de interés**
7. **Presupuesto aproximado**
8. **Urgencia** (esta semana / este mes / sin apuro)

Estos campos alimentan el scoring BANT que clasifica el lead como
caliente / tibio / frío.
