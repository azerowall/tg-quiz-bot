
from aiogram import Bot, Dispatcher, executor, types

import config


bot = Bot(token=config.API_TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Hello, I'm quiz bot!")



def run_bot():
    executor.start_polling(dp, skip_updates=True)