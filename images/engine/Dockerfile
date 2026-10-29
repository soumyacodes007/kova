# A miner engine image: the cadrecover miner code with one strategy baked in. Its image ID
# (sha256) is what the miner commits on-chain and what the auditor re-runs.
#
#   docker build -f images/engine/Dockerfile --build-arg STRATEGY=mock-oracle \
#       -t cadrecover-engine:mock-oracle src
FROM python:3.12-slim
RUN pip install --no-cache-dir pydantic==2.14.1
ARG STRATEGY
ENV CADRECOVER_ENGINE_STRATEGY=${STRATEGY} PYTHONPATH=/opt/engine PYTHONDONTWRITEBYTECODE=1
LABEL org.cadrecover.strategy=${STRATEGY}
COPY cadrecover/__init__.py cadrecover/paths.py /opt/engine/cadrecover/
COPY cadrecover/protocol /opt/engine/cadrecover/protocol
COPY cadrecover/miner/strategies.py cadrecover/miner/templates.py cadrecover/miner/engine.py /opt/engine/cadrecover/miner/
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin engine
USER 1000:1000
ENTRYPOINT ["python", "-m", "cadrecover.miner.engine", "/task"]
