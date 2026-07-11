"""Utility script to test FastAPI endpoints without launching a server.

It imports the `backend.main` module directly using ``importlib`` (avoiding the
package-import issue we observed) and creates a ``TestClient`` instance from
FastAPI. The script then performs a simple GET request against the
``/api/health`` endpoint and prints the HTTP status code and JSON payload.

Running this script provides a quick sanity‑check that the application can be
imported and that the core health endpoint works as expected.
"""

import os
import importlib.util

# Resolve the path to backend/main.py relative to the **inner** project folder.
# The repository has a top‑level ``LUMINA_Project`` directory that contains the
# actual Python package. Adjust the path accordingly so the import succeeds.
module_path = os.path.join(os.getcwd(), 'LUMINA_Project', 'backend', 'main.py')
spec = importlib.util.spec_from_file_location("backend.main", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app

# Use FastAPI's TestClient for in‑process requests.
from fastapi.testclient import TestClient

client = TestClient(app)

# Basic sanity check – ensure the FastAPI app can be imported and the health
# endpoint returns a successful response.
response = client.get("/api/health")
print("Health endpoint status code:", response.status_code)
print("Health endpoint JSON:", response.json())
