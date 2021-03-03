from abc import ABCMeta, abstractmethod
from typing import Tuple, List


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
        return DummyQuestion(id, 'question'+id, 'answer'+id)
    
    async def find(self, content: str, page: int, page_size: int) -> Tuple[int, List[str]]:
        start = page * page_size
        end = start + page_size
        if end > self._total:
            end = self._total
        return self._total, [str(i) for i in range(start, end)]

