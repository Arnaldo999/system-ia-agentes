FROM nginx:alpine

# Copiar el CRM modelo y sus JS bundles
COPY crm-v2.html /usr/share/nginx/html/dev/crm-v2.html
COPY js /usr/share/nginx/html/dev/js

# Catch-all: crm.lovbot.ai/ sirve directo el CRM v2
COPY crm-v2.html /usr/share/nginx/html/index.html

# Config nginx dedicada para el CRM
COPY nginx.crm.conf /etc/nginx/conf.d/default.conf

# Healthcheck via wget con IP explícita
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1

EXPOSE 80
