from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='📱 Поделиться номером', request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def searchman_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='📦 Добавить товар')]],
        resize_keyboard=True,
    )


def stores_keyboard(stores: list, page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    start = page * per_page
    end = start + per_page
    page_stores = stores[start:end]

    for store in page_stores:
        builder.button(text=f'🏪 {store.name}', callback_data=f'store_sel_{store.id}')

    builder.adjust(2)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='◀️', callback_data=f'stores_pg_{page - 1}'))
    if end < len(stores):
        nav.append(InlineKeyboardButton(text='▶️', callback_data=f'stores_pg_{page + 1}'))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(text='🔍 Поиск', callback_data='store_search'),
        InlineKeyboardButton(text='➕ Новый магазин', callback_data='store_new'),
    )

    return builder.as_markup()


def images_done_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f'✅ Готово — {count} фото', callback_data='images_done')]]
    )


def take_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='✅ Взять', callback_data=f'take_{product_id}')]]
    )
