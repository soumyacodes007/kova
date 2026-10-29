# Sandbox image for rebuilding miner code. Same build123d/OCP pair as the CAD
# worker env (images/cad-worker/pyproject.toml), so references and candidates
# come from one engine. Only build123d + the standalone runner are inside.
#
#   docker build -t cadrecover-sandbox:build123d-0.13.0 images/cad-worker
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir build123d==0.13.0 cadquery-ocp-novtk==8.0.1.1.0

COPY sandbox_runner.py /opt/runner/sandbox_runner.py
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin runner
USER 1000:1000
ENTRYPOINT ["python", "-I", "/opt/runner/sandbox_runner.py"]
