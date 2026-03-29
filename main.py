#!/usr/bin/env python3
"""Firefly III AI Transaction Categorizer – web server entry point.

Usage:
    python main.py              # Start on http://localhost:8000
    python main.py --port 9000  # Custom port
    python main.py --host 0.0.0.0  # Expose on network (use with caution!)

Configuration via .env:
    FIREFLY_URL       URL to your Firefly III instance
    FIREFLY_TOKEN     Personal access token from Firefly III
    ANTHROPIC_API_KEY Optional: Claude API key (data leaves your machine)
    OLLAMA_URL        Optional: Local Ollama base URL (100% private)
    OLLAMA_MODEL      Optional: Ollama model name (default: llama3)
"""

import argparse
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description='Firefly III AI-driven transaktionskategoriserare (webbgränssnitt)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Bind-adress (standard: 127.0.0.1 = bara din dator)',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port (standard: 8000)',
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Öppna inte webbläsaren automatiskt',
    )
    args = parser.parse_args()

    if args.host != '127.0.0.1':
        print('⚠️  Varning: du exponerar servern utanför localhost.')
        print('   Din Firefly III-data kan nås av andra på nätverket!')
        print()

    url = f'http://{args.host}:{args.port}'
    print(f'🔥 Firefly III Kategoriserare')
    print(f'   Öppna: {url}')
    print(f'   Tryck Ctrl+C för att avsluta')
    print()

    import uvicorn
    from src.web import app

    if not args.no_browser:
        import threading, time
        def _open():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
