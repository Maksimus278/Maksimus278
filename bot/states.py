from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_route = State()
    waiting_truck = State()


class WatchStates(StatesGroup):
    waiting_route = State()
