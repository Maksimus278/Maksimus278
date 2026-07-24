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
    "Я ищу <b>loads / грузы</b> по направлению.\n\n"
    "<b>Как искать</b>\n"
    "• Нажми «🔍 Найти груз»\n"
    "• Или напиши маршрут: <code>Москва - СПб</code>\n"
    "• Или только город погрузки: <code>Казань</code>\n\n"
    "<b>Команды</b>\n"
    "/search — поиск\n"
    "/watch Москва - Казань — подписка на направление\n"
    "/watches — мои подписки\n"
    "/unwatch — снять все подписки\n"
    "/loads — свежие грузы\n"
    "/help — справка"
)


def _format_results(loads: list, query: SearchQuery) -> str:
    origin = query.origin or "любой"
    destination = query.destination or "любой"
    header = f"🔎 Найдено по маршруту <b>{origin} → {destination}</b>: <b>{len(loads)}</b>\n"
    if not loads:
        return (
            header
            + "\nНичего не нашёл по этим фильтрам.\n"
            "Попробуй другой город или подпишись на направление — пришлю, как появится."
        )
    body = "\n\n".join(load.format_card() for load in loads)
    return header + "\n" + body


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🚛 <b>ProxyBot — поиск грузов (loads)</b>\n\n"
        "Пиши направление, например:\n"
        "<code>Москва → Санкт-Петербург</code>\n"
        "<code>Екб - Новосибирск</code>\n\n"
        "Или жми кнопки ниже.",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("loads"))
@router.message(F.text == "📋 Все грузы")
async def cmd_loads(message: Message, repo: LoadRepository) -> None:
    loads = repo.all()[:8]
    if not loads:
        await message.answer("Пока нет грузов в базе.")
        return
    text = "📋 <b>Свежие грузы</b>\n\n" + "\n\n".join(load.format_card() for load in loads)
    await message.answer(text)


@router.message(Command("search"))
@router.message(F.text == "🔍 Найти груз")
async def cmd_search(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_route)
    await message.answer(
        "Введи направление:\n"
        "<code>Откуда - Куда</code>\n\n"
        "Примеры: <code>Москва - СПб</code>, <code>Казань → Самара</code>",
    )


@router.message(SearchStates.waiting_route)
async def search_route_entered(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Нужен текст маршрута.")
        return
    query = parse_route_text(message.text)
    await state.update_data(query=query.model_dump())
    await state.set_state(SearchStates.waiting_truck)
    await message.answer(
        f"Маршрут: <b>{query.origin or 'любой'} → {query.destination or 'любой'}</b>\n"
        "Выбери тип кузова:",
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
    if truck != "любой":
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
        "Введи направление:\n<code>Откуда - Куда</code>"
    )


@router.callback_query(F.data.startswith("watch:"))
async def watch_from_callback(
    callback: CallbackQuery,
    repo: LoadRepository,
) -> None:
    await callback.answer("Подписка сохранена")
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
        f"👀 Слежу за направлением <b>{origin or 'любой'} → {destination or 'любой'}</b>.\n"
        "Как появится подходящий груз — пришлю сюда.\n"
        "Снять подписки: /unwatch"
    )


@router.message(Command("watch"))
async def cmd_watch(message: Message, repo: LoadRepository) -> None:
    text = (message.text or "").replace("/watch", "", 1).strip()
    if not text:
        await message.answer("Пример: <code>/watch Москва - Казань</code>")
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
        f"👀 Подписка: <b>{query.origin or 'любой'} → {query.destination or 'любой'}</b>"
    )


@router.message(Command("watches"))
@router.message(F.text == "👀 Мои подписки")
async def cmd_watches(message: Message, repo: LoadRepository) -> None:
    watches = repo.watches_for(message.from_user.id)  # type: ignore[union-attr]
    if not watches:
        await message.answer("Подписок нет. Добавь через /watch Москва - СПб")
        return
    lines = [
        f"• {w.origin or 'любой'} → {w.destination or 'любой'}"
        + (f" ({w.truck_type})" if w.truck_type else "")
        for w in watches
    ]
    await message.answer("👀 <b>Твои подписки</b>\n" + "\n".join(lines))


@router.message(Command("unwatch"))
async def cmd_unwatch(message: Message, repo: LoadRepository) -> None:
    removed = repo.remove_watches(message.from_user.id)  # type: ignore[union-attr]
    await message.answer(f"Снято подписок: {removed}")


@router.message(F.text.regexp(r".*(->|→|-|—|–).*"))
async def quick_route_search(message: Message, state: FSMContext, repo: LoadRepository) -> None:
    current = await state.get_state()
    if current is not None:
        return
    query = parse_route_text(message.text or "")
    loads = repo.search(query)
    await message.answer(
        _format_results(loads, query),
        reply_markup=after_search_keyboard(query.origin, query.destination),
    )
