#!/bin/bash
# Levanta el servidor de Nuestra Iglesia
# Uso:
#   ./run.sh                   # usa .env si existe, sino modo demo
#   GEMINI_API_KEY=xxx ./run.sh   # API key inline
#   LLM_PROVIDER=demo ./run.sh    # forzar modo demo (sin LLM)

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[init] Creando virtualenv..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -r requirements.txt
else
  source .venv/bin/activate
fi

# Cargar .env si existe
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

export FREESHOW_URL="${FREESHOW_URL:-http://localhost:5506}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.0-flash}"

if [ -z "$GEMINI_API_KEY" ] && [ "$LLM_PROVIDER" != "demo" ]; then
  echo ""
  echo "⚠️  GEMINI_API_KEY vacío — corriendo en modo demo (heurística sin LLM)"
  echo "    Para activar IA real: copiá .env.example a .env y poné tu API key"
  echo "    https://aistudio.google.com/apikey (gratis)"
  export LLM_PROVIDER="demo"
fi

echo ""
echo "════════════════════════════════════════════════"
echo "  NUESTRA IGLESIA — Sistema de presentación IA"
echo "════════════════════════════════════════════════"
echo "  LLM:        ${LLM_PROVIDER:-demo}"
echo "  Modelo:     $GEMINI_MODEL"
echo "  Freeshow:   $FREESHOW_URL"
echo ""
echo "  Panel operador:   http://localhost:8000/"
echo "  Pantalla pública: http://localhost:8000/publico"
echo "════════════════════════════════════════════════"
echo ""

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
