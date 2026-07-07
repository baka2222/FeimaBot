import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy import select

from bot.database.connection import session_maker
from bot.database.models import AiImage, Image, Product, Staff, Store, product_images_table
from bot.keyboards.keyboards import upload_product_keyboard
from bot.locales import t
from bot.states.states import AiCreatorStates

router = Router()

MEDIA_ROOT = os.getenv('MEDIA_ROOT', 'admin_panel/media')
GROUP_ID = os.getenv('GROUP_ID')                     # группа ИИ-создателей
UPLOADER_GROUP_ID = os.getenv('UPLOADER_GROUP_ID')   # группа загрузчиков


@router.callback_query(F.data.startswith('take_'))
async def handle_take_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.removeprefix('take_'))
    tg_id = callback.from_user.id

    async with session_maker() as session:
        staff = (await session.execute(
            select(Staff).where(Staff.tg_id == tg_id)
        )).scalar_one_or_none()

        if not staff:
            await callback.answer(t('ru', 'take_not_found'), show_alert=True)
            return

        lang = staff.lang or 'ru'

        if staff.role != 'ai_creator':
            await callback.answer(t(lang, 'take_not_ai'), show_alert=True)
            return

        existing = (await session.execute(
            select(AiImage).where(AiImage.product_id == product_id).limit(1)
        )).scalar_one_or_none()
        if existing:
            await callback.answer(t(lang, 'take_already'), show_alert=True)
            return

        product = (await session.execute(
            select(Product).where(Product.id == product_id)
        )).scalar_one()

        main_img = (await session.execute(
            select(Image).where(Image.id == product.main_image_id)
        )).scalar_one_or_none()

        additional_imgs = list((await session.execute(
            select(Image)
            .join(product_images_table, Image.id == product_images_table.c.image_id)
            .where(product_images_table.c.product_id == product_id)
        )).scalars().all())

        product_name = product.name
        staff_id = staff.id

    # Редактируем сообщение в группе ИИ-креаторов: убираем кнопку, помечаем взятым
    hashtag = '#' + staff.name.replace(' ', '_')
    try:
        original = html_decoration.unparse(
            callback.message.caption or '',
            callback.message.caption_entities or [],
        )
        await callback.message.edit_caption(
            caption=f'{original}\n\n🎨 Взял: {hashtag}',
            reply_markup=None,
            parse_mode='HTML',
        )
    except Exception:
        pass

    await callback.answer(t(lang, 'take_taken'))

    # Устанавливаем FSM-состояние для лички ИИ-креатора
    private_key = StorageKey(bot_id=callback.bot.id, chat_id=tg_id, user_id=tg_id)
    await state.storage.set_state(private_key, AiCreatorStates.wait_photos)
    await state.storage.set_data(private_key, {
        'product_id': product_id, 'staff_id': staff_id, 'lang': lang,
    })

    try:
        media_root = Path(MEDIA_ROOT)
        media: list[InputMediaPhoto] = []
        caption = t(lang, 'ai_product_photos', name=product_name)

        if main_img:
            main_path = media_root / main_img.image
            if main_path.exists():
                media.append(InputMediaPhoto(
                    media=FSInputFile(str(main_path)), caption=caption, parse_mode='HTML',
                ))

        for img in additional_imgs:
            img_path = media_root / img.image
            if img_path.exists():
                media.append(InputMediaPhoto(media=FSInputFile(str(img_path))))

        if len(media) > 1:
            await callback.bot.send_media_group(chat_id=tg_id, media=media)
        elif len(media) == 1 and main_img:
            await callback.bot.send_photo(
                chat_id=tg_id,
                photo=FSInputFile(str(media_root / main_img.image)),
                caption=caption, parse_mode='HTML',
            )

        await callback.bot.send_message(
            chat_id=tg_id,
            text=t(lang, 'ai_wait_photos', name=product_name),
            parse_mode='HTML',
        )
    except Exception:
        pass  # ИИ-креатор должен хотя бы раз запустить бота


@router.message(AiCreatorStates.wait_photos, F.photo, F.chat.type == 'private')
async def handle_ai_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    photo = message.photo[-1]
    now = datetime.now(timezone.utc)

    filename = f'{uuid.uuid4().hex}.jpg'
    relative_path = f'ai_images/{filename}'
    full_path = Path(MEDIA_ROOT) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    await message.bot.download(photo, destination=str(full_path))

    async with session_maker() as session:
        ai_img = AiImage(
            creator_id=data['staff_id'],
            product_id=data['product_id'],
            image=relative_path,
            created_at=now,
            updated_at=now,
        )
        session.add(ai_img)
        await session.commit()

    await message.answer(t(lang, 'ai_photo_saved'))


@router.message(AiCreatorStates.wait_photos, Command('done'), F.chat.type == 'private')
async def handle_ai_done(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    product_id = data['product_id']
    staff_id = data['staff_id']

    async with session_maker() as session:
        ai_imgs = list((await session.execute(
            select(AiImage)
            .where(AiImage.product_id == product_id, AiImage.creator_id == staff_id)
            .order_by(AiImage.id)
        )).scalars().all())

        if not ai_imgs:
            await message.answer(t(lang, 'ai_done_nothing'))
            return

        product = (await session.execute(
            select(Product).where(Product.id == product_id)
        )).scalar_one()
        store = (await session.execute(
            select(Store).where(Store.id == product.store_id)
        )).scalar_one()
        creator = (await session.execute(
            select(Staff).where(Staff.id == product.creator_id)
        )).scalar_one()
        ai_creator = (await session.execute(
            select(Staff).where(Staff.id == staff_id)
        )).scalar_one()

        product_data = {
            'name': product.name, 'price': product.price or '—',
            'store': store.name, 'size': product.size, 'color': product.color,
            'material': product.material, 'characteristics': product.characteristics,
            'packaging': product.packaging, 'creator': creator.name,
            'ai_name': ai_creator.name,
        }
        ai_paths = [img.image for img in ai_imgs]

    await state.clear()
    await message.answer(t(lang, 'ai_done'))

    if not UPLOADER_GROUP_ID:
        return

    # Подпись в группу загрузчиков — ВСЕГДА на русском
    caption = (
        f'🎨 <b>Готов к загрузке в панель!</b>\n\n'
        f'📦 <b>Название:</b> {product_data["name"]}\n'
        f'💰 <b>Цена:</b> {product_data["price"]}\n'
        f'🏪 <b>Магазин:</b> {product_data["store"]}\n'
        f'📐 <b>Размеры:</b> {product_data["size"]}\n'
        f'🎨 <b>Цвет:</b> {product_data["color"]}\n'
        f'🧵 <b>Материал:</b> {product_data["material"]}\n'
        f'📋 <b>Характеристики:</b> {product_data["characteristics"]}\n'
        f'📦 <b>Комплектация:</b> {product_data["packaging"]}\n'
        f'👤 <b>Поисковик:</b> {product_data["creator"]}\n'
        f'🎨 <b>ИИ-креатор:</b> {product_data["ai_name"]}\n'
        f'📸 <b>ИИ-фото:</b> {len(ai_paths)} шт.'
    )

    media_root = Path(MEDIA_ROOT)
    media: list[InputMediaPhoto] = []
    for i, rel in enumerate(ai_paths):
        p = media_root / rel
        if not p.exists():
            continue
        if i == 0:
            media.append(InputMediaPhoto(
                media=FSInputFile(str(p)), caption=caption, parse_mode='HTML',
            ))
        else:
            media.append(InputMediaPhoto(media=FSInputFile(str(p))))

    if len(media) > 1:
        await message.bot.send_media_group(chat_id=int(UPLOADER_GROUP_ID), media=media)
        # Кнопку нельзя прикрепить к альбому — отдельным сообщением
        await message.bot.send_message(
            chat_id=int(UPLOADER_GROUP_ID),
            text=f'☝️ <b>{product_data["name"]}</b> — заявка на загрузку',
            reply_markup=upload_product_keyboard(product_id),
            parse_mode='HTML',
        )
    elif len(media) == 1:
        await message.bot.send_photo(
            chat_id=int(UPLOADER_GROUP_ID),
            photo=FSInputFile(str(media_root / ai_paths[0])),
            caption=caption,
            reply_markup=upload_product_keyboard(product_id),
            parse_mode='HTML',
        )
