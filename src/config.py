import os


API_TOKEN = os.getenv('API_TOKEN')
#DATABASE_URL= 'sqlite:///tg_quiz_bot.db'
DATABASE_URL = 'sqlite:///:memory:'
LIST_PAGE_SIZE = 5
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H.%M.%S'