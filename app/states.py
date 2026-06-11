"""FSM states for the survey flow."""

from aiogram.fsm.state import State, StatesGroup


class SurveyStates(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q4_confirm_empty = State()
