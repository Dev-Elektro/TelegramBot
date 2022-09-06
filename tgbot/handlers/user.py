from aiogram import Dispatcher
from aiogram.types import Message
from tgbot.services.setting_default_commands import set_user_commands


async def user_start(message: Message):
    await message.reply(f"Hello, user!")
    await set_user_commands(message.bot, message.from_user.id)


def register_user(dp: Dispatcher):
    dp.register_message_handler(user_start, commands=["start"], state="*")
