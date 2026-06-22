from aiogram.fsm.state import StatesGroup, State


class AuthStates(StatesGroup):
    waiting_contact = State()


class SearchmanStates(StatesGroup):
    select_store = State()
    search_store = State()
    add_store_name = State()
    add_store_phone = State()
    product_name = State()
    product_size = State()
    product_color = State()
    product_material = State()
    product_characteristics = State()
    product_packaging = State()
    product_main_image = State()
    product_images = State()


class AiCreatorStates(StatesGroup):
    wait_photos = State()
