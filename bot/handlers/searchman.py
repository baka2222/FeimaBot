import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import insert, select

from bot.database.connection import session_maker
from bot.database.models import Staff, Store, Image, Product, product_images_table
from bot.keyboards.keyboards import (
    stores_keyboard, take_product_keyboard,
    searchman_menu, images_done_keyboard,
)
from bot.states.states import SearchmanStates

router = Router()

MEDIA_ROOT = os.getenv('MEDIA_ROOT', 'admin_panel/media')
GROUP_ID = os.getenv('GROUP_ID')
MAX_IMAGES = 10


async def _get_searchman(tg_id: int) -> Staff | None:
    async with session_maker() as session:
        result = await session.execute(
            select(Staff).where(Staff.tg_id == tg_id, Staff.role == 'searchman')
        )
        return result.scalar_one_or_none()


async def _fetch_stores(search_text: str | None = None) -> list:
    async with session_maker() as session:
        query = select(Store).order_by(Store.name)
        if search_text:
            query = query.where(Store.name.ilike(f'%{search_text}%'))
        result = await session.execute(query)
        return list(result.scalars().all())


async def _save_photo(bot, photo, subfolder: str) -> str:
    filename = f'{uuid.uuid4().hex}.jpg'
    relative_path = f'{subfolder}/{filename}'
    full_path = Path(MEDIA_ROOT) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    await bot.download(photo, destination=str(full_path))
    return relative_path


# ── Entry point ────────────────────────────────────────────────────────────

@router.message(StateFilter(None), F.text == '📦 Добавить товар')
async def start_add_product(message: Message, state: FSMContext):
    staff = await _get_searchman(message.from_user.id)
    if not staff:
        await message.answer('❌ Нет доступа. Войдите через /start.')
        return

    await state.update_data(staff_id=staff.id, staff_name=staff.name)
    stores = await _fetch_stores()
    await message.answer(
        '🏪 <b>Выберите магазин</b>\n\n'
        '⚠️ Указывайте название магазина максимально точно, '
        'чтобы его легко было найти в будущем.\n'
        '🚫 За неверные данные предусмотрен штраф.',
        reply_markup=stores_keyboard(stores, page=0),
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.select_store)


# ── Store selection callbacks ──────────────────────────────────────────────

@router.callback_query(SearchmanStates.select_store, F.data.startswith('store_sel_'))
async def cb_select_store(callback: CallbackQuery, state: FSMContext):
    store_id = int(callback.data.removeprefix('store_sel_'))
    await state.update_data(store_id=store_id)
    await callback.message.edit_text('✅ Магазин выбран.')
    await callback.answer()
    await callback.message.answer(
        '📦 <b>Название товара</b>\n\n'
        'Введите точное название товара так, как оно написано на упаковке или ценнике.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_name)


@router.callback_query(SearchmanStates.select_store, F.data.startswith('stores_pg_'))
async def cb_stores_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.removeprefix('stores_pg_'))
    stores = await _fetch_stores()
    await callback.message.edit_text(
        '🏪 <b>Выберите магазин</b>\n\n'
        '⚠️ Название указывайте точно — по нему потом ищут.\n'
        '🚫 За неверные данные предусмотрен штраф.',
        reply_markup=stores_keyboard(stores, page),
        parse_mode='HTML',
    )
    await callback.answer()


@router.callback_query(SearchmanStates.select_store, F.data == 'store_search')
async def cb_store_search(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('🔍 Введите часть названия магазина или имени владельца:')
    await state.set_state(SearchmanStates.search_store)
    await callback.answer()


@router.callback_query(SearchmanStates.select_store, F.data == 'store_new')
async def cb_store_new(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        '🏪 <b>Новый магазин — Название</b>\n\n'
        'Введите название магазина или имя владельца.\n'
        '⚠️ Указывайте максимально точно — по этому названию его будут находить в списке.\n'
        '🚫 За неверные данные предусмотрен штраф.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.add_store_name)
    await callback.answer()


# ── Store text search ──────────────────────────────────────────────────────

@router.message(SearchmanStates.search_store)
async def handle_store_search(message: Message, state: FSMContext):
    text = message.text.strip()
    stores = await _fetch_stores(search_text=text)
    if not stores:
        await message.answer(
            f'❌ Ничего не найдено по запросу «{text}».\n'
            'Попробуйте другой запрос или добавьте новый магазин:',
            reply_markup=stores_keyboard([], 0),
        )
    else:
        await message.answer(f'🔍 Результаты по «{text}»:', reply_markup=stores_keyboard(stores, 0))
    await state.set_state(SearchmanStates.select_store)


# ── New store FSM ──────────────────────────────────────────────────────────

@router.message(SearchmanStates.add_store_name)
async def handle_new_store_name(message: Message, state: FSMContext):
    await state.update_data(new_store_name=message.text.strip())
    await message.answer(
        '📞 <b>Новый магазин — Телефон</b>\n\n'
        'Введите номер телефона магазина (только цифры, без пробелов и +).\n'
        '🚫 За неверные данные предусмотрен штраф.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.add_store_phone)


@router.message(SearchmanStates.add_store_phone)
async def handle_new_store_phone(message: Message, state: FSMContext):
    phone_str = ''.join(filter(str.isdigit, message.text.strip()))
    if not phone_str:
        await message.answer('❌ Некорректный номер. Введите только цифры:')
        return

    data = await state.get_data()
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        store = Store(name=data['new_store_name'], phone=int(phone_str), created_at=now, updated_at=now)
        session.add(store)
        await session.commit()
        await session.refresh(store)
        store_id, store_name = store.id, store.name

    await state.update_data(store_id=store_id)
    await message.answer(f'✅ Магазин «{store_name}» добавлен!')
    await message.answer(
        '📦 <b>Название товара</b>\n\n'
        'Введите точное название товара так, как оно написано на упаковке или ценнике.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_name)


# ── Product fields FSM ─────────────────────────────────────────────────────

@router.message(SearchmanStates.product_name)
async def handle_product_name(message: Message, state: FSMContext):
    await state.update_data(product_name=message.text.strip())
    await message.answer(
        '📐 <b>Размеры товара</b>\n\n'
        'Укажите размеры (длина × ширина × высота, или S/M/L и т.д.).\n'
        '💡 Если размеров нет — напишите <b>Нету</b>.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_size)


@router.message(SearchmanStates.product_size)
async def handle_product_size(message: Message, state: FSMContext):
    await state.update_data(product_size=message.text.strip())
    await message.answer(
        '🎨 <b>Цвета товара</b>\n\n'
        'Перечислите все доступные цвета через запятую.\n'
        '💡 Если неизвестно — напишите <b>Нету</b>.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_color)


@router.message(SearchmanStates.product_color)
async def handle_product_color(message: Message, state: FSMContext):
    await state.update_data(product_color=message.text.strip())
    await message.answer(
        '🧵 <b>Материал товара</b>\n\n'
        'Укажите из чего сделан товар (хлопок, полиэстер, пластик и т.д.).\n'
        '💡 Если неизвестно — напишите <b>Нету</b>.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_material)


@router.message(SearchmanStates.product_material)
async def handle_product_material(message: Message, state: FSMContext):
    await state.update_data(product_material=message.text.strip())
    await message.answer(
        '📋 <b>Характеристики товара</b>\n\n'
        'Вес, мощность, страна производителя и т.д.\n'
        '💡 Если нечего добавить — напишите <b>Нету</b>.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_characteristics)


@router.message(SearchmanStates.product_characteristics)
async def handle_product_characteristics(message: Message, state: FSMContext):
    await state.update_data(product_characteristics=message.text.strip())
    await message.answer(
        '📦 <b>Комплектация товара</b>\n\n'
        'Что входит в комплект? (например: товар + инструкция + зарядка).\n'
        '💡 Если нет дополнений — напишите <b>Нету</b>.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_packaging)


@router.message(SearchmanStates.product_packaging)
async def handle_product_packaging(message: Message, state: FSMContext):
    await state.update_data(product_packaging=message.text.strip())
    await message.answer(
        '📸 <b>Главное фото товара</b>\n\n'
        'Отправьте одно чёткое главное фото — оно будет обложкой карточки товара.\n'
        '⚠️ За плохое качество фото предусмотрен штраф.',
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.product_main_image)


# ── Main image ─────────────────────────────────────────────────────────────

@router.message(SearchmanStates.product_main_image, F.photo)
async def handle_product_main_image(message: Message, state: FSMContext):
    relative_path = await _save_photo(message.bot, message.photo[-1], 'images')
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        img = Image(image=relative_path, created_at=now, updated_at=now)
        session.add(img)
        await session.flush()
        main_image_id = img.id
        await session.commit()

    await state.update_data(
        main_image_id=main_image_id,
        main_photo_file_id=message.photo[-1].file_id,
        image_ids=[],
    )
    await state.set_state(SearchmanStates.product_images)
    await message.answer(
        '✅ Главное фото сохранено!\n\n'
        f'📸 <b>Фото товара (альбом)</b>\n\n'
        f'Отправляйте фотографии по одной — разные ракурсы, детали, этикетка и т.д.\n'
        f'Максимум {MAX_IMAGES} фото. Когда закончите — нажмите «Готово».',
        parse_mode='HTML',
    )


@router.message(SearchmanStates.product_main_image)
async def handle_main_image_wrong(message: Message):
    await message.answer('❌ Пожалуйста, отправьте фотографию.')


# ── Album images ───────────────────────────────────────────────────────────

@router.message(SearchmanStates.product_images, F.photo)
async def handle_album_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    image_ids: list = data.get('image_ids', [])

    if len(image_ids) >= MAX_IMAGES:
        await message.answer(
            f'❌ Достигнут максимум {MAX_IMAGES} фото. Нажмите «Готово».',
            reply_markup=images_done_keyboard(len(image_ids)),
        )
        return

    relative_path = await _save_photo(message.bot, message.photo[-1], 'images')
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        img = Image(image=relative_path, created_at=now, updated_at=now)
        session.add(img)
        await session.flush()
        image_ids.append(img.id)
        await session.commit()

    await state.update_data(image_ids=image_ids)
    count = len(image_ids)

    if count >= MAX_IMAGES:
        await message.answer(f'✅ Фото {count}/{MAX_IMAGES} — максимум достигнут!')
        await _finalize(message, state)
    else:
        remaining = MAX_IMAGES - count
        await message.answer(
            f'✅ Фото {count}/{MAX_IMAGES} добавлено. Можно ещё {remaining}.',
            reply_markup=images_done_keyboard(count),
        )


@router.callback_query(SearchmanStates.product_images, F.data == 'images_done')
async def cb_images_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('image_ids'):
        await callback.answer('❌ Добавьте хотя бы одно фото.', show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _finalize(callback.message, state)


@router.message(SearchmanStates.product_images)
async def handle_album_wrong(message: Message, state: FSMContext):
    data = await state.get_data()
    count = len(data.get('image_ids', []))
    await message.answer(
        '❌ Пожалуйста, отправьте фотографию.',
        reply_markup=images_done_keyboard(count) if count > 0 else None,
    )


# ── Finalize: save Product + send to group ─────────────────────────────────

async def _finalize(message: Message, state: FSMContext):
    data = await state.get_data()
    image_ids: list = data['image_ids']
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        product = Product(
            creator_id=data['staff_id'],
            store_id=data['store_id'],
            main_image_id=data['main_image_id'],
            name=data['product_name'],
            size=data['product_size'],
            color=data['product_color'],
            material=data['product_material'],
            characteristics=data['product_characteristics'],
            packaging=data['product_packaging'],
            created_at=now,
            updated_at=now,
        )
        session.add(product)
        await session.flush()

        # Link images via ManyToMany junction table
        for img_id in image_ids:
            await session.execute(
                insert(product_images_table).values(product_id=product.id, image_id=img_id)
            )

        await session.commit()
        product_id = product.id

        store = (await session.execute(
            select(Store).where(Store.id == data['store_id'])
        )).scalar_one()

    main_file_id = data['main_photo_file_id']

    caption = (
        f'🆕 <b>Новый товар!</b>\n\n'
        f'📦 <b>Название:</b> {data["product_name"]}\n'
        f'🏪 <b>Магазин:</b> {store.name}\n'
        f'📐 <b>Размеры:</b> {data["product_size"]}\n'
        f'🎨 <b>Цвет:</b> {data["product_color"]}\n'
        f'🧵 <b>Материал:</b> {data["product_material"]}\n'
        f'📋 <b>Характеристики:</b> {data["product_characteristics"]}\n'
        f'📦 <b>Комплектация:</b> {data["product_packaging"]}\n'
        f'👤 <b>Поисковик:</b> {data["staff_name"]}\n'
        f'📸 <b>Фото:</b> {len(image_ids)} шт.'
    )

    await state.clear()
    await message.answer(
        f'✅ <b>Товар успешно добавлен!</b>\n'
        f'📸 Фото товара: {len(image_ids)} шт.',
        reply_markup=searchman_menu(),
        parse_mode='HTML',
    )

    if not GROUP_ID:
        return

    await message.bot.send_photo(
        chat_id=int(GROUP_ID),
        photo=main_file_id,
        caption=caption,
        reply_markup=take_product_keyboard(product_id),
        parse_mode='HTML',
    )
