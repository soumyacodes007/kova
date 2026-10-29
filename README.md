# CADRecover

A Bittensor subnet that turns engineering drawings into editable, verified parametric CAD.

Miners get drawings generated from hidden parts and submit parametric CAD code. Validators rebuild each submission and pay only for models that match the drawing's dimensions **and** stay correct when a parameter changes.

> Status: phases 0–2 done (protocol, environments + localnet, plate challenges with readable drawings). See [notes/shared.md](notes/shared.md).

```bash
make envs          # three locked environments under ~/.cadrecover/envs (run in WSL/Linux)
make localnet      # Bittensor localnet on 127.0.0.1:9944
make wallets       # dev wallets (local/test only)
make test          # each environment's test suite
make challenge     # a hidden plate + its dimensioned drawing
```

- [PRD.md](PRD.md): build plan v2.1 (product, mechanism, architecture, phases, demo)
- [REVIEW.md](REVIEW.md): review findings and their status
- [AGENTS.md](AGENTS.md): how the three coding agents split the phases, hand off work and keep notes
- [notes/](notes/): the shared board and each agent's phase-by-phase progress
