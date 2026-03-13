# Debug y errores frecuentes

HTTP Request n8n: JSON parameter needs to be valid JSON
- Causa: JSON body pegado como literal o con prefijo incorrecto (por ejemplo "=={{").
- Solucion: usar modo Expression y un prefijo unico "={{...}}".
