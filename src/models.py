
from sqlalchemy import Column, Integer, String, DateTime, Boolean, MetaData, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Quiz(Base):
    __tablename__ = 'quiz'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)

    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
    
    def __repr__(self):
        return f"<Quiz {self.id} {self.name}>"

class Question(Base):
    __tablename__ = 'question'

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey('quiz.id'), nullable=False)
    # id вопроса в БД ЧГК 
    ext_id = Column(String(50), nullable=False)

    quiz = relationship('Quiz', backref='questions')

    def __init__(self, quiz_id, ext_id):
        self.quiz_id = quiz_id
        self.ext_id = ext_id

    def __repr__(self):
        return f"<Question {self.ext_id}>"

class QuizResult(Base):
    __tablename__ = 'quizresult'
    
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey('quiz.id'), nullable=False)
    user_id = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    end_time = Column(DateTime, nullable=True)

    quiz = relationship('Quiz', backref='results')

    def set_score(self, good, total):
        self.score = good // total * 100

    def increment_score(self, total = None):
        if total is None:
            total = len(self.questions_results)
        good = self.score / 100 * total
        good += 1
        self.set_score(good, total)

    def all_answers_right(self):
        return self.score == 100
    

    def __init__(self, quiz_id, user_id, score, end_time):
        self.quiz_id = quiz_id
        self.user_id = user_id
        self.score = score
        self.end_time = end_time

    def __repr__(self):
        return f"<QuizResult qid = {self.quiz_id} uid = {self.user_id} score = {self.score}>"


class QuestionResult(Base):
    __tablename__ = 'useranswer'

    id = Column(Integer, primary_key=True)
    quiz_result_id = Column(Integer, ForeignKey('quizresult.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('question.id'), nullable=False)
    text = Column(String(100), nullable=False)
    result = Column(Boolean, nullable=False)

    quiz_result = relationship('QuizResult', backref='questions_results')
    question = relationship('Question')

    def __init__(self, quiz_result_id, question_id, text, result):
        self.quiz_result_id = quiz_result_id
        self.question_id = question_id
        self.text = text
        self.result = result

    def __repr__(self):
        return f"<UserAnswer {self.result} \"{self.text}\">"
