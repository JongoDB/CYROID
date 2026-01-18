# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies first (for layer caching on fresh builds)
COPY package.json package-lock.json* ./
RUN npm install

# Copy entrypoint script that syncs deps when package.json changes
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY . .

EXPOSE 5173

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["npm", "run", "dev"]
