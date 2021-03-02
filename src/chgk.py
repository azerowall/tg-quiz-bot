from abc import ABCMeta, abstractmethod
from typing import Tuple, List
import aiohttp
import asyncio
from lxml import html
import re


class Question:
    """Интерфейс вопроса БД ЧГК"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def id(self) -> str:
        """Идентификатор вопроса. Представляет собой часть URL.

        Пример:
        URL: "https://db.chgk.info/question/ef01.2/3"
        id: "ef01.2/3"
        """

    @abstractmethod
    def question_text(self) -> str:
        """Текст вопроса, выводимый пользователю"""

    @abstractmethod
    def answer_text(self) -> str:
        """Текст ответа, выводимый пользователю."""

    @abstractmethod
    def check_answer(self, answer: str) -> bool:
        """Проверка ответа"""

    def __repr__(self):
        return f"<chgk.Question {self.id()}>"


class QuestionStorage:
    __metaclass__ = ABCMeta

    @abstractmethod
    async def get_by_id(self, id: str) -> Question:
        """Возвращает вопрос по его id"""

    @abstractmethod
    async def find(self, content: str, page: int, page_size: int) -> Tuple[int, List[str]]:
        """Поиск вопросов по контенту
        
        Возвращает колличество найденных вопросов и список идентификаторов
        """


# Заглушки для тестов

class DummyQuestion(Question):
    def __init__(self, id, question, answer):
        self._id = id
        self._question = question
        self._answer = answer

    def id(self) -> str:
        return self._id

    def question(self) -> str:
        return self._question

    def answer(self) -> str:
        return self._answer

    def check_answer(self, answer: str) -> bool:
        return self.answer() == answer


class DummyQuestionStorage(QuestionStorage):
    def __init__(self, total):
        self._total = total

    async def get_by_id(self, id: str) -> Question:
        return DummyQuestion(id, 'question' + id, 'answer' + id)

    async def find(self, content: str, page: int, page_size: int) -> Tuple[int, List[str]]:
        start = page * page_size
        end = start + page_size
        if end > self._total:
            end = self._total
        return self._total, [await self.get_by_id(str(i)) for i in range(start, end)]


class CHGKQuestion(Question):
    def __init__(self, id, question, answer):
        self._id = id
        self._question = question
        self._answer = answer

    def id(self) -> str:
        return self._id

    def question_text(self) -> str:
        return self._question

    def answer_text(self) -> str:
        return self._answer

    def check_answer(self, answer: str) -> bool:
        if answer == self._answer:
            return True
        return False


class CHGKQuestionStorage(QuestionStorage):
    async def find(self, content: str, page: int, page_size: int) -> Tuple[int, List[str]]:
        async with aiohttp.ClientSession() as session:
            url = f'https://db.chgk.info/search/questions/{content}/types123/limit{page_size}?page={page}'
            async with session.get(url) as response:
                result = await response.text()
                return self.parse_result(result)

    def parse_result(self, content):
        tree = html.fromstring(content)
        elems = tree.xpath('//h2[@class="title"]/text()')[1]
        total = re.findall(r'\d+', elems)

        elems = tree.xpath('//dl[@class="search-results questions-results"]//dd/div[@class="question"]//strong[@class="Question"]//a/@href')
        return int(total[0]), list(map(lambda x: x.replace('/question/', ''), elems))

    async def get_by_id(self, id: str) -> Question:
        async with aiohttp.ClientSession() as session:
            url = f'https://db.chgk.info/question/{id}'
            async with session.get(url) as response:
                content = await response.text()
                quest_res = self.parse_question(content)[0]
                answer = self.parse_question(content)[1]
                quest = CHGKQuestion(id, quest_res, answer)
                return quest

    def parse_question(self, content) -> Question:
        tree = html.fromstring(content)
        elems = tree.xpath('//p/text()')
        return elems[1].replace('\n', ' ').strip(), elems[3].strip()




