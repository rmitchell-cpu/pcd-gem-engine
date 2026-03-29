"""Start the PCD GEM Engine web dashboard.

Usage:
    python3 web_server.py
    python3 web_server.py --port 8080
"""

import argparse
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="PCD GEM Engine Web Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    print(f"\n  PCD GEM Engine — Dashboard")
    print(f"  Running at: http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop.\n")

    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
