from aiogram import Dispatcher
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


async def admin_start(message: Message):
    await message.reply("Hello, admin!", reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton("SHARE_CONTACT", request_contact=True)
            ]
        ],
        resize_keyboard=True,
    ))


async def admin_stop(message: Message):
    await message.answer("ok", reply_markup=ReplyKeyboardRemove())


def register_admin(dp: Dispatcher):
    dp.register_message_handler(admin_start, commands=["start"], state="*", is_admin=True)
    dp.register_message_handler(admin_stop, commands=["stop"], state="*", is_admin=True)
