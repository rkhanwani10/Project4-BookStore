from models import Base, Department, Patient, User
from flask import Flask, render_template, redirect, jsonify, request, url_for, abort, g, make_response
from flask.ext.httpauth import HTTPBasicAuth
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine, desc
from datetime import datetime
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import requests
import json

auth = HTTPBasicAuth()

engine = create_engine('sqlite:///patientRecords.db')

Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

app = Flask(__name__)

CLIENT_ID = json.loads(open('client_secrets.json').read())['web']['client_id']

@auth.verify_password
def verify_password(username_or_token, password):
    user_id = User.verify_auth_token(username_or_token)
    if user_id is None:
        user = session.query(User).filter_by(username=username_or_token).first()
        if (user is None) or (not user.verify_password(password)):
            return False
    else:
        user = session.query(User).filter_by(id=user_id).one()
    g.user = user
    return True

@auth.login_required
def get_auth_token():
    token = g.user.generate_auth_token()
    return jsonify({'token': token.decode('ascii')})

@app.route('/users/new', methods=['POST'])
def newUser():
    username = request.json.get('username')
    password = request.json.get('password')
    check_existing = session.query(User).filter_by(username=username).first()
    if username is None or password is None or check_existing is not None:
        abort(400)
    new_user = User(username=username)
    new_user.hashPassword(password)
    session.add(new_user)
    session.commit()
    return jsonify({'username': new_user.username}), 201

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/')
@app.route('/records')
def showDepartments():
    departments = session.query(Department).order_by(Department.department_name).all()
    recently_admitted = session.query(Patient).order_by(desc(Patient.date_of_admission)).all()
    return render_template('home.html', departments=departments,
        patients=recently_admitted)

@app.route('/records/<department>/patients')
def showPatients(department):
    departments = session.query(Department).order_by(Department.department_name).all()
    joined = session.query(Patient).join(Patient.department)
    patients = joined.filter_by(department_name=department).all()
    return render_template('home.html', departments=departments,
        patients=patients)

@app.route('/records/<int:patient_id>/')
def viewPatient(patient_id):
    patient = session.query(Patient).filter_by(id=patient_id).one()
    department_id = patient.department_id
    department = session.query(Department).filter_by(id=department_id).one()
    department_name = department.department_name
    return render_template('viewPatient.html', patient=patient, department_name=department_name)

@app.route('/records/<department>/patients.JSON')
def showDepartmentPatientsJSON(department):
    departments = session.query(Department).order_by(Department.department_name).all()
    joined = session.query(Patient).join(Patient.department)
    patients = joined.filter_by(department_name=department).all()
    patients_to_jsonify = []
    for patient in patients:
        patients_to_jsonify.append(patient.serialize(department))
    return jsonify(patients=patients_to_jsonify)

@app.route('/records/<name>.JSON')
def viewPatientsJSON(name):
    patients = session.query(Patient).filter_by(name=name).all()
    patients_to_jsonify = []
    for patient in patients:
        department_id = patient.department_id
        department = session.query(Department).filter_by(id=department_id).one()
        department_name = department.department_name
        patients_to_jsonify.append(patient.serialize(department_name))
    return jsonify(patients=patients_to_jsonify)

@app.route('/records/patient/new', methods=['GET','POST'])
def newPatient():
    if request.method == 'POST':
        department_name = request.form['department_name']
        department = session.query(Department).filter_by(department_name=department_name).one()
        date_of_admission = request.form['date_of_admission']
        dt = datetime.strptime(date_of_admission, "%Y-%m-%d")
        newPatient = Patient(name=request.form['name'], age=int(request.form['age']),
            notes=request.form['notes'], date_of_admission=dt, department_id=department.id)
        session.add(newPatient)
        session.commit()
        return redirect(url_for('showPatients', department=department_name))
    else:
        return render_template('newPatient.html')

@app.route('/records/<int:patient_id>/delete', methods=['GET','POST'])
def deletePatient(patient_id):
    patient = session.query(Patient).filter_by(id=patient_id).one()
    department_id = patient.department_id
    department = session.query(Department).filter_by(id=department_id).one()
    department_name = department.department_name
    if request.method == 'POST':
        session.delete(patient)
        session.commit()
        return redirect(url_for('showPatients', department=department_name))
    else:
        url = url_for('showPatients',department=department_name)
        return render_template('deletePatient.html', patient_name=patient.name, url=url)

@app.route('/records/<int:patient_id>/edit', methods=['GET','POST'])
def editPatient(patient_id):
    patient = session.query(Patient).filter_by(id=patient_id).one()
    if request.method == 'POST':
        if request.form['name']:
            patient.name = request.form['name']
        if request.form['age']:
            patient.age = request.form['age']
        if request.form['date_of_admission']:
            dt = datetime.strptime(request.form['date_of_admission'], "%Y-%m-%d")
            patient.date_of_admission = dt
        if request.form['department_name']:
            dep_name = request.form['department_name']
            department = session.query(Department).filter_by(department_name=dep_name).one()
            patient.department_id = department.id
        # ignored checking empty notes to enable removing notes from patient
        # records. Value set to patient's stored notes in html template
        patient.notes = request.form['notes']
        session.commit()
        return redirect(url_for('viewPatient',patient_id=patient_id))
    else:
        return render_template('editPatient.html',patient=patient)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
