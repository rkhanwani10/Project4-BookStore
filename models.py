from sqlalchemy import Column, ForeignKey, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

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

    @property
    def serialize(self):
        return {
            'name': self.name,
            'age': self.age,
            'date_of_admission': str(self.date_of_admission),
            'department': self.department_id,
            'notes': self.notes
        }

engine = create_engine('sqlite:///patientRecords.db')

Base.metadata.create_all(engine)
