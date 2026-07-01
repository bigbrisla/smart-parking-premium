"""Start the Telegram bot (cloud level).

Requires TELEGRAM_TOKEN in the .env file (or in the environment). EDGE_URL points
to the edge instance to connect to (default: Gran Reno on :8001).

Usage:
    python scripts/run_bot.py
    python scripts/run_bot.py --edge-url http://127.0.0.1:8001
"""
import _bootstrap  # noqa: F401

import argparse
import os

from src.bot.bot import build_application
from src.common.env import load_env


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Smart Parking Premium Telegram bot")
    parser.add_argument("--token", default=os.environ.get("TELEGRAM_TOKEN"))
    parser.add_argument("--edge-url", default=os.environ.get("EDGE_URL", "http://127.0.0.1:8001"))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit(
            "TELEGRAM_TOKEN missing. Create a bot with @BotFather and put it in .env"
        )

    print(f"Bot started. Connected to the edge: {args.edge_url}")
    app = build_application(args.token, args.edge_url)
    app.run_polling()


if __name__ == "__main__":
    main()
