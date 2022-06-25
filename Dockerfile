FROM python:2-alpine

RUN apk add --no-cache musl-dev gcc
RUN pip install twisted

COPY . /app
WORKDIR /app

ENTRYPOINT ["python", "master_server.py"]
