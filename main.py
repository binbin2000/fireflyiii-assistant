"""Entry point – starts the uvicorn server."""

import argparse
import webbrowser

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Firefly III Kategoriserare")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        print(f"Öppnar webbläsare på {url}")

    uvicorn.run("src.web:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
