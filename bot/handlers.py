from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    after_search_keyboard,
    main_menu,
    truck_type_keyboard,
)
from bot.leads import Lead
from bot.models import SearchQuery, WatchFilter
from bot.search import LoadRepository, normalize_city, parse_route_text
from bot.service import LoadService
from bot.states import LeadStates, SearchStates

router = Router()

HELP_TEXT = (
    "I generate <b>real US freight leads</b> from live loads "
    "(broker company + phone + lane).\n\n"
    "<b>Leads</b>\n"
    "• Tap «🔥 Get leads» for fresh broker leads\n"
    "• Or: <code>/leads Chicago</code>\n"
    "• Or: <code>/leads Dallas - Atlanta</code>\n\n"
    "<b>Loads</b>\n"
    "• <code>Chicago - Dallas</code>\n"
    "• <code>LA to Phoenix</code>\n"
    "• /loads — latest live loads\n\n"
    "<b>Other</b>\n"
    "/watch Chicago - Dallas — watch a lane\n"
    "/help — help"
)

MENU_TEXTS = {
    "🔥 Get leads",
    "🔍 Find load",
    "🔍 Найти груз",
    "👀 My watches",
    "👀 Мои подписки",
    "📋 All loads",
    "📋 Все грузы",
    "ℹ️ Help",
    "ℹ️ Помощь",
}


def _format_header(total: int, query: SearchQuery, shown: int, source: str) -> str:
    origin = query.origin or "any"
    destination = query.destination or "any"
    return (
        f"🔎 US loads <b>{origin} → {destination}</b>\n"
        f"Found <b>{total}</b> · showing <b>{shown}</b>\n"
        f"<i>source: {source}</i>\n"
    )


def _chunk_texts(parts: list[str], header: str, max_len: int = 3500) -> list[str]:
    if not parts:
        return [header + "\nNothing found."]
    chunks: list[str] = []
    current = header
    for part in parts:
        card = "\n\n" + part
        if len(current) + len(card) > max_len and current != header:
            chunks.append(current)
            current = "<i>…more</i>" + card
        else:
            current += card
    chunks.append(current)
    return chunks


async def _send_search_results(
    message: Message,
    service: LoadService,
    query: SearchQuery,
    limit: int = 12,
) -> None:
    await message.answer("⏳ Searching live US loads…")
    loads, source = await service.search(query, limit=limit)
    header = _format_header(len(loads), query, len(loads), source)
    cards = [load.format_card() for load in loads]
    chunks = _chunk_texts(cards, header)
    for i, chunk in enumerate(chunks):
        kwargs = {}
        if i == len(chunks) - 1:
            kwargs["reply_markup"] = after_search_keyboard(query.origin, query.destination)
        await message.answer(chunk, **kwargs)


async def _send_leads(
    message: Message,
    service: LoadService,
    query: SearchQuery | None = None,
    limit: int = 12,
) -> None:
    await message.answer("🔥 Generating real broker leads from live loads…")
    leads, source = await service.generate_leads(query, limit=limit)
    scope = "US hubs"
    if query and (query.origin or query.destination):
        scope = f"{query.origin or 'any'} → {query.destination or 'any'}"
    header = (
        f"🔥 <b>Real leads</b> · {scope}\n"
        f"Generated <b>{len(leads)}</b> unique broker contacts\n"
        f"<i>source: {source}</i>\n"
    )
    if not leads:
        await message.answer(
            header + "\nNo dialable leads right now. Try another city, e.g. <code>/leads Chicago</code>",
            reply_markup=main_menu(),
        )
        return
    cards = [lead.format_card(i) for i, lead in enumerate(leads, start=1)]
    chunks = _chunk_texts(cards, header)
    for chunk in chunks:
        await message.answer(chunk, reply_markup=main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, service: LoadService) -> None:
    await state.clear()
    mode = "LIVE Trulos leads" if service.use_live else "local demo"
    await message.answer(
        "🚛 <b>ProxyBot — US Leads & Loads</b>\n\n"
        f"Mode: <b>{mode}</b>\n\n"
        "I pull <b>real broker leads</b> (company + phone) from live US loads.\n\n"
        "Tap «🔥 Get leads» or try:\n"
        "<code>/leads Chicago</code>\n"
        "<code>/leads Dallas - Atlanta</code>",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text.in_({"ℹ️ Help", "ℹ️ Помощь"}))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("leads"))
@router.message(F.text == "🔥 Get leads")
async def cmd_leads(message: Message, state: FSMContext, service: LoadService) -> None:
    text = (message.text or "").strip()
    # /leads Chicago - Dallas  OR bare button
    if text.startswith("/leads"):
        arg = text.replace("/leads", "", 1).strip()
        if arg:
            query = parse_route_text(arg)
            await _send_leads(message, service, query)
            return
    # Button without args → ask for city/lane OR generate nationwide
    await state.set_state(LeadStates.waiting_route)
    await message.answer(
        "Where should I pull leads from?\n\n"
        "Send a city/lane, e.g.\n"
        "<code>Chicago</code>\n"
        "<code>Dallas - Atlanta</code>\n\n"
        "Or send <code>all</code> for a multi-hub US sweep."
    )


@router.message(LeadStates.waiting_route)
async def leads_route_entered(message: Message, state: FSMContext, service: LoadService) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Send a city, lane, or <code>all</code>.")
        return
    await state.clear()
    if text.lower() in {"all", "us", "usa", "*", "any"}:
        await _send_leads(message, service, None)
        return
    query = parse_route_text(text)
    await _send_leads(message, service, query)


@router.callback_query(F.data.startswith("leads:"))
async def leads_from_callback(callback: CallbackQuery, service: LoadService) -> None:
    await callback.answer()
    raw = (callback.data or "").split(":", 1)[1]
    origin_raw, destination_raw = raw.split("|", 1)
    origin = None if origin_raw == "*" else normalize_city(origin_raw)
    destination = None if destination_raw == "*" else normalize_city(destination_raw)
    query = SearchQuery(origin=origin, destination=destination)
    await _send_leads(callback.message, service, query)  # type: ignore[arg-type]


@router.message(Command("loads"))
@router.message(F.text.in_({"📋 All loads", "📋 Все грузы"}))
async def cmd_loads(message: Message, service: LoadService) -> None:
    await message.answer("⏳ Pulling latest live loads…")
    loads, source = await service.latest(limit=12)
    if not loads:
        await message.answer("No loads right now. Try a city search.")
        return
    header = f"📋 <b>Latest US loads</b> · <i>{source}</i>\n"
    cards = [load.format_card() for load in loads]
    chunks = _chunk_texts(cards, header)
    for chunk in chunks:
        await message.answer(chunk)


@router.message(Command("search"))
@router.message(F.text.in_({"🔍 Find load", "🔍 Найти груз"}))
async def cmd_search(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_route)
    await message.answer(
        "Enter a US lane or city:\n"
        "<code>Chicago - Dallas</code>\n"
        "<code>LA to Phoenix</code>\n"
        "<code>Atlanta</code>",
    )


@router.message(SearchStates.waiting_route)
async def search_route_entered(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Need a text route.")
        return
    query = parse_route_text(message.text)
    await state.update_data(query=query.model_dump())
    await state.set_state(SearchStates.waiting_truck)
    await message.answer(
        f"Lane: <b>{query.origin or 'any'} → {query.destination or 'any'}</b>\n"
        "Pick equipment (or Any for all):",
        reply_markup=truck_type_keyboard(),
    )


@router.callback_query(F.data.startswith("truck:"))
async def search_truck_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    service: LoadService,
) -> None:
    await callback.answer()
    data = await state.get_data()
    raw_query = data.get("query")
    if not raw_query:
        await callback.message.answer(  # type: ignore[union-attr]
            "Search expired. Tap «🔍 Find load» or type a route like <code>Chicago - Dallas</code>."
        )
        await state.clear()
        return

    query = SearchQuery.model_validate(raw_query)
    truck = (callback.data or "").split(":", 1)[1]
    if truck != "any":
        query.truck_type = truck
    await state.clear()
    await _send_search_results(callback.message, service, query)  # type: ignore[arg-type]


@router.callback_query(F.data == "search:new")
async def search_new(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SearchStates.waiting_route)
    await callback.message.answer(  # type: ignore[union-attr]
        "Enter a US lane or city:\n<code>Origin - Destination</code>"
    )


@router.callback_query(F.data.startswith("watch:"))
async def watch_from_callback(
    callback: CallbackQuery,
    repo: LoadRepository,
) -> None:
    await callback.answer("Watch saved")
    raw = (callback.data or "").split(":", 1)[1]
    origin_raw, destination_raw = raw.split("|", 1)
    origin = None if origin_raw == "*" else normalize_city(origin_raw)
    destination = None if destination_raw == "*" else normalize_city(destination_raw)
    user = callback.from_user
    if user is None:
        return
    repo.add_watch(
        WatchFilter(user_id=user.id, origin=origin, destination=destination)
    )
    await callback.message.answer(  # type: ignore[union-attr]
        f"👀 Watching <b>{origin or 'any'} → {destination or 'any'}</b>.\n"
        "Clear watches: /unwatch"
    )


@router.message(Command("watch"))
async def cmd_watch(message: Message, repo: LoadRepository) -> None:
    text = (message.text or "").replace("/watch", "", 1).strip()
    if not text:
        await message.answer("Example: <code>/watch Chicago - Dallas</code>")
        return
    query = parse_route_text(text)
    repo.add_watch(
        WatchFilter(
            user_id=message.from_user.id,  # type: ignore[union-attr]
            origin=query.origin,
            destination=query.destination,
        )
    )
    await message.answer(
        f"👀 Watching: <b>{query.origin or 'any'} → {query.destination or 'any'}</b>"
    )


@router.message(Command("watches"))
@router.message(F.text.in_({"👀 My watches", "👀 Мои подписки"}))
async def cmd_watches(message: Message, repo: LoadRepository) -> None:
    watches = repo.watches_for(message.from_user.id)  # type: ignore[union-attr]
    if not watches:
        await message.answer("No watches yet. Add one: /watch Chicago - Dallas")
        return
    lines = [
        f"• {w.origin or 'any'} → {w.destination or 'any'}"
        + (f" ({w.truck_type})" if w.truck_type else "")
        for w in watches
    ]
    await message.answer("👀 <b>Your watches</b>\n" + "\n".join(lines))


@router.message(Command("unwatch"))
async def cmd_unwatch(message: Message, repo: LoadRepository) -> None:
    removed = repo.remove_watches(message.from_user.id)  # type: ignore[union-attr]
    await message.answer(f"Cleared watches: {removed}")


@router.message(Command("reload"))
async def cmd_reload(message: Message, repo: LoadRepository) -> None:
    repo.reload()
    await message.answer(f"Reloaded local fallback board: <b>{len(repo.all())}</b> loads")


@router.message(F.text.regexp(r"(?i).*(->|→|-|—|–|\bto\b).*"))
async def quick_route_search(
    message: Message,
    state: FSMContext,
    service: LoadService,
) -> None:
    current = await state.get_state()
    if current is not None:
        return
    text = message.text or ""
    if text in MENU_TEXTS or text.startswith(("🔍", "👀", "📋", "ℹ️", "🔥", "/")):
        return
    query = parse_route_text(text)
    await _send_search_results(message, service, query)


@router.message(F.text)
async def city_or_fallback(
    message: Message,
    state: FSMContext,
    service: LoadService,
) -> None:
    current = await state.get_state()
    if current is not None:
        return
    text = (message.text or "").strip()
    if not text or text in MENU_TEXTS or text.startswith("/"):
        return

    query = parse_route_text(text)
    await _send_search_results(message, service, query)
