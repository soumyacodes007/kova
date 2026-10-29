"""Versions every record carries. Bump PROTOCOL_VERSION on any schema change and log it in notes/shared.md."""

PROTOCOL_VERSION = "0.1.0"
SCORING_VERSION = "2.1"  # PRD v2.1: every parameter set scored, critical features gate each set
CAD_ENGINE = {"build123d": "0.13.0"}  # the exact build123d miners' code is rebuilt with
