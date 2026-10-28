FROM node:22.23.4-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm ci

FROM node:22.23.4-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
RUN npm run build

FROM node:22.23.4-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    API_URL=http://api:8000
RUN addgroup -S nia && adduser -S -G nia nia
COPY --from=builder --chown=nia:nia /app/public ./public
COPY --from=builder --chown=nia:nia /app/.next/standalone ./
COPY --from=builder --chown=nia:nia /app/.next/static ./.next/static
USER nia
EXPOSE 3000
CMD ["node", "server.js"]
