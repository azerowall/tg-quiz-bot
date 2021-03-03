import asyncio
from chgk import DummyQuestionStorage


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
    total, questions_ids = await qstorage.find('test', 0, TOTAL + 1)
    assert TOTAL == total, 'wrong total number'
    assert total == len(questions_ids)
    for i, id in enumerate(questions_ids):
        assert id == str(i)