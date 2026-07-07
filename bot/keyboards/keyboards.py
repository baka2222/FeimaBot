from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.locales import t, BTN_ADD_PRODUCT


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='🇷🇺 Русский', callback_data='lang_ru'),
        InlineKeyboardButton(text='🇨🇳 中文', callback_data='lang_zh'),
    ]])


def contact_keyboard(lang: str = 'ru') -> ReplyKeyboardMarkup:
    text = '📱 Поделиться номером' if lang == 'ru' else '📱 分享号码'
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def searchman_menu(lang: str = 'ru') -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_ADD_PRODUCT.get(lang, BTN_ADD_PRODUCT['ru']))]],
        resize_keyboard=True,
    )


def stores_keyboard(stores: list, page: int = 0, per_page: int = 8, lang: str = 'ru') -> InlineKeyboardMarkup:
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
        InlineKeyboardButton(text=t(lang, 'btn_search'), callback_data='store_search'),
        InlineKeyboardButton(text=t(lang, 'btn_new_store'), callback_data='store_new'),
    )

    return builder.as_markup()


def images_done_keyboard(count: int, lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, 'btn_done_photos', count=count), callback_data='images_done')
    ]])


def take_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Кнопка для группы ИИ-создателей (всегда по-русски)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Взять', callback_data=f'take_{product_id}')
    ]])


def upload_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Кнопка для группы загрузчиков (всегда по-русски)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='📥 Загрузить в панель', callback_data=f'upload_{product_id}')
    ]])
