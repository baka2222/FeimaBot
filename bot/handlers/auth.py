from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Contact
from sqlalchemy import select

from bot.database.connection import session_maker
from bot.database.models import Staff
from bot.keyboards.keyboards import contact_keyboard, remove_keyboard, searchman_menu
from bot.states.states import AuthStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        'Добро пожаловать в Feima Bot!\nДля входа поделитесь своим номером телефона:',
        reply_markup=contact_keyboard(),
    )
    await state.set_state(AuthStates.waiting_contact)


@router.message(AuthStates.waiting_contact, F.contact)
async def handle_contact(message: Message, state: FSMContext):
    contact: Contact = message.contact
    phone = int(''.join(filter(str.isdigit, contact.phone_number)))

    async with session_maker() as session:
        result = await session.execute(select(Staff).where(Staff.phone == phone))
        staff = result.scalar_one_or_none()

        if not staff:
            await message.answer(
                '❌ Вы не найдены в системе.\nОбратитесь к администратору для регистрации.',
                reply_markup=remove_keyboard(),
            )
            await state.clear()
            return

        staff.tg_id = message.from_user.id
        staff.registred = True
        staff.updated_at = datetime.now(timezone.utc)
        await session.commit()

        role = staff.role
        name = staff.name

    await state.clear()

    if role == 'searchman':
        await message.answer(
            f'✅ Добро пожаловать, {name}!\nВаша роль: Поисковик товаров.',
            reply_markup=searchman_menu(),
        )
    elif role == 'ai_creator':
        await message.answer(
            f'✅ Добро пожаловать, {name}!\nВаша роль: ИИ-создатель контента.\n\n'
            'Ожидайте задания в группе — нажмите «Взять» на опубликованном товаре.',
            reply_markup=remove_keyboard(),
        )


@router.message(AuthStates.waiting_contact)
async def wrong_contact(message: Message):
    await message.answer('Пожалуйста, воспользуйтесь кнопкой для отправки номера телефона.')


@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer('Нет активной операции.')
        return
    await state.clear()
    await message.answer('❌ Операция отменена.', reply_markup=searchman_menu())
