"""Challenge generation (owner: agent A).

Split by environment:
- families/*_spec.py   pure data + seeded sampling; importable everywhere
- families/<name>.py   build123d geometry + reference self-test (CAD worker env)
- cad_worker.py        CAD worker entry point (CAD env)
- drawing_worker.py    drawing, lint, coverage, scan look (drawing env)
- pipeline.py          orchestrates both and writes the records (services env)
"""
