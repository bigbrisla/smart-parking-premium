"""Construction of the Telegram bot application.

Registers the handlers and injects the EdgeClient (pointed at the chosen edge
instance). Note: the command names are in Italian on purpose (the demo is Italian).
"""
from __future__ import annotations

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.bot import handlers
from src.bot.client import EdgeClient


def build_application(token: str, edge_url: str) -> Application:
    app = Application.builder().token(token).build()
    # URL of the primary parking; each user can then pick another one with /parcheggio
    app.bot_data["default_url"] = edge_url

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("targa", handlers.cmd_targa))
    app.add_handler(CommandHandler("parcheggio", handlers.cmd_parcheggio))
    app.add_handler(CommandHandler(["disponibilita", "posti"], handlers.cmd_disponibilita))
    app.add_handler(CommandHandler("prenota", handlers.cmd_prenota))
    app.add_handler(CommandHandler("annulla", handlers.cmd_annulla))
    app.add_handler(CommandHandler("posizione", handlers.cmd_posizione))
    app.add_handler(CommandHandler("vai", handlers.cmd_vai))

    app.add_handler(CallbackQueryHandler(handlers.on_reserve_callback, pattern=r"^reserve\|"))
    app.add_handler(CallbackQueryHandler(handlers.on_switch_callback, pattern=r"^switch\|"))
    app.add_handler(MessageHandler(filters.LOCATION, handlers.on_location))

    return app
