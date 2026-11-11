# syntax=docker/dockerfile:1

# --- Shared Node runtime -----------------------------------------------------
# The monorepo is installed once at the workspace root; the client and the API
# both run on this image.
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
COPY client/package.json ./client/
COPY server/package.json ./server/

# --- Development -------------------------------------------------------------
# Hot-reloading Vite client (5173) and Express API (3001). This is the target
# used for local development.
FROM base AS development
RUN npm ci --no-audit --no-fund
COPY . .
EXPOSE 5173 3001
CMD ["npm", "run", "dev"]

# --- Build -------------------------------------------------------------------
# Compile the React client and drop dev-only dependencies.
FROM base AS build
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build && npm prune --omit=dev

# --- Production --------------------------------------------------------------
# One origin: Express serves the API and the built client.
FROM node:22-alpine AS production
ENV NODE_ENV=production
ENV PORT=3000
WORKDIR /app
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/server ./server
COPY --from=build /app/client/dist ./client/dist
EXPOSE 3000
CMD ["node", "server/src/index.js"]
