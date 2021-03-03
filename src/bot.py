import logging
import math
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.callback_data import CallbackData

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

import config
import chgk
from models import Base, Quiz, Question, QuizResult, QuestionResult

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

engine = create_engine(config.DATABASE_URL)
Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)
Base.metadata.create_all(engine)

bot = Bot(token=config.API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


#question_storage = chgk.DummyQuestionStorage(100)
question_storage = chgk.CHGKQuestionStorage()



class session_scope:
    def __enter__(self):
        self._sess = Session()
        return self._sess

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self._sess.rollback()
        self._sess.close()
        if exc_val:
            raise


QUIZZES_LIST_CD = CallbackData('quizzes', 'page')
QUIZ_CD = CallbackData('quiz', 'quiz_id', 'action')
class QuizActions:
    SHOW = 0
    REMOVE = 1

QUIZ_RESULTS_LIST_CD = CallbackData('quiz_results', 'quiz_id', 'page')
QUIZ_RESULT_CD = CallbackData('quiz_result', 'quiz_result_id', 'action')
class QuizResultActions:
    SHOW = 0
    MANUAL_CHECK = 1

QUIZ_RESULT_MANUAL_CHECK_CD = CallbackData('quiz_manual_check', 'quiz_result_id', 'wrong_answer_number', 'action')
class ManualCheckActions:
    INITIAL = 0
    ACCEPT = 1
    REJECT = 2


def make_quiz_result(quiz, user_id):
    result = QuizResult(quiz.id, user_id, 0, datetime.now())
    for quest in quiz.questions:
        result.questions_results.append(
            QuestionResult(result.id, quest.id, f"answer{quest.ext_id}", False)
        )
    return result

def init_db(session: Session):
    user_id = 260238017

    quizzes = [
        Quiz(user_id, 'quiz1'),
        Quiz(user_id, 'quiz2'),
        Quiz(user_id, 'quiz3'),
        Quiz(user_id, 'quiz4'),
        Quiz(user_id, 'quiz5'),
    ]
    for q in quizzes:
        q.questions = [
            Question(q.id, '1'),
            Question(q.id, '2'),
        ]
        session.add(q)
        session.flush()
        q.results = [
            make_quiz_result(q, user_id),
        ]

    session.commit()



def get_quiz_link(quiz_id: int):
    return f"t.me/osu_tg_quiz_bot?start={quiz_id}"


@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    words = message.text.split()
    if len(words) == 2:
        quiz_id = int(words[1])
        await start_quiz(quiz_id, message, state)
    else:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.row(
            types.InlineKeyboardButton('New', callback_data='newquiz'),
            types.InlineKeyboardButton('Quizzes', callback_data=QUIZZES_LIST_CD.new('0'))
        )
        await bot.send_message(message.from_user.id, "Hello, I'm quiz bot!", reply_markup=kb)



@dp.message_handler(commands='cancel', state='*')
async def cancel(message: types.Message, state: FSMContext):
    cur_state = await state.get_state()
    if cur_state is None:
        return
    
    logger.info(f"Cancelling state {cur_state}")
    await state.finish()


#
# Create quiz
#

class CreateQuizStates(StatesGroup):
    name = State()
    tag = State()
    count = State()

@dp.callback_query_handler(text="newquiz")
async def new_quiz(query: types.CallbackQuery):
    await query.answer(query.data)
    await CreateQuizStates.name.set()
    await bot.send_message(query.from_user.id, '1️⃣ Step one: The Name!')

@dp.message_handler(state=CreateQuizStates.name)
async def new_quiz_process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text
    await CreateQuizStates.next()
    await bot.send_message(message.from_user.id, '2️⃣ Step two: The Tag!')

@dp.message_handler(state=CreateQuizStates.tag)
async def new_quiz_process_tag(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['tag'] = message.text
    await CreateQuizStates.next()
    await bot.send_message(message.from_user.id, '3️⃣ Step three: The Number! (... of questions, of course)')


@dp.message_handler(state=CreateQuizStates.count)
async def new_quiz_process_count(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    async with state.proxy() as data:
        name, tag, count = data['name'], data['tag'], int(message.text)
    await state.finish()

    with session_scope() as session:
        chgk_questions_ids = await chgk.get_n_random_questions(question_storage, tag, count)
        logger.debug(f"User {user_id}, tag '{tag}', count {count}, ids {chgk_questions_ids}")

        quiz = Quiz(user_id, name)
        for ext_id in chgk_questions_ids:
            quiz.questions.append(Question(quiz.id, ext_id))
        session.add(quiz)
        session.commit()
        link = get_quiz_link(quiz.id)
        await bot.send_message(user_id, f"Done! Quiz: {link}")



#
# Quizzes list
#


def make_pagination_buttons(make_cd, page: int, items_total:int = None):
    pages_count = math.ceil(items_total / config.LIST_PAGE_SIZE)

    prev = make_cd(page - 1) if page > 0 else 'none'
    next = make_cd(page + 1) if page < pages_count - 1 else 'none'
    btns = [
        types.InlineKeyboardButton('<', callback_data=prev),
        types.InlineKeyboardButton(f"· {page + 1} / {pages_count} ·", callback_data='none'),
        types.InlineKeyboardButton('>', callback_data=next)
    ]
    return btns


@dp.callback_query_handler(QUIZZES_LIST_CD.filter())
async def quizzes_list(query: types.CallbackQuery, callback_data: dict):
    page = int(callback_data['page'])
    user_id = query.from_user.id

    await query.answer(str(page + 1))

    with session_scope() as session:
        sqlq = session.query(Quiz).filter(Quiz.user_id == user_id)
        total = sqlq.count()
        items = sqlq.offset(page * config.LIST_PAGE_SIZE).limit(config.LIST_PAGE_SIZE)
    
    kb = types.InlineKeyboardMarkup()
    for i, item in enumerate(items, page * config.LIST_PAGE_SIZE + 1):
        cbdata = QUIZ_CD.new(item.id, QuizActions.SHOW)
        kb.add( types.InlineKeyboardButton(f"{i}. {item.name}", callback_data=cbdata) )

    kb.add( *make_pagination_buttons(QUIZZES_LIST_CD.new, page, total) )

    # TODO - кнопка Back

    await query.message.edit_text("Your quizzes", reply_markup=kb)



@dp.callback_query_handler(QUIZ_CD.filter())
async def quiz_actions(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    quiz_id = int(callback_data['quiz_id'])
    action = int(callback_data['action'])
    await query.answer(quiz_id)

    if action == QuizActions.SHOW:
        with session_scope() as session:
            quiz = session.query(Quiz).get(quiz_id)
            results_count = session.query(QuizResult)\
                .filter((QuizResult.quiz_id == quiz_id) & QuizResult.finished_query()).count()
            text = (
                f"Name: {quiz.name}\n"
                f"Questions: {len(quiz.questions)}\n"
                f"Results: {results_count}\n"
                f"Link: {get_quiz_link(quiz.id)}"
            )
        kb = types.InlineKeyboardMarkup()
        kb.add( types.InlineKeyboardButton('Results',
            callback_data=QUIZ_RESULTS_LIST_CD.new(quiz_id, 0)) )
        kb.add( types.InlineKeyboardButton('Remove',
            callback_data=QUIZ_CD.new(quiz_id, QuizActions.REMOVE)) )
        # TODO теоретически, через quiz_id мы можем найти страницу
        kb.add( types.InlineKeyboardButton('Back',
            callback_data=QUIZZES_LIST_CD.new('0')) )
        await query.message.edit_text(text, reply_markup=kb)
    elif action == QuizActions.REMOVE:
        with session_scope() as  session:
            session.query(Quiz).filter_by(id=quiz_id).delete()
        # TODO лучше показывать список
        await query.message.edit_text("Done")


@dp.callback_query_handler(QUIZ_RESULTS_LIST_CD.filter())
async def quiz_results_list(query: types.CallbackQuery, callback_data: dict):
    quiz_id = int(callback_data['quiz_id'])
    page = int(callback_data['page'])
    await query.answer(page)

    with session_scope() as session:
        sqlq = session.query(QuizResult)\
            .filter((QuizResult.quiz_id == quiz_id) & QuizResult.finished_query())
        total = sqlq.count()
        items = sqlq.offset(page * config.LIST_PAGE_SIZE).limit(config.LIST_PAGE_SIZE)
    
    kb = types.InlineKeyboardMarkup()
    for item in items:
        user = await bot.get_chat_member(item.user_id, item.user_id)
        kb.add(
            types.InlineKeyboardButton(
                f"@{user.user.username} - {item.score} ({item.end_time.date().strftime(config.DATE_FORMAT)})",
                callback_data=QUIZ_RESULT_CD.new(item.id, QuizResultActions.SHOW)) )
    
    kb.add( *make_pagination_buttons(lambda page: QUIZ_RESULTS_LIST_CD.new(quiz_id, page), page, total) )

    kb.add( types.InlineKeyboardButton('Back',
        callback_data=QUIZ_CD.new(quiz_id, QuizActions.SHOW)) )

    await query.message.edit_text("Quiz results", reply_markup=kb)


@dp.callback_query_handler(QUIZ_RESULT_CD.filter())
async def quiz_result_actions(query: types.CallbackQuery, callback_data: dict):
    quiz_result_id = int(callback_data['quiz_result_id'])
    action = int(callback_data['action'])
    await query.answer('quiz result')

    if action == QuizResultActions.SHOW:
        with session_scope() as session:
            quiz_result = session.query(QuizResult).get(quiz_result_id)
            
            kb = types.InlineKeyboardMarkup()
            if not quiz_result.all_answers_right():
                kb.add( types.InlineKeyboardButton('Manually check wrong answers',
                    callback_data=QUIZ_RESULT_MANUAL_CHECK_CD.new(quiz_result.id, 0, ManualCheckActions.INITIAL)) )
            kb.add( types.InlineKeyboardButton('Back',
                callback_data=QUIZ_RESULTS_LIST_CD.new(quiz_result.quiz_id, 0)) )

            user = await bot.get_chat_member(quiz_result.user_id, quiz_result.user_id)
            
            text = (
                f"Quiz {quiz_result.quiz.name}\n"
                f"User @{user.user.username}\n"
                f"Score {quiz_result.score}\n"
                f"Time {quiz_result.end_time.strftime(config.DATETIME_FORMAT)}\n"
            )
            
            await query.message.edit_text(text, reply_markup=kb)


#
# DB Api
#

# Да-да - я только в конце понял, что удобнее было бы использовать Репозиторий

def repo_start_quiz(session: Session, user_id: int, quiz_id: int):
    quiz_result = QuizResult(quiz_id, user_id, 0, None)
    session.add(quiz_result)
    session.flush()
    return quiz_result.id


def repo_set_answer(session: Session, quiz_result_id: int, question_id: int, answer: str, result: bool):
    try:
        question_result = session.query(QuestionResult)\
            .filter_by(quiz_result_id=quiz_result_id, question_id=question_id).one()
    
        question_result.text = answer
        question_result.result = result
    except NoResultFound:
        question_result = QuestionResult(quiz_result_id, question_id, answer, result)
        session.add(question_result)


def repo_accept_answer(session: Session, quiz_result: QuizResult, question_result: QuestionResult):
    if question_result.result:
        return
    question_result.result = True
    quiz_result.increment_score()


#
# Run Quiz
#


class RunQuizStates(StatesGroup):
    running = State()


async def start_quiz(quiz_id: int, message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    with session_scope() as session:
        quiz = session.query(Quiz).get(quiz_id)
        questions = quiz.questions
        quiz_result_id = repo_start_quiz(session, user_id, quiz_id)

        await RunQuizStates.running.set()
        async with state.proxy() as data:
            data['quiz_id'] = quiz_id
            data['quiz_result_id'] = quiz_result_id
            data['questions'] = [(q.id, q.ext_id) for q in questions]
            data['question_num'] = 0
        
        quiz_info = (
            "Ready for Quiz?\n"
            f"Name: {quiz.name}\n"
            f"Questions: {len(questions)}"
        )
        session.commit()
    await bot.send_message(user_id, quiz_info)
    await run_quiz_iteration(message, state)


@dp.message_handler(state=RunQuizStates.running)
async def run_quiz_iteration(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    is_finish = False
    async with state.proxy() as data:
        quiz_result_id = data['quiz_result_id']
        questions = data['questions']
        qnum = data['question_num']

        has_answer = qnum > 0
        has_question = qnum < len(questions)

        if has_answer:
            with session_scope() as session:
                id, ext_id = questions[qnum - 1]
                chgk_question = await question_storage.get_by_id(ext_id)
                result = chgk_question.check_answer(message.text)
                repo_set_answer(session, quiz_result_id, id, message.text, result)
                session.commit()

        if has_question:
            _, ext_id = questions[qnum]
            chgk_question = await question_storage.get_by_id(ext_id)
            text = chgk_question.question_text()
            await bot.send_message(user_id, text)
        else:
            # finish quiz
            is_finish = True
            with session_scope() as session:
                quiz_result = session.query(QuizResult).get(quiz_result_id)
                questions_results = quiz_result.questions_results
                total = len(questions_results)
                good = sum(int(qr.result) for qr in questions_results if qr.result)
                quiz_result.set_score(good, total)
                quiz_result.end_time = datetime.now()
                assert len(questions) == total
                session.commit()

                text = (
                    f"Done!\n"
                    f"End time: {quiz_result.end_time.strftime(config.DATETIME_FORMAT)}\n"
                    f"Your result {good}/{total} ({quiz_result.score})"
                )
                await bot.send_message(user_id, text)

        qnum += 1
        data['question_num'] = qnum
    
    if is_finish:
        await state.finish()




#
# Run Quiz manual check
#


@dp.callback_query_handler(QUIZ_RESULT_MANUAL_CHECK_CD.filter())
async def manual_check_iteration(query: types.CallbackQuery, state: FSMContext, callback_data: dict):
    quiz_result_id = int(callback_data['quiz_result_id'])
    qnum = int(callback_data['wrong_answer_number'])
    accept_result = int(callback_data['action'])
    has_accept_result = qnum > 0
    
    await query.answer(f'manual check {qnum}')

    with session_scope() as session:
        sqlq = session.query(QuestionResult)\
            .filter_by(quiz_result_id=quiz_result_id, result=False)
        
        question_result = sqlq.offset(qnum).first()

        if has_accept_result and accept_result == ManualCheckActions.ACCEPT:
            quiz_result = session.query(QuizResult).get(quiz_result_id)
            prev_question_result = sqlq.offset(qnum - 1).first()
            repo_accept_answer(session, quiz_result, prev_question_result)
            session.commit()
        
        if question_result is not None:
            question = question_result.question
            ext_id = question.ext_id
            chgk_question = await question_storage.get_by_id(ext_id)
            text = (
                "Question:\n"
                f"`{chgk_question.question_text()}`\n"
                "Right answer:\n"
                f"`{chgk_question.answer_text()}`\n"
                "User answer:\n"
                f"`{question_result.text}`"
            )

            next_qnum = qnum if accept_result == ManualCheckActions.ACCEPT else qnum + 1
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton('<',
                    callback_data=QUIZ_RESULT_CD.new(quiz_result_id, QuizResultActions.SHOW)),

                types.InlineKeyboardButton('𐄂',
                    callback_data=QUIZ_RESULT_MANUAL_CHECK_CD.new(quiz_result_id, next_qnum, ManualCheckActions.REJECT)),
                types.InlineKeyboardButton('🗸',
                    callback_data=QUIZ_RESULT_MANUAL_CHECK_CD.new(quiz_result_id, next_qnum, ManualCheckActions.ACCEPT)),
            )

            await query.message.edit_text(text, reply_markup=kb)
        else:
            # finish
            await query.message.edit_text("Done!")




def run_bot():
    with session_scope() as session:
        init_db(session)
    executor.start_polling(dp, skip_updates=True)

