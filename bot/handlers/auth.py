from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, Contact
from sqlalchemy import select

from bot.database.connection import session_maker
from bot.database.models import Staff
from bot.keyboards.keyboards import (
    language_keyboard, contact_keyboard, remove_keyboard, searchman_menu,
)
from bot.locales import t
from bot.states.states import AuthStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        t('ru', 'choose_language'),
        reply_markup=language_keyboard(),
    )
    await state.set_state(AuthStates.choosing_language)


@router.callback_query(AuthStates.choosing_language, F.data.startswith('lang_'))
async def cb_choose_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.removeprefix('lang_')
    await state.update_data(lang=lang)
    await callback.message.delete()
    await callback.message.answer(
        t(lang, 'share_phone'),
        reply_markup=contact_keyboard(lang),
    )
    await state.set_state(AuthStates.waiting_contact)
    await callback.answer()


@router.message(AuthStates.waiting_contact, F.contact)
async def handle_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    contact: Contact = message.contact
    phone = int(''.join(filter(str.isdigit, contact.phone_number)))

    async with session_maker() as session:
        result = await session.execute(select(Staff).where(Staff.phone == phone))
        staff = result.scalar_one_or_none()

        if not staff:
            await message.answer(
                t(lang, 'not_registered'),
                reply_markup=remove_keyboard(),
            )
            await state.clear()
            return

        staff.tg_id = message.from_user.id
        staff.lang = lang
        staff.registred = True
        staff.updated_at = datetime.now(timezone.utc)
        await session.commit()

        role = staff.role
        name = staff.name

    await state.clear()

    if role == 'searchman':
        await message.answer(
            t(lang, 'welcome_searchman', name=name),
            reply_markup=searchman_menu(lang),
        )
    elif role == 'ai_creator':
        await message.answer(
            t(lang, 'welcome_ai_creator', name=name),
            reply_markup=remove_keyboard(),
        )
    elif role == 'uploader':
        await message.answer(
            t(lang, 'welcome_uploader', name=name),
            reply_markup=remove_keyboard(),
        )


@router.message(AuthStates.waiting_contact)
async def wrong_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await message.answer(t(lang, 'use_contact_button'))


@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    if await state.get_state() is None:
        await message.answer(t(lang, 'no_active_op'))
        return
    await state.clear()
    await message.answer(t(lang, 'cancelled'), reply_markup=searchman_menu(lang))
