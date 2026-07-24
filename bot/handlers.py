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
from bot.models import SearchQuery, WatchFilter
from bot.search import LoadRepository, normalize_city, parse_route_text
from bot.states import SearchStates

router = Router()

HELP_TEXT = (
    "I find <b>US freight loads</b> by lane.\n\n"
    "<b>How to search</b>\n"
    "• Tap «🔍 Find load»\n"
    "• Or type a route: <code>Chicago - Dallas</code>\n"
    "• Or: <code>LA to Phoenix</code>\n"
    "• Or origin only: <code>Atlanta</code>\n\n"
    "<b>Commands</b>\n"
    "/search — guided search\n"
    "/watch Chicago - Dallas — watch a lane\n"
    "/watches — my watches\n"
    "/unwatch — clear watches\n"
    "/loads — latest US loads\n"
    "/help — help"
)


def _format_results(loads: list, query: SearchQuery) -> str:
    origin = query.origin or "any"
    destination = query.destination or "any"
    header = f"🔎 US loads <b>{origin} → {destination}</b>: <b>{len(loads)}</b>\n"
    if not loads:
        return (
            header
            + "\nNothing found for this lane.\n"
            "Try another city or watch the lane — I'll notify you when a load appears."
        )
    body = "\n\n".join(load.format_card() for load in loads)
    return header + "\n" + body


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🚛 <b>ProxyBot — US Load Board</b>\n\n"
        "Search American freight loads, for example:\n"
        "<code>Chicago → Dallas</code>\n"
        "<code>LA to Phoenix</code>\n"
        "<code>Atlanta - Miami</code>\n\n"
        "Or use the buttons below.",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text.in_({"ℹ️ Help", "ℹ️ Помощь"}))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("loads"))
@router.message(F.text.in_({"📋 All loads", "📋 Все грузы"}))
async def cmd_loads(message: Message, repo: LoadRepository) -> None:
    loads = repo.all()[:8]
    if not loads:
        await message.answer("No loads in the board yet.")
        return
    text = "📋 <b>Latest US loads</b>\n\n" + "\n\n".join(load.format_card() for load in loads)
    await message.answer(text)


@router.message(Command("search"))
@router.message(F.text.in_({"🔍 Find load", "🔍 Найти груз"}))
async def cmd_search(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_route)
    await message.answer(
        "Enter a US lane:\n"
        "<code>Origin - Destination</code>\n\n"
        "Examples: <code>Chicago - Dallas</code>, <code>LA to Phoenix</code>",
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
        "Pick equipment type:",
        reply_markup=truck_type_keyboard(),
    )


@router.callback_query(F.data.startswith("truck:"), SearchStates.waiting_truck)
async def search_truck_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    repo: LoadRepository,
) -> None:
    await callback.answer()
    data = await state.get_data()
    query = SearchQuery.model_validate(data.get("query", {}))
    truck = (callback.data or "").split(":", 1)[1]
    if truck != "any":
        query.truck_type = truck
    await state.clear()

    loads = repo.search(query)
    text = _format_results(loads, query)
    await callback.message.answer(  # type: ignore[union-attr]
        text,
        reply_markup=after_search_keyboard(query.origin, query.destination),
    )


@router.callback_query(F.data == "search:new")
async def search_new(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SearchStates.waiting_route)
    await callback.message.answer(  # type: ignore[union-attr]
        "Enter a US lane:\n<code>Origin - Destination</code>"
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


@router.message(F.text.regexp(r"(?i).*(->|→|-|—|–|\bto\b).*"))
async def quick_route_search(message: Message, state: FSMContext, repo: LoadRepository) -> None:
    current = await state.get_state()
    if current is not None:
        return
    # Ignore menu buttons that contain dashes in Russian/legacy text
    text = message.text or ""
    if text.startswith(("🔍", "👀", "📋", "ℹ️")):
        return
    query = parse_route_text(text)
    loads = repo.search(query)
    await message.answer(
        _format_results(loads, query),
        reply_markup=after_search_keyboard(query.origin, query.destination),
    )
