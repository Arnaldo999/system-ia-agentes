#!/bin/bash
# check_secrets.sh
# Un script simple para detectar posibles tokens o secretos hardcodeados antes del commit.

echo "Revisando posibles secretos en scripts de pruebas..."

matches=$(grep -rE "(EAAM[a-zA-Z0-9]+|pat[A-Za-z0-9]{15,}|Bearer [a-zA-Z0-9\-\._~+/]+=*|['\"]549[0-9]{10,}['\"])" scripts/ tests/ tools/ 2>/dev/null)

if [ -n "$matches" ]; then
    echo "⚠️  ATENCIÓN: Se encontraron posibles secretos o números de teléfono hardcodeados:"
    echo "$matches"
    echo ""
    echo "Por favor, reemplaza estos valores por os.getenv('VARIABLE_NAME') y configúralos en tu archivo .env."
    exit 1
else
    echo "✅ No se detectaron secretos hardcodeados (Regex básica)."
    exit 0
fi
