"""Exports the live FastAPI app's OpenAPI schema to backend/openapi.json.
Run after any change to a route, request/response schema, or docstring
that should be reflected in the API documentation:
    python backend/scripts/export_openapi.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "openapi.json")


def main() -> None:
    schema = app.openapi()
    with open(OUTPUT_PATH, "w") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(schema['paths'])} paths to {os.path.abspath(OUTPUT_PATH)}")


if __name__ == "__main__":
    main()
