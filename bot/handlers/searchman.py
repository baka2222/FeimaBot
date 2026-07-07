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
from bot.locales import t, BTN_ADD_PRODUCT
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

@router.message(StateFilter(None), F.text.in_(set(BTN_ADD_PRODUCT.values())))
async def start_add_product(message: Message, state: FSMContext):
    staff = await _get_searchman(message.from_user.id)
    if not staff:
        await message.answer(t('ru', 'no_access'))
        return

    lang = staff.lang or 'ru'
    await state.update_data(staff_id=staff.id, staff_name=staff.name, lang=lang)
    stores = await _fetch_stores()
    await message.answer(
        t(lang, 'choose_store'),
        reply_markup=stores_keyboard(stores, page=0, lang=lang),
        parse_mode='HTML',
    )
    await state.set_state(SearchmanStates.select_store)


# ── Store selection callbacks ──────────────────────────────────────────────

@router.callback_query(SearchmanStates.select_store, F.data.startswith('store_sel_'))
async def cb_select_store(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    store_id = int(callback.data.removeprefix('store_sel_'))
    await state.update_data(store_id=store_id)
    await callback.message.edit_text(t(lang, 'store_selected'))
    await callback.answer()
    await callback.message.answer(t(lang, 'product_name'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_name)


@router.callback_query(SearchmanStates.select_store, F.data.startswith('stores_pg_'))
async def cb_stores_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    page = int(callback.data.removeprefix('stores_pg_'))
    stores = await _fetch_stores()
    await callback.message.edit_text(
        t(lang, 'choose_store'),
        reply_markup=stores_keyboard(stores, page, lang=lang),
        parse_mode='HTML',
    )
    await callback.answer()


@router.callback_query(SearchmanStates.select_store, F.data == 'store_search')
async def cb_store_search(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await callback.message.edit_text(t(lang, 'store_search_prompt'))
    await state.set_state(SearchmanStates.search_store)
    await callback.answer()


@router.callback_query(SearchmanStates.select_store, F.data == 'store_new')
async def cb_store_new(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await callback.message.edit_text(t(lang, 'new_store_name'), parse_mode='HTML')
    await state.set_state(SearchmanStates.add_store_name)
    await callback.answer()


# ── Store text search ──────────────────────────────────────────────────────

@router.message(SearchmanStates.search_store)
async def handle_store_search(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    text = message.text.strip()
    stores = await _fetch_stores(search_text=text)
    if not stores:
        await message.answer(
            t(lang, 'store_search_none', text=text),
            reply_markup=stores_keyboard([], 0, lang=lang),
        )
    else:
        await message.answer(
            t(lang, 'store_search_results', text=text),
            reply_markup=stores_keyboard(stores, 0, lang=lang),
        )
    await state.set_state(SearchmanStates.select_store)


# ── New store FSM ──────────────────────────────────────────────────────────

@router.message(SearchmanStates.add_store_name)
async def handle_new_store_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(new_store_name=message.text.strip())
    await message.answer(t(lang, 'new_store_phone'), parse_mode='HTML')
    await state.set_state(SearchmanStates.add_store_phone)


@router.message(SearchmanStates.add_store_phone)
async def handle_new_store_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    phone_str = ''.join(filter(str.isdigit, message.text.strip()))
    if not phone_str:
        await message.answer(t(lang, 'bad_phone'))
        return

    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        store = Store(name=data['new_store_name'], phone=int(phone_str), created_at=now, updated_at=now)
        session.add(store)
        await session.commit()
        await session.refresh(store)
        store_id, store_name = store.id, store.name

    await state.update_data(store_id=store_id)
    await message.answer(t(lang, 'store_added', name=store_name))
    await message.answer(t(lang, 'product_name'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_name)


# ── Product fields FSM ─────────────────────────────────────────────────────

@router.message(SearchmanStates.product_name)
async def handle_product_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_name=message.text.strip())
    await message.answer(t(lang, 'product_price'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_price)


@router.message(SearchmanStates.product_price)
async def handle_product_price(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_price=message.text.strip())
    await message.answer(t(lang, 'product_size'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_size)


@router.message(SearchmanStates.product_size)
async def handle_product_size(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_size=message.text.strip())
    await message.answer(t(lang, 'product_color'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_color)


@router.message(SearchmanStates.product_color)
async def handle_product_color(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_color=message.text.strip())
    await message.answer(t(lang, 'product_material'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_material)


@router.message(SearchmanStates.product_material)
async def handle_product_material(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_material=message.text.strip())
    await message.answer(t(lang, 'product_characteristics'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_characteristics)


@router.message(SearchmanStates.product_characteristics)
async def handle_product_characteristics(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_characteristics=message.text.strip())
    await message.answer(t(lang, 'product_packaging'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_packaging)


@router.message(SearchmanStates.product_packaging)
async def handle_product_packaging(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await state.update_data(product_packaging=message.text.strip())
    await message.answer(t(lang, 'main_photo'), parse_mode='HTML')
    await state.set_state(SearchmanStates.product_main_image)


# ── Main image ─────────────────────────────────────────────────────────────

@router.message(SearchmanStates.product_main_image, F.photo)
async def handle_product_main_image(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
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
    await message.answer(t(lang, 'main_photo_saved', max=MAX_IMAGES), parse_mode='HTML')


@router.message(SearchmanStates.product_main_image)
async def handle_main_image_wrong(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await message.answer(t(lang, 'send_photo_please'))


# ── Album images ───────────────────────────────────────────────────────────

@router.message(SearchmanStates.product_images, F.photo)
async def handle_album_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    image_ids: list = data.get('image_ids', [])

    if len(image_ids) >= MAX_IMAGES:
        await message.answer(
            t(lang, 'max_reached', max=MAX_IMAGES),
            reply_markup=images_done_keyboard(len(image_ids), lang=lang),
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
        await message.answer(t(lang, 'max_reached_final', count=count, max=MAX_IMAGES))
        await _finalize(message, state)
    else:
        remaining = MAX_IMAGES - count
        await message.answer(
            t(lang, 'photo_added', count=count, max=MAX_IMAGES, remaining=remaining),
            reply_markup=images_done_keyboard(count, lang=lang),
        )


@router.callback_query(SearchmanStates.product_images, F.data == 'images_done')
async def cb_images_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    if not data.get('image_ids'):
        await callback.answer(t(lang, 'add_at_least_one'), show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _finalize(callback.message, state)


@router.message(SearchmanStates.product_images)
async def handle_album_wrong(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    count = len(data.get('image_ids', []))
    await message.answer(
        t(lang, 'send_photo_or_done'),
        reply_markup=images_done_keyboard(count, lang=lang) if count > 0 else None,
    )


# ── Finalize: save Product + send to group ─────────────────────────────────

async def _finalize(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    image_ids: list = data['image_ids']
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        product = Product(
            creator_id=data['staff_id'],
            store_id=data['store_id'],
            main_image_id=data['main_image_id'],
            name=data['product_name'],
            price=data.get('product_price', ''),
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

    # Подпись в группу — ВСЕГДА на русском
    caption = (
        f'🆕 <b>Новый товар!</b>\n\n'
        f'📦 <b>Название:</b> {data["product_name"]}\n'
        f'💰 <b>Цена:</b> {data.get("product_price", "—")}\n'
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
        t(lang, 'product_added', count=len(image_ids)),
        reply_markup=searchman_menu(lang),
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
