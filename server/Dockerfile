# N-Ways Addressing for Benin: the registry server.
#   docker compose up -d        (from server/; see server/README.md)
# Build context: the repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADDRESSES_DB=/data/addresses.sqlite \
    REGISTRY_DIR=/app/registry \
    PORT=8080

RUN groupadd --system --gid 10001 addresses \
 && useradd --system --uid 10001 --gid addresses --home-dir /app --shell /usr/sbin/nologin addresses \
 && mkdir -p /data && chown addresses:addresses /data

WORKDIR /app
COPY engine/reference/bj_engine.py engine/reference/bj_border.py engine/reference/plate_names.py engine/reference/
COPY engine/data/border.json engine/data/
COPY model/keys.json model/names.json model/
COPY model/units/arrondissements.geojson model/units/
COPY registry/ registry/
COPY server/__init__.py server/__main__.py server/api.py server/engine.py server/store.py server/
COPY LICENSE LICENSE-DATA LICENSE-DOCS LICENSING.md NOTICE ./

USER addresses
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30m --retries=3 \
  CMD ["python3", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/health' % os.environ.get('PORT', '8080'), timeout=4)"]

CMD ["python3", "-m", "server", "start"]
