# build env
# FROM node:13.12.0-alpine as build
FROM node:14.21.3-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . ./
# Client ID для входа через Google подставляется в бандл на этапе сборки.
# Если не передан — кнопка Google просто не отрисовывается.
ARG REACT_APP_GOOGLE_CLIENT_ID
ENV REACT_APP_GOOGLE_CLIENT_ID=$REACT_APP_GOOGLE_CLIENT_ID
RUN npm run build
CMD cp -r build result_build
