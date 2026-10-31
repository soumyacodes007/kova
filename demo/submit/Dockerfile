# Submit demo: the services env plus a script that walks one miner submission end to end
# (Hugging Face pin -> free pre-check -> hotkey-signed chain commitment -> validator readback -> queue).
# Built from the repo root by demo/submit/compose.yaml. Localnet only.
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 CADRECOVER_HOME=/data
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --extra services --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --extra services --no-dev
# Lium (Bittensor SN51 GPU rental) CLI in its own venv, for the optional fine-tune route.
RUN uv venv -q /opt/lium && uv pip install -q -p /opt/lium lium.io==0.38.1 && ln -s /opt/lium/bin/lium /usr/local/bin/lium
COPY demo/submit/submit-demo.sh /usr/local/bin/submit-demo
RUN sed -i 's/\r$//' /usr/local/bin/submit-demo && chmod +x /usr/local/bin/submit-demo
ENTRYPOINT ["submit-demo"]
