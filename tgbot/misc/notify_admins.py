from aiogram import Bot
from tgbot.misc.broadcaster import broadcast


async def start_notify(bot: Bot, admin_ids: list):
    await broadcast(bot, admin_ids, "Бот запущен!")
