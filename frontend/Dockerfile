FROM node:20-alpine

WORKDIR /app

COPY package.json ./
COPY tsconfig.json ./
COPY next.config.ts ./
COPY next-env.d.ts ./
COPY app ./app
COPY components ./components
COPY lib ./lib

RUN npm install

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"]
