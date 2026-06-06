# ── ScoutIQ Frontend (React + Vite) ──────────────────────────────────────────
FROM node:20-alpine

WORKDIR /app

# Accept API URL as build argument
ARG VITE_API_URL=http://api:8000
ENV VITE_API_URL=$VITE_API_URL

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Verify build succeeded
RUN test -d dist || (echo "ERROR: Build failed - dist/ not found" && exit 1)

# Serve frontend with a simple HTTP server
FROM node:20-alpine

WORKDIR /app

# Install serve package for serving static files
RUN npm install -g serve

# Copy built app from builder
COPY --from=0 /app/dist ./dist

# Port
ENV PORT=3000
EXPOSE 3000

# Serve the built app
CMD ["serve", "-s", "dist", "-l", "3000"]
