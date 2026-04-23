FROM nginx:alpine

COPY clientes.html /usr/share/nginx/html/clientes.html
COPY agencia.html /usr/share/nginx/html/agencia.html

# index.html → clientes por defecto
COPY clientes.html /usr/share/nginx/html/index.html

# Config nginx: sirve /clientes y /agencia con redirect desde raiz
RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index clientes.html;\n\
\n\
    location / {\n\
        try_files $uri $uri/ =404;\n\
    }\n\
\n\
    location = / {\n\
        return 302 /clientes.html;\n\
    }\n\
\n\
    location = /admin {\n\
        return 302 /clientes.html;\n\
    }\n\
\n\
    location = /clientes {\n\
        return 302 /clientes.html;\n\
    }\n\
\n\
    location = /agencia {\n\
        return 302 /agencia.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

# Healthcheck usando wget (disponible en nginx:alpine)
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost/ || exit 1

EXPOSE 80
