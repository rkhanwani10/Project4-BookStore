from sqlalchemy import Column, ForeignKey, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from passlib.apps import custom_app_context as pwd_context
import random, string
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired)

Base = declarative_base()

secret_key = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, index=True)
    email = Column(String)
    password_hash = Column(String)

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=600):
        s = Serializer(secret_key,expiration)
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(secret_key)
        try:
            data = s.loads(token)
        except BadSignature:
            return None
        except SignatureExpired:
            return None
        user_id = data['id']
        return user_id

class Department(Base):
    __tablename__ = 'departments'

    id = Column(Integer, primary_key=True)
    department_name = Column(String, nullable=False)

class Patient(Base):
    __tablename__ = 'patients'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    notes = Column(String)
    date_of_admission = Column(Date, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'))
    department = relationship(Department)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship(User)

    def serialize(self, department):
        return {
            'name': self.name,
            'age': self.age,
            'date_of_admission': str(self.date_of_admission),
            'department': department,
            'notes': self.notes
        }

engine = create_engine('sqlite:///patientRecords.db')

Base.metadata.create_all(engine)
