import unittest
import asyncio
from chgk import DummyQuestionStorage

def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


class TestDummy(unittest.TestCase):
    @async_test
    async def test_find(self):
        TOTAL = 9
        qstorage = DummyQuestionStorage(TOTAL)
        total, questions = await qstorage.find('test', 0, TOTAL + 1)
        self.assertEqual(TOTAL, total, 'wrong total number')
        self.assertEqual(total, len(questions))
        for i, quest in enumerate(questions):
            self.assertEqual(quest.id(), str(i))

if __name__ == '__main__':
    unittest.main()