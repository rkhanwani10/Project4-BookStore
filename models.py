from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

class Book(Base):
    __tablename__ = 'book'

    isbn = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    author = Column(String)
    genre = Column(String)

engine = create_engine('sqlite:///books.db')

Base.metadata.create_all(engine)
