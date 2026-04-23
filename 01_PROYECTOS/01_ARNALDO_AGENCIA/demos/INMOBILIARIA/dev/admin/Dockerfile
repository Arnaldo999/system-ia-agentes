FROM nginx:alpine

# Copiar archivos HTML
COPY clientes.html /usr/share/nginx/html/clientes.html
COPY agencia.html /usr/share/nginx/html/agencia.html
COPY clientes.html /usr/share/nginx/html/index.html

# Usar config nginx desde archivo (evita problemas con escape en printf)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Healthcheck via wget con IP explícita (127.0.0.1) y sin --spider
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1/clientes.html || exit 1

EXPOSE 80
