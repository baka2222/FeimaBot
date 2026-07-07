import os
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy import select

from bot.database.connection import session_maker
from bot.database.models import Product, Staff
from bot.locales import t

router = Router()

UPLOADER_GROUP_ID = os.getenv('UPLOADER_GROUP_ID')


@router.callback_query(F.data.startswith('upload_'))
async def handle_upload_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.removeprefix('upload_'))
    tg_id = callback.from_user.id
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        staff = (await session.execute(
            select(Staff).where(Staff.tg_id == tg_id)
        )).scalar_one_or_none()

        if not staff:
            await callback.answer(t('ru', 'upload_not_found'), show_alert=True)
            return

        lang = staff.lang or 'ru'

        if staff.role != 'uploader':
            await callback.answer(t(lang, 'upload_not_uploader'), show_alert=True)
            return

        product = (await session.execute(
            select(Product).where(Product.id == product_id)
        )).scalar_one_or_none()

        if product is None:
            await callback.answer(t(lang, 'upload_already'), show_alert=True)
            return

        if product.uploader_id is not None:
            await callback.answer(t(lang, 'upload_already'), show_alert=True)
            return

        product.uploader_id = staff.id
        product.uploaded_at = now
        product.updated_at = now
        await session.commit()
        staff_name = staff.name

    # Помечаем сообщение в группе загрузчиков хештегом и убираем кнопку
    hashtag = '#' + staff_name.replace(' ', '_')
    try:
        if callback.message.caption is not None:
            original = html_decoration.unparse(
                callback.message.caption or '',
                callback.message.caption_entities or [],
            )
            await callback.message.edit_caption(
                caption=f'{original}\n\n📥 Загрузил: {hashtag}',
                reply_markup=None,
                parse_mode='HTML',
            )
        else:
            original = html_decoration.unparse(
                callback.message.text or '',
                callback.message.entities or [],
            )
            await callback.message.edit_text(
                text=f'{original}\n\n📥 Загрузил: {hashtag}',
                reply_markup=None,
                parse_mode='HTML',
            )
    except Exception:
        pass

    await callback.answer(t(lang, 'upload_taken'), show_alert=True)
