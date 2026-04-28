# Nuestra Iglesia — Software de presentación inteligente

Sistema de presentación con detección automática de referencias bíblicas y sincronización de letras de canciones, usando **Gemma 4 local** + **Freeshow** + **FastAPI**.

> Cliente: Pastor Pablo (Café Nueva Vida / Nuestra Iglesia)
> Tipo: pro-bono / caso de estudio para referidos
> Estado: DEMO funcional. Pendiente discovery sábado para adaptar a hardware iglesia.

## Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│                    PC OPERADOR DE IGLESIA                     │
│                                                                │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │  Audio del  │───▶│   Gemma 4    │───▶│   Backend       │  │
│  │   Pastor    │    │  multimodal  │    │   FastAPI       │  │
│  │ (consola→PC)│    │  (Ollama)    │    │   (Python)      │  │
│  └─────────────┘    └──────────────┘    └────────┬────────┘  │
│                                                   │           │
│                          ┌────────────────────────┼─────┐    │
│                          ▼                        ▼     ▼    │
│                  ┌──────────────┐        ┌──────────┐ ┌────┐ │
│                  │   Panel      │        │ Pantalla │ │FS  │ │
│                  │  Operador    │        │  Pública │ │API │ │
│                  │  (HTML)      │        │  (HTML)  │ │    │ │
│                  └──────────────┘        └────┬─────┘ └─┬──┘ │
└───────────────────────────────────────────────┼─────────┼────┘
                                                ▼         ▼
                                       ┌────────────────────┐
                                       │  PANTALLA GIGANTE  │
                                       │  (proyector / LED) │
                                       └────────────────────┘
```

## Modo de uso

### Demo (sin dependencias externas) — para mostrar el sábado

```bash
./run.sh
```

Esto levanta el servidor en `http://localhost:8000/` con:
- **Panel operador**: `http://localhost:8000/`
- **Pantalla pública**: `http://localhost:8000/publico` (abrir en monitor secundario o pantalla externa)

En modo demo:
- Funciona el botón "Simular Pastor" con detección heurística (sin Gemma)
- Funciona el listado de versículos y canciones
- Funciona la pantalla pública con WebSocket en tiempo real
- NO requiere Ollama ni Freeshow corriendo

### Modo live (con Gemma 4 + Freeshow)

1. Instalar Ollama y Gemma 4:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull gemma4:4b
   ollama serve  # corre en localhost:11434
   ```

2. Instalar Freeshow desde https://freeshow.app y activar API en Settings → Connections (puerto 5506).

3. Levantar el backend:
   ```bash
   DEMO_MODE=false ./run.sh
   ```

El badge superior pasará de "DEMO" (amarillo) a "LIVE" (verde) cuando ambos servicios estén disponibles.

## Para el sábado en la iglesia (demo flow)

1. **Llegar 15 min antes**, abrir el panel operador en notebook + conectar la pantalla pública a un monitor o TV externo (HDMI).
2. **Mostrar la pantalla idle** durante el saludo inicial (logo "Nuestra Iglesia" con efecto sutil).
3. **Demo manual**: click en cualquier versículo de la lista → aparece en pantalla pública con animación + tipografía grande. Comentar: "esto es lo que pasa cuando el operador busca y manda. Ahora viene la magia."
4. **Demo automática**: en el cuadro "Simular Pastor", click en alguno de los ejemplos rápidos (ej: "Abramos en Juan 3:16"). Se detecta solo y aparece. Comentar: "esto sería el Pastor hablando — Gemma 4 escucha y dispara."
5. **Demo de canciones**: abrir "Cuán grande es Él", click en líneas. La pantalla pública anima con la línea anterior arriba en gris, la actual grande en blanco, la siguiente abajo en gris. Comentar: "esto sigue al cantante en vivo — Gemma 4 escucha la voz del director y avanza."
6. **No prometer fechas**. Decir: "esto es la base. Lo que sigue es adaptarlo al hardware de ustedes y entrenar al equipo."

## Estructura del proyecto

```
software/
├── backend/
│   └── main.py              # FastAPI: detección + presentación + WebSockets
├── frontend/
│   ├── operador.html        # Panel de control (notebook del operador)
│   └── publico.html         # Pantalla gigante (proyector/TV)
├── data/
│   ├── versiculos.json      # 12 versículos populares en RV1960
│   └── canciones.json       # 3 canciones de adoración
├── docs/
├── requirements.txt
├── run.sh                   # Script de arranque
└── README.md                # Este archivo
```

## Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET    | `/estado`                 | Estado de Ollama, Freeshow, conexiones |
| GET    | `/datos/versiculos`       | Biblioteca de versículos cargados |
| GET    | `/datos/canciones`        | Repertorio cargado |
| POST   | `/detectar/texto`         | Detecta referencia/canción en texto transcripto |
| POST   | `/presentar/versiculo`    | Muestra versículo en pantalla pública + Freeshow |
| POST   | `/presentar/letra`        | Muestra línea de canción |
| POST   | `/presentar/limpiar`      | Limpia la pantalla |
| POST   | `/demo/simular-pastor`    | Simula que el Pastor habla (detección + presentación) |
| WS     | `/ws/operador`            | WebSocket para panel operador |
| WS     | `/ws/publico`             | WebSocket para pantalla pública |

## Datos de ejemplo cargados

### Versículos (12)
- Juan 3:16, Salmo 23:1, Salmo 23:4, Romanos 8:28
- Filipenses 4:13, Proverbios 3:5, Jeremías 29:11
- Mateo 6:33, 1 Corintios 13:4, Efesios 2:8
- Salmo 91:1, Isaías 41:10

### Canciones (3)
- Cuán grande es Él (tradicional)
- Renuévame Señor Jesús (Marcos Witt)
- Te doy gloria (Marco Barrientos)

## Próximos pasos post-discovery

Después del sábado, completar:
1. Importar la base bíblica completa que use la iglesia (RV1960 / NVI / etc) según Sección 3 del discovery
2. Cargar el repertorio real de canciones de la iglesia (cuántas, en qué formato vienen)
3. Adaptar tipografía/colores a la identidad visual de la iglesia
4. Conectar audio real del Pastor (consola → tarjeta USB → backend)
5. Configurar Gemma 4 en la PC del operador (o mini-PC dedicado si no rinde)
6. Entrenamiento al equipo de medios (1 sesión)
