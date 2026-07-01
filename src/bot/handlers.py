"""Telegram bot command handlers (CLOUD level, end-user side).

Each command turns into one or more calls to the edge via EdgeClient. The bot does
not hold the state: it always reads and modifies it through the Digital Twin API.

Note: the messages replied to the user are intentionally kept in Italian (the demo
is in Italian); only comments and docstrings are in English.
"""
from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from src.bot.client import EdgeClient, EdgeError


def get_edge(context: ContextTypes.DEFAULT_TYPE) -> EdgeClient:
    """EdgeClient toward the parking chosen by the user (default: the primary)."""
    url = context.user_data.get("edge_url") or context.application.bot_data["default_url"]
    return EdgeClient(url)


async def discover_parkings(default_url: str) -> list[dict]:
    """Discover the available parkings: the primary + its federated peers."""
    edge = EdgeClient(default_url)
    parkings: list[dict] = []
    av = await edge.availability()
    parkings.append({"id": av["parking_id"], "name": av["name"], "url": default_url})
    for p in await edge.peers():
        parkings.append({"id": p["id"], "name": p["name"], "url": p["url"]})
    # dedup by URL keeping the order
    seen, out = set(), []
    for p in parkings:
        if p["url"] not in seen:
            seen.add(p["url"])
            out.append(p)
    return out


def get_plate(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("plate", "DEMO")


# --------------------------------------------------------------------------- #
#  Basic commands
# --------------------------------------------------------------------------- #

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Benvenuto in *Smart Parking Premium* 🅿️\n\n"
        "Comandi disponibili:\n"
        "/parcheggio – scegli il parcheggio (Gran Reno / IKEA)\n"
        "/disponibilita – posti liberi ora\n"
        "/prenota – prenota uno stallo\n"
        "/annulla – annulla la tua prenotazione\n"
        "/posizione – condividi la posizione (apre la sbarra se sei vicino)\n"
        "/targa – imposta la targa del veicolo\n",
        parse_mode="Markdown",
    )


cmd_help = cmd_start


async def cmd_targa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            f"Targa attuale: *{get_plate(context)}*\nUsa: `/targa AB123CD`",
            parse_mode="Markdown",
        )
        return
    plate = context.args[0].upper()
    context.user_data["plate"] = plate
    await update.message.reply_text(f"Targa impostata: *{plate}*", parse_mode="Markdown")


# --------------------------------------------------------------------------- #
#  Parking selection (primary + federated peers)
# --------------------------------------------------------------------------- #

async def cmd_parcheggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    default_url = context.application.bot_data["default_url"]
    current = context.user_data.get("edge_url", default_url)
    try:
        parkings = await discover_parkings(default_url)
    except EdgeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return

    rows = []
    for p in parkings:
        marker = "✅ " if p["url"] == current else ""
        rows.append([InlineKeyboardButton(f"{marker}{p['name']}", callback_data=f"switch|{p['url']}")])
    await update.message.reply_text(
        "Scegli il parcheggio su cui operare:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def on_switch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data.split("|", 1)[1]
    context.user_data["edge_url"] = url
    try:
        av = await EdgeClient(url).availability()
        name = av["name"]
    except EdgeError:
        name = url
    await query.edit_message_text(
        f"🅿️ Ora sei collegato a *{name}*.\nUsa /disponibilita o /prenota.",
        parse_mode="Markdown",
    )


# --------------------------------------------------------------------------- #
#  Availability (with federated suggestion if full)
# --------------------------------------------------------------------------- #

async def cmd_disponibilita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    edge = get_edge(context)
    try:
        av = await edge.availability()
    except EdgeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return

    if av["free"] > 0:
        await update.message.reply_text(
            f"🅿️ *{av['name']}*\nPosti liberi: *{av['free']}* su {av['total']}",
            parse_mode="Markdown",
        )
        return

    # parking full: ask the edge for the federated suggestions
    await _reply_full_with_suggestions(update, edge, av)


async def _reply_full_with_suggestions(update: Update, edge: EdgeClient, av: dict):
    text = f"🅿️ *{av['name']}*\n❌ Nessun posto libero."
    try:
        sug = await edge.suggest()
        alts = sug.get("suggestions", [])
    except EdgeError:
        alts = []
    if alts:
        text += "\n\n🔁 Parcheggi limitrofi con posti liberi:"
        for a in alts:
            text += f"\n• *{a['name']}*: {a['free']} liberi"
        text += "\n\nUsa /parcheggio per passare a uno di questi e prenotare."
    else:
        text += "\nAnche i parcheggi federati risultano pieni o non raggiungibili."
    await update.message.reply_text(text, parse_mode="Markdown")


# --------------------------------------------------------------------------- #
#  Reservation (inline keyboard of free slots)
# --------------------------------------------------------------------------- #

async def cmd_prenota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    edge = get_edge(context)
    user = update.effective_user.first_name or str(update.effective_user.id)

    # /prenota P03 -> direct reservation
    if context.args:
        await _do_reserve(update.message.reply_text, edge, context.args[0].upper(), user)
        return

    # otherwise show the free slots as buttons
    try:
        free = await edge.free_slots()
    except EdgeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    if not free:
        av = await edge.availability()
        await _reply_full_with_suggestions(update, edge, av)
        return

    buttons = [InlineKeyboardButton(sid, callback_data=f"reserve|{sid}") for sid in free]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await update.message.reply_text(
        "Scegli lo stallo da prenotare:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def on_reserve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_id = query.data.split("|", 1)[1]
    user = update.effective_user.first_name or str(update.effective_user.id)
    await _do_reserve(query.edit_message_text, get_edge(context), slot_id, user)


async def _do_reserve(reply, edge: EdgeClient, slot_id: str, user: str):
    """`reply` is a coroutine factory (reply_text or edit_message_text)."""
    try:
        await edge.reserve(slot_id, user)
    except EdgeError as e:
        await reply(f"❌ Impossibile prenotare {slot_id}: {e}")
        return
    await reply(f"✅ Stallo *{slot_id}* prenotato a nome di {user}.", parse_mode="Markdown")


async def cmd_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    edge = get_edge(context)
    if not context.args:
        await update.message.reply_text("Usa: `/annulla P03`", parse_mode="Markdown")
        return
    slot_id = context.args[0].upper()
    try:
        await edge.cancel(slot_id)
    except EdgeError as e:
        await update.message.reply_text(f"❌ {e}")
        return
    await update.message.reply_text(f"✅ Prenotazione di *{slot_id}* annullata.", parse_mode="Markdown")


# --------------------------------------------------------------------------- #
#  GPS position -> Haversine -> barrier
# --------------------------------------------------------------------------- #

async def cmd_posizione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Invia la mia posizione", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Condividi la posizione: se sei abbastanza vicino, la sbarra si apre.\n"
        "In alternativa, simula con: `/vai 44.4775 11.2807`",
        parse_mode="Markdown", reply_markup=keyboard,
    )


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    # log the real coordinates received (useful to calibrate the entrance on the position)
    logging.getLogger("bot").info("LOCATION RECEIVED lat=%.6f lon=%.6f", loc.latitude, loc.longitude)
    await _send_position(update, context, loc.latitude, loc.longitude)


async def cmd_vai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lat, lon = float(context.args[0]), float(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Usa: `/vai <lat> <lon>`", parse_mode="Markdown")
        return
    await _send_position(update, context, lat, lon)


async def _send_position(update: Update, context: ContextTypes.DEFAULT_TYPE, lat: float, lon: float):
    edge = get_edge(context)
    try:
        res = await edge.vehicle_position(lat, lon, get_plate(context))
    except EdgeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    dist = res["distance_m"]
    if res["unlocked"]:
        await update.message.reply_text(
            f"🚗 Sei a {dist:.0f} m dall'ingresso.\n🚧 *Sbarra APERTA* – benvenuto!",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"🚗 Sei a {dist:.0f} m dall'ingresso (soglia {res['threshold_m']:.0f} m).\n"
            "Avvicinati ancora per lo sblocco automatico.",
        )
