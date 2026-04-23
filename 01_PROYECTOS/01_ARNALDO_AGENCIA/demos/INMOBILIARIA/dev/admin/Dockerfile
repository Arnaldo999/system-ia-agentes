FROM nginx:alpine

# Copiar archivos HTML
COPY clientes.html /usr/share/nginx/html/clientes.html
COPY agencia.html /usr/share/nginx/html/agencia.html
COPY clientes.html /usr/share/nginx/html/index.html

# Usar config nginx desde archivo (evita problemas con escape en printf)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Healthcheck via wget (disponible en nginx:alpine)
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://localhost/clientes.html || exit 1

EXPOSE 80
