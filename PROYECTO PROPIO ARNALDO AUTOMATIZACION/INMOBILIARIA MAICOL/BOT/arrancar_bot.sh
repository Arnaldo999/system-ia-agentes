#!/bin/bash
# Arranca el bot de Inmobiliaria Maicol en puerto 8001

cd "$(dirname "$0")"

# Cargar variables de entorno
if [ -f .env.bot ]; then
    export $(grep -v '^#' .env.bot | grep -v '^$' | xargs)
fi

# Crear venv si no existe
if [ ! -d venv_bot ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv_bot
    venv_bot/bin/pip install -q -r requirements_bot.txt
fi

echo "🏠 Arrancando Bot Inmobiliaria Maicol en puerto 8001..."
echo "   Health: http://localhost:8001/health"
echo "   Propiedades: http://localhost:8001/inmobiliaria/propiedades"
echo ""

venv_bot/bin/python bot_whatsapp.py
