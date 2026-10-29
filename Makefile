# CADRecover dev tasks (owner: agent B). Run from WSL or Linux.
HOME_DIR ?= $(HOME)/.cadrecover
ENVS     := $(HOME_DIR)/envs
UVX      := UV_LINK_MODE=copy uv

.PHONY: envs check-envs localnet localnet-down wallets heartbeat test challenge

envs:  ## create/refresh the three locked environments
	UV_PROJECT_ENVIRONMENT=$(ENVS)/services $(UVX) sync --extra services --python 3.12
	UV_PROJECT_ENVIRONMENT=$(ENVS)/cad      $(UVX) sync --project images/cad-worker --python 3.12
	UV_PROJECT_ENVIRONMENT=$(ENVS)/drawing  $(UVX) sync --project images/drawing-worker --python 3.13

check-envs:  ## each environment imports its libraries
	bash scripts/check-envs.sh

localnet:
	docker compose up -d localnet

localnet-down:
	docker compose down

wallets:  ## dev wallets (local/test only)
	$(ENVS)/services/bin/cadrecover setup wallets

heartbeat:  ## local chain produces blocks
	$(ENVS)/services/bin/cadrecover chain heartbeat --network local

test:  ## each environment runs its own suite
	$(ENVS)/services/bin/python -m pytest -q tests/services
	$(ENVS)/cad/bin/python -m pytest -q tests/cad
	$(ENVS)/drawing/bin/python -m pytest -q tests/drawing

challenge:  ## phase 2 done-when: one hidden plate + its drawing
	$(ENVS)/services/bin/cadrecover challenge new --family plate
