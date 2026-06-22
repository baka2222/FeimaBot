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
from bot.database.models import AiImage, Image, Product, Staff, product_images_table
from bot.states.states import AiCreatorStates

router = Router()

MEDIA_ROOT = os.getenv('MEDIA_ROOT', 'admin_panel/media')


@router.callback_query(F.data.startswith('take_'))
async def handle_take_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.removeprefix('take_'))
    tg_id = callback.from_user.id

    async with session_maker() as session:
        staff_res = await session.execute(select(Staff).where(Staff.tg_id == tg_id))
        staff = staff_res.scalar_one_or_none()

        if not staff:
            await callback.answer(
                '❌ Вы не найдены в системе. Сначала войдите в бота через /start.',
                show_alert=True,
            )
            return

        if staff.role != 'ai_creator':
            await callback.answer(
                '❌ Только ИИ-создатели могут брать задания.',
                show_alert=True,
            )
            return

        existing_res = await session.execute(
            select(AiImage).where(AiImage.product_id == product_id).limit(1)
        )
        if existing_res.scalar_one_or_none():
            await callback.answer('❌ Этот товар уже взят другим ИИ-создателем.', show_alert=True)
            return

        prod_res = await session.execute(select(Product).where(Product.id == product_id))
        product = prod_res.scalar_one()

        # Главное фото
        main_img_res = await session.execute(
            select(Image).where(Image.id == product.main_image_id)
        )
        main_img = main_img_res.scalar_one_or_none()

        # Доп. фото товара (M2M)
        add_imgs_res = await session.execute(
            select(Image)
            .join(product_images_table, Image.id == product_images_table.c.image_id)
            .where(product_images_table.c.product_id == product_id)
        )
        additional_imgs = list(add_imgs_res.scalars().all())

        product_name = product.name
        staff_id = staff.id
        staff_name = staff.name

    # Редактируем сообщение в группе: добавляем хэштег, убираем кнопку
    hashtag = '#' + staff_name.replace(' ', '_')
    try:
        original = html_decoration.unparse(
            callback.message.caption or '',
            callback.message.caption_entities or [],
        )
        await callback.message.edit_caption(
            caption=f'{original}\n\n{hashtag}',
            reply_markup=None,
            parse_mode='HTML',
        )
    except Exception:
        pass  # сообщение могло быть уже изменено

    await callback.answer('✅ Задание взято!')

    # Устанавливаем FSM-состояние для личного чата ИИ-создателя
    private_key = StorageKey(bot_id=callback.bot.id, chat_id=tg_id, user_id=tg_id)
    await state.storage.set_state(private_key, AiCreatorStates.wait_photos)
    await state.storage.set_data(private_key, {'product_id': product_id, 'staff_id': staff_id})

    try:
        # Сначала отправляем альбом фото товара
        media_root = Path(MEDIA_ROOT)
        media: list[InputMediaPhoto] = []

        if main_img:
            main_path = media_root / main_img.image
            if main_path.exists():
                media.append(InputMediaPhoto(
                    media=FSInputFile(str(main_path)),
                    caption=f'📦 <b>{product_name}</b>\n\nФото товара для ИИ-обработки:',
                    parse_mode='HTML',
                ))

        for img in additional_imgs:
            img_path = media_root / img.image
            if img_path.exists():
                media.append(InputMediaPhoto(media=FSInputFile(str(img_path))))

        if len(media) > 1:
            await callback.bot.send_media_group(chat_id=tg_id, media=media)
        elif len(media) == 1:
            await callback.bot.send_photo(
                chat_id=tg_id,
                photo=FSInputFile(str(media_root / main_img.image)),
                caption=f'📦 <b>{product_name}</b>\n\nФото товара для ИИ-обработки:',
                parse_mode='HTML',
            )

        # Затем инструкция
        await callback.bot.send_message(
            chat_id=tg_id,
            text=(
                f'📸 Жду ваши ИИ-фотки!\n\n'
                f'📦 <b>Товар:</b> {product_name}\n\n'
                f'Отправляйте готовые фотографии по одной.\n'
                f'Когда закончите — напишите /done'
            ),
            parse_mode='HTML',
        )
    except Exception:
        pass  # ИИ-создатель должен хотя бы раз запустить бота


@router.message(AiCreatorStates.wait_photos, F.photo, F.chat.type == 'private')
async def handle_ai_photo(message: Message, state: FSMContext):
    data = await state.get_data()
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

    await message.answer('✅ Фото сохранено! Отправьте ещё или /done для завершения.')


@router.message(AiCreatorStates.wait_photos, Command('done'), F.chat.type == 'private')
async def handle_ai_done(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('✅ Готово! Все фотки сохранены.\nОжидайте следующего задания в группе.')
