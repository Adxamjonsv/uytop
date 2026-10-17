"""Convenience entry point for running UyTop locally."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)

main.py syntax: OK
