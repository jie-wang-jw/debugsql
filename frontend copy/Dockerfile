FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--port", "5173"]
