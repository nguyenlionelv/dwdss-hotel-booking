# Dùng chung: cài dependency và copy source frontend.
FROM node:24-alpine AS base

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

# Development: chạy Vite với hot reload, dùng --target development.
FROM base AS development

EXPOSE 5173

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:5173/', {signal: AbortSignal.timeout(3000)}).then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--strictPort"]

# Triển khai - build: tạo static assets trong /app/dist.
FROM base AS build

ENV VITE_API_BASE_URL=""
RUN npm run build

# Triển khai - runtime: Nginx phục vụ bản build; đây là stage mặc định.
FROM nginx:1.30-alpine AS runtime

ENV API_UPSTREAM=http://backend:8000 \
    NGINX_ENVSUBST_FILTER=API_UPSTREAM

COPY infra/frontend/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/frontend-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
