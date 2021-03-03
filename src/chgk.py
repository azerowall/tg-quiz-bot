from abc import ABCMeta, abstractmethod
from typing import Tuple, List
import re
import random
import math
import logging
from html import unescape as html_unescape

import aiohttp
import asyncio
from lxml import etree, html


logger = logging.getLogger(__name__)


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
        
        Возвращает колличество страниц и список идентификаторов на запрошенной странице
        """


# Заглушки для тестов

class DummyQuestion(Question):
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
        return self.answer_text() == answer


class DummyQuestionStorage(QuestionStorage):
    def __init__(self, total):
        self._total = total

    async def get_by_id(self, id: str) -> Question:
        return DummyQuestion(id, 'question' + id, 'answer' + id)

    async def find(self, content: str, page: int, page_size: int) -> Tuple[int, List[str]]:
        pages_total = math.ceil(self._total / page_size)
        start = page * page_size
        end = start + page_size
        if end > self._total:
            end = self._total
        return pages_total, [str(i) for i in range(start, end)]


class CHGKQuestion(Question):
    def __init__(self, id, question, answer, other_answer = None):
        self._id = id
        self._question = question
        self._answer = answer
        self._other_answer = other_answer

    def id(self) -> str:
        return self._id

    def question_text(self) -> str:
        return self._question

    def answer_text(self) -> str:
        return self._answer

    def check_answer(self, answer: str) -> bool:
        answer = self.normalize_string(answer)
        return answer == self.normalize_string(self._answer) or answer == self.normalize_string(self._other_answer) \
            if self._other_answer is not None else answer == self.normalize_string(self._answer)

    @staticmethod
    def normalize_string(s: str):
        s = s.lower()
        return re.findall(r'[\w\d]+', s, re.UNICODE)


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

        pages_total = tree.xpath('//li[@class="pager-last last"]/a/@href')[0]
        pages_total = re.search(r'page\=(\d+)', pages_total).group(1)
        pages_total = int(pages_total)

        elems = tree.xpath('//dl[@class="search-results questions-results"]//dd/div[@class="question"]//strong[@class="Question"]//a/@href')
        return pages_total, list(map(lambda x: x.replace('/question/', ''), elems))

    async def get_by_id(self, id: str) -> Question:
        async with aiohttp.ClientSession() as session:
            url = f'https://db.chgk.info/question/{id}/xml'
            async with session.get(url) as response:
                content = await response.text()
                return self.parse_question(id, content)


    def parse_question(self, id: str, content: str) -> Question:
        question_elem = etree.fromstring(content)

        question = question_elem.xpath('//Question/text()')[0]
        answer = question_elem.xpath('//Answer/text()')[0]
        answer = html_unescape(answer)
        pass_criteria = question_elem.xpath('//PassCriteria')
        if len(pass_criteria) > 0:
            pass_criteria = pass_criteria[0].text
            pass_criteria = html_unescape(pass_criteria)
        else:
            pass_criteria = None

        question_elem = html.fromstring(question)
        question = question_elem.xpath('text()')
        question = ''.join(question).strip().replace('\n', ' ')

        razdatka = question_elem.xpath('//div[@class="razdatka"]/text()')
        if len(razdatka) > 0:
            razdatka = ''.join(p.lstrip() for p in razdatka if not p.isspace())
            question = (
                "Раздаточный материал:\n"
                f"{razdatka}\n"
                f"{question}"
            )

        return CHGKQuestion(id, question, answer, pass_criteria)



'''
https://db.chgk.info/question/vse_puchk01_u/5
Это вопрос, который нормально выводится в поиске,
но ссылка на него сразу же редиректит на целый тур. Id тоже меняется.
Итого нет связи 1 к 1 между найденным вопросом и тем, что доступно по ссылке.
Именно поэтому существует этот вынужденный костыль:
при создании квиза будет выполнена попытка загрузки и парсинга всех выбранных вопросов - проблемные будут выброшены.

Также total (количество найденных вопросов) либо не соответствует действительности, либо выводят не равномерное их количество.
'''
async def get_n_random_questions(qs: QuestionStorage, tag: str, count: int) -> List[str]:
    total, _ = await qs.find(tag, 0, 1)

    if total < count:
        raise Exception(f"Found less questions than requested ({total} < {count})")

    total = min(total, 999)

    questions = set()
    while len(questions) != count:
        question_number = random.randint(0, total - 1)
        _, ids = await qs.find(tag, question_number, 1)
        assert len(ids) == 1
        id = ids[0]

        try:
            question = await qs.get_by_id(id)
        except Exception as e: # TODO?
            logger.debug(f"Got exception on question '{id}' => try next question. Exception: {e}")
        else:
            questions.add(id)
    return questions
