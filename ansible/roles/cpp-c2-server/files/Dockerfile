#docker login --username Guac0 --password ${{ secrets.DOCKER_ACTION_SECRET }} ghcr.io
#docker build . -t ghcr.io/guac0/cppc2-server:latest
#docker push ghcr.io/guac0/cppc2-server:latest
FROM alpine:3.19

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --break-system-packages -r requirements.txt