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

# Deshabilitar healthcheck de Docker — Coolify usa su propio mecanismo
# nginx:alpine no tiene wget/curl para el check interno por defecto
HEALTHCHECK NONE

EXPOSE 80
