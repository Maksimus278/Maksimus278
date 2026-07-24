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
from bot.models import Load, SearchQuery, WatchFilter
from bot.search import LoadRepository, normalize_city, parse_route_text
from bot.service import LoadService
from bot.states import SearchStates

router = Router()

HELP_TEXT = (
    "I find <b>real US freight loads</b> (live from Trulos public board).\n\n"
    "<b>How to search</b>\n"
    "• Tap «🔍 Find load»\n"
    "• Route: <code>Chicago - Dallas</code>\n"
    "• Or: <code>LA to Phoenix</code>\n"
    "• City only: <code>Atlanta</code>\n\n"
    "<b>Commands</b>\n"
    "/search — guided search\n"
    "/loads — latest live US loads\n"
    "/watch Chicago - Dallas — watch a lane\n"
    "/watches — my watches\n"
    "/unwatch — clear watches\n"
    "/help — help"
)

MENU_TEXTS = {
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


def _chunk_loads(loads: list[Load], header: str, max_len: int = 3500) -> list[str]:
    if not loads:
        return [
            header
            + "\nNothing found for this filter.\n"
            "Try another city (Chicago, Dallas, LA, Atlanta…) or /loads"
        ]

    chunks: list[str] = []
    current = header
    for load in loads:
        card = "\n\n" + load.format_card()
        if len(current) + len(card) > max_len and current != header:
            chunks.append(current)
            current = "<i>…more loads</i>" + card
        else:
            current += card
    chunks.append(current)
    return chunks


async def _send_search_results(
    message: Message,
    service: LoadService,
    query: SearchQuery,
    limit: int = 15,
) -> None:
    await message.answer("⏳ Searching live US loads…")
    loads, source = await service.search(query, limit=limit)
    header = _format_header(len(loads), query, len(loads), source)
    chunks = _chunk_loads(loads, header)
    for i, chunk in enumerate(chunks):
        kwargs = {}
        if i == len(chunks) - 1:
            kwargs["reply_markup"] = after_search_keyboard(query.origin, query.destination)
        await message.answer(chunk, **kwargs)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, service: LoadService) -> None:
    await state.clear()
    mode = "LIVE Trulos board" if service.use_live else "local demo"
    await message.answer(
        "🚛 <b>ProxyBot — US Load Board</b>\n\n"
        f"Mode: <b>{mode}</b>\n\n"
        "Search real American freight, for example:\n"
        "<code>Chicago → Dallas</code>\n"
        "<code>LA to Phoenix</code>\n"
        "<code>Atlanta</code>\n\n"
        "Or use the buttons below.",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text.in_({"ℹ️ Help", "ℹ️ Помощь"}))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("loads"))
@router.message(F.text.in_({"📋 All loads", "📋 Все грузы"}))
async def cmd_loads(message: Message, service: LoadService) -> None:
    await message.answer("⏳ Pulling latest live loads…")
    loads, source = await service.latest(limit=12)
    if not loads:
        await message.answer("No loads right now. Try a city search.")
        return
    header = f"📋 <b>Latest US loads</b> · <i>{source}</i>\n"
    chunks = _chunk_loads(loads, header)
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
        "I'll send matching US loads here.\n"
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
    if text in MENU_TEXTS or text.startswith(("🔍", "👀", "📋", "ℹ️", "/")):
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
