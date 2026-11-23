# nginx gateway: serves the Dimora web client and routes /api to the service that owns each resource.
# Build from the repository root (Compose does this) to include website-studio/.
FROM nginx:1.29-alpine

COPY microservices/gateway/nginx.conf /etc/nginx/nginx.conf
COPY website-studio/public/ /usr/share/nginx/html/

# Runs as the unprivileged nginx user on port 8080; temporary files live in /tmp.
USER nginx
EXPOSE 8080
