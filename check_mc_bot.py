import mysql.connector
from mysql.connector import Error
import requests
from requests.exceptions import RequestException
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from discord.ext import commands
import discord
import datetime
import asyncio

# ========================================
# Настройки для включения и выключения ботов
# ========================================
ENABLE_DISCORD_BOT = True
ENABLE_TELEGRAM_BOT = True

# ========================================
# Настройки для подключения к базе данных
# ========================================
DB_CONFIG = {
    'host': 'localhost',
    'database': 'check_mc_bot',
    'user': 'check_mc_bot',
    'password': 'password'
}

# ========================================
# Настройки таблицы
# ========================================
TABLE_SETTINGS = {
    'name': 'checkers_name',
    'columns': {
        'id': 'INT NOT NULL AUTO_INCREMENT',
        'username_id': 'VARCHAR(20) NOT NULL',
        'name': 'VARCHAR(255) COLLATE utf8mb4_general_ci DEFAULT NULL',
        'mc_name': 'VARCHAR(255) COLLATE utf8mb4_general_ci NOT NULL',
        'result': "ENUM('Success', 'Failed') COLLATE utf8mb4_general_ci NOT NULL",
        'time': 'TIME DEFAULT NULL'
    },
    'primary_key': 'id'
}

# ========================================
# Токен для Discord бота
# ========================================
DISCORD_TOKEN = 'YOUR_TOKEN'

# ========================================
# ID канала, в котором бот будет работать
# ========================================
TARGET_CHANNEL_ID = 1275189334785523803

# ========================================
# Токен для Telegram бота
# ========================================
TELEGRAM_TOKEN = 'YOUR_TOKEN'

# Функция для подключения к базе данных
def create_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            create_table_if_not_exists(connection)
            return connection
    except Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None
        
# Создание таблицы, если она не существует
def create_table_if_not_exists(conn):
    cursor = conn.cursor()
    columns_definition = ", ".join([f"`{col}` {definition}" for col, definition in TABLE_SETTINGS['columns'].items()])
    create_table_query = f"""
        CREATE TABLE IF NOT EXISTS `{TABLE_SETTINGS['name']}` (
            {columns_definition},
            PRIMARY KEY (`{TABLE_SETTINGS['primary_key']}`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """
    cursor.execute(create_table_query)
    conn.commit()
    cursor.close()

# Функция для записи данных в базу данных
def log_check(user_id, username, nickname, result, time):
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = f"INSERT INTO `{TABLE_SETTINGS['name']}` (username_id, name, mc_name, result, time) VALUES (%s, %s, %s, %s, %s)"
        data = (user_id, username, nickname, result, time)
        cursor.execute(query, data)
        connection.commit()
        cursor.close()
        connection.close()

# Telegram бот
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Приветствую!\n Чтобы выполнить проверку просто введите ник ^^\n\n Доступные команды:\n · /list - показывает последние 20 проверок. \n · /start - показывает это сообщение.\n\nАвтор: @m1fanya."
    )

async def check_license(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    nickname = update.message.text.strip()
    url = f"https://api.mojang.com/users/profiles/minecraft/{nickname}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except RequestException:
        await update.message.reply_text(f"❌ Не удалось найти игрока с именем {nickname}!")
        log_check(user_id, username, nickname, 'Failed', update.message.date)
        return

    if response.status_code == 200:
        data = response.json()
        result = f"✅ Игрок {data['name']} имеет лицензию! ^^"
        await update.message.reply_text(result)
        log_check(user_id, username, nickname, 'Success', update.message.date)

async def list_checks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = f"SELECT mc_name, result, time FROM `{TABLE_SETTINGS['name']}` WHERE username_id = %s ORDER BY time ASC LIMIT 20"
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if rows:
            result_text = "\n".join([f"Никнейм: {row[0]}, Результат: {row[1]}, Время: {row[2]}" for row in rows])
        else:
            result_text = "Нет проверок для отображения."
        
        await update.message.reply_text(result_text)
    else:
        await update.message.reply_text("Ошибка подключения к базе данных.")

# Discord бот
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(name="start")
async def discord_start(ctx):
    await ctx.send("Приветствую! Чтобы выполнить проверку просто введите ник ^^\n\n Доступные команды:\n · !list - показывает последние 20 проверок. \n · !start - показывает это сообщение.\n\nАвтор: @m1fanya.")

@bot.command(name="list")
async def discord_list_checks(ctx):
    user_id = ctx.author.id
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = f"SELECT mc_name, result, time FROM `{TABLE_SETTINGS['name']}` WHERE username_id = %s ORDER BY time ASC LIMIT 20"
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if rows:
            result_text = "\n".join([f"Никнейм: {row[0]}, Результат: {row[1]}, Время: {row[2]}" for row in rows])
        else:
            result_text = "Нет проверок для отображения."
        
        await ctx.send(result_text)
    else:
        await ctx.send("Ошибка подключения к базе данных.")

@bot.event
async def on_message(message):
    target_channel_id = TARGET_CHANNEL_ID

    if message.channel.id != target_channel_id:
        return  # Игнорируем сообщения не из целевого канала

    if message.author == bot.user:
        return  # Игнорируем сообщения от бота

    # Обработка команд
    await bot.process_commands(message)

    user_id = message.author.id
    username = message.author.name
    nickname = message.content.strip()

    # Если сообщение не является командой
    if nickname and not message.content.startswith(bot.command_prefix):
        url = f"https://api.mojang.com/users/profiles/minecraft/{nickname}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except RequestException:
            await message.channel.send(f"❌ Не удалось найти игрока с именем {nickname}!")
            log_check(user_id, username, nickname, 'Failed', datetime.datetime.now())
            return

        if response.status_code == 200:
            data = response.json()
            result = f"✅ Игрок {data['name']} имеет лицензию! ^^"
            await message.channel.send(result)
            log_check(user_id, username, nickname, 'Success', datetime.datetime.now())

async def main():
    if ENABLE_TELEGRAM_BOT:
        # Запуск Telegram бота
        telegram_application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        telegram_application.add_handler(CommandHandler('start', start))
        telegram_application.add_handler(CommandHandler('list', list_checks))
        telegram_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_license))

        # Запуск Telegram бота в отдельной задаче
        await telegram_application.initialize()
        await telegram_application.start()
        await telegram_application.updater.start_polling()

    if ENABLE_DISCORD_BOT:
        # Запуск Discord бота
        await bot.start(DISCORD_TOKEN)

# Запуск основного цикла событий
if __name__ == '__main__':
    asyncio.run(main())
