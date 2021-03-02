import asyncio
import string

from chgk import DummyQuestionStorage, CHGKQuestionStorage


# Простой вариант
# Потом мб заменить на pytest.mark.asyncio из pytest-asyncio
def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


@async_test
async def test_dummy_find():
    TOTAL = 9
    qstorage = DummyQuestionStorage(TOTAL)
    total, questions = await qstorage.find('test', 0, TOTAL + 1)
    assert TOTAL == total, 'wrong total number'
    assert total == len(questions)
    for i, quest in enumerate(questions):
        assert quest.id() == str(i)


@async_test
async def test_chgk_get_by_id():
    id = 'gerbr13/98'
    qs = CHGKQuestionStorage()
    question = await qs.get_by_id(id)
    assert question.id() == id
    s = 'В 2002 году в ходе одной церемонии над Виндзором пролетел самолет времен Второй мировой войны'
    assert question.question_text().find(s) != -1


@async_test
async def test_chgk_find():
    content = 'море'
    page = 0
    page_size = 4
    qs = CHGKQuestionStorage()
    quest = await qs.find(content, page, page_size)
    total = 5150
    id_list = ['leti08.4/4', 'rubr08st/154', 'ukrbr07.7/3', 'uzbek17.4/10']
    assert quest[1] == id_list
    assert quest[0] == total



@async_test
async def test_chgk_check_answer():
    pass