FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Strip crossorigin attribute — nginx proxy doesn't send CORS headers,
# causing module scripts to silently fail to execute
RUN sed -i 's/ crossorigin//g' /usr/share/nginx/html/index.html
EXPOSE 80
