FROM node:20-alpine

WORKDIR /app

ARG VITE_API_BASE_URL=/api
ARG VITE_DEV_API_TARGET=http://backend:8000
ARG VITE_USE_MOCK_SERVICES=false
ARG VITE_SHOW_DEV_AUTH_NOTE=false

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_DEV_API_TARGET=$VITE_DEV_API_TARGET
ENV VITE_USE_MOCK_SERVICES=$VITE_USE_MOCK_SERVICES
ENV VITE_SHOW_DEV_AUTH_NOTE=$VITE_SHOW_DEV_AUTH_NOTE

COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm install

COPY . .

RUN npm run build

EXPOSE 5173

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
