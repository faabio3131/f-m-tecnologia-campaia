FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG CAMPAIA_BFF_ORIGIN
ARG NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID
ARG NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API
ARG NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=google

ENV CAMPAIA_BFF_ORIGIN=${CAMPAIA_BFF_ORIGIN} \
    NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID=${NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID} \
    NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API=${NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API} \
    NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=${NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE}

RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    HOSTNAME=0.0.0.0

RUN groupadd --gid 10001 campaia \
    && useradd --uid 10001 --gid campaia --create-home campaia

COPY --from=builder --chown=campaia:campaia /app/.next/standalone ./
COPY --from=builder --chown=campaia:campaia /app/.next/static ./.next/static

USER campaia
EXPOSE 8080
CMD ["node", "server.js"]
