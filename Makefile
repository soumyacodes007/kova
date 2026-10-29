# CADRecover dev tasks (owner: agent B). Run from WSL or Linux.
HOME_DIR ?= $(HOME)/.cadrecover
ENVS     := $(HOME_DIR)/envs
UVX      := UV_LINK_MODE=copy uv

.PHONY: envs check-envs localnet localnet-down wallets heartbeat test challenge doctor status api demo demo-down

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

doctor:  ## is this machine ready? envs, docker, images, chain, miners, ports (exit 1 on failure)
	$(ENVS)/services/bin/cadrecover doctor

status:  ## chain, miners, latest run, weight receipts and audits on one screen (WATCH=1 to redraw)
	$(ENVS)/services/bin/cadrecover status $(if $(WATCH),--watch)

api:  ## read API on 127.0.0.1:8000
	$(ENVS)/services/bin/cadrecover api serve --port $(or $(PORT),8000)

demo:  ## backend gate: localnet + miners + rounds + audit + weights; 3-pane tmux (DEMO_HEADLESS=1 for plain stdout, non-zero on failure)
	bash scripts/demo.sh

demo-down:  ## close the tmux session and stop the miners (ALL=1 also stops the localnet)
	bash scripts/demo.sh down
