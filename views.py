from models import Base, Department, Patient
from flask import Flask, render_template, jsonify, request, url_for, abort, g
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine, desc

engine = create_engine('sqlite:///patientRecords.db')

Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

app = Flask(__name__)

@app.route('/')
def showDepartments():
    departments = session.query(Department).order_by(Department.department_name).all()
    recently_admitted = session.query(Patient).order_by(desc(Patient.date_of_admission)).all()
    return render_template('home.html', departments=departments,
        patients=recently_admitted)

@app.route('/catalog/<department>/items')
def showPatients(deparment):
    departments = session.query(Department).order_by(Department.department_name).all()
    joined = session.query(Patient).join(Patient.department)
    patients = joined.filter_by(department_name=department).all()
    return render_template('home.html', departments=departments,
        patients=patients)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
