"""Read API, live event stream and OpenAPI source for the frontend (owner: agent C).

    from cadrecover.api.app import create_app, main

Read-only: it never writes the database, never runs miner code, never touches runtime/private, and never
invents data (empty lists when there is nothing). Python owns the truth; the frontend only presents it.
"""
