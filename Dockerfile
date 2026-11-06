FROM --platform=$BUILDPLATFORM docker.io/library/node:24-slim AS node_builder
WORKDIR /angular
COPY angular/ /angular
RUN npm config set update-notifier false && \
  npm config set fund false && \
  npm config set audit false && \
  npm ci
RUN npm run build self-host-planning-poker

FROM docker.io/library/python:3.13-alpine
RUN adduser -H -D -u 1001 -G root default
WORKDIR /app
COPY --chown=1001:0 flask/ ./
COPY --chown=1001:0 --from=node_builder /angular/dist/self-host-planning-poker ./static
RUN pip install --upgrade pip && \
  pip install --requirement requirements.txt && \
  mkdir /data && \
  chown -R 1001:0 /app /data && \
  chmod -R g+w /app /data
USER 1001
CMD [ "gunicorn", "--worker-class", "gevent", "-w", "1", "--no-control-socket", "app:app", "--bind", "0.0.0.0:8000" ]
