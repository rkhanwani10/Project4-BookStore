from models import Base, Department, Patient, User
from flask import Flask, render_template, redirect, jsonify, request, url_for
from flask import abort, g, make_response, flash
from flask import session as login_session
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
import random
import string
import os

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
        users_query = session.query(User)
        user = users_query.filter_by(username=username_or_token).first()
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
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    if login_session.get('state') is not None:
        del login_session['state']
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/oauth/google', methods=['POST'])
def gconnect():
    # If this request does not have `X-Requested-With` header,
    # this could be a CSRF
    check_state = request.args.get("state") == login_session['state']
    if (not request.headers.get('X-Requested-With')) or (not check_state):
        abort(403)
    auth_code = request.data
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(auth_code)
        if login_session.get('credentials') is not None:
            del login_session['credentials']
        login_session['credentials'] = credentials
    except FlowExchangeError:
        err_msg = 'Failed to upgrade the authorization code.'
        response = make_response(json.dumps(err_msg), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    gapi_url = 'https://www.googleapis.com/'
    url = gapi_url + ('oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Get user info
    h = httplib2.Http()
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    name = data['name']
    email = data['email']

    # see if user exists, if it doesn't make a new one
    user = session.query(User).filter_by(email=email).first()
    if not user:
        user = User(username=name, email=email)
        session.add(user)
        session.commit()

    if login_session.get('user_id') is not None:
        del login_session['user_id']
    login_session['user_id'] = user.id

    # STEP 4 - Make token
    token = user.generate_auth_token()

    # STEP 5 - Send back token to the client
    return jsonify({'token': token.decode('ascii')})


@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    h = httplib2.Http()
    try:
        credentials.revoke(h)
    except Exception:
        access_token = credentials.access_token
        response = requests.get(
                    credentials.revoke_uri + '?token=' + access_token)
    del login_session['credentials']
    del login_session['user_id']
    del login_session['state']

    return redirect(url_for('login'))


@app.route('/')
@app.route('/records')
def showDepartments():
    if login_session.get('credentials') is None:
        return redirect(url_for('login'))
    departments_query = session.query(Department)
    departments = departments_query.order_by(Department.department_name).all()
    pquery = session.query(Patient)
    recently_admitted = pquery.order_by(desc(Patient.date_of_admission)).all()
    return render_template('home.html', departments=departments,
                           patients=recently_admitted, active="recent_admits")


@app.route('/records/<department>/patients')
def showPatients(department):
    if login_session.get('credentials') is None:
        return redirect(url_for('login'))
    departments_query = session.query(Department)
    departments = departments_query.order_by(Department.department_name).all()
    joined = session.query(Patient).join(Patient.department)
    patients = joined.filter_by(department_name=department)
    patients_ordered = patients.order_by(Patient.name).all()
    return render_template('home.html', departments=departments,
                           patients=patients_ordered,
                           active=department.replace(' ', ''))


@app.route('/records/<int:patient_id>/')
def viewPatient(patient_id):
    if login_session.get('credentials') is None:
        return redirect(url_for('login'))
    patient = session.query(Patient).filter_by(id=patient_id).one()
    department_id = patient.department_id
    department = session.query(Department).filter_by(id=department_id).one()
    department_name = department.department_name
    return render_template('viewPatient.html', patient=patient,
                           department_name=department_name)


@app.route('/records/<department>/patients.JSON')
def showDepartmentPatientsJSON(department):
    # if login_session.get('credentials') is None:
    #     return redirect(url_for('login'))
    departments_query = session.query(Department)
    departments = departments_query.order_by(Department.department_name).all()
    joined = session.query(Patient).join(Patient.department)
    patients = joined.filter_by(department_name=department).all()
    patients_to_jsonify = []
    for patient in patients:
        patients_to_jsonify.append(patient.serialize(department))
    return jsonify(patients=patients_to_jsonify)


@app.route('/records/<name>.JSON')
def viewPatientsJSON(name):
    # if login_session.get('credentials') is None:
    #     return redirect(url_for('login'))
    patients = session.query(Patient).filter_by(name=name).all()
    patients_to_jsonify = []
    for patient in patients:
        department_id = patient.department_id
        departments_query = session.query(Department)
        department = departments_query.filter_by(id=department_id).one()
        department_name = department.department_name
        patients_to_jsonify.append(patient.serialize(department_name))
    return jsonify(patients=patients_to_jsonify)


@app.route('/records/<int:patient_id>.JSON')
def viewPatientJSON(patient_id):
    patient = session.query(Patient).filter_by(id=patient_id).one()
    department_id = patient.department_id
    department = session.query(Department).filter_by(id=department_id).one()
    department_name = department.department_name
    return jsonify(patient.serialize(department_name))


@app.route('/records/patient/new', methods=['GET', 'POST'])
def newPatient():
    if login_session.get('credentials') is None:
        return redirect(url_for('login'))
    if request.method == 'POST':
        department_name = request.form['department_name']
        dquery = session.query(Department)
        department = dquery.filter_by(department_name=department_name).one()
        date_of_admission = request.form['date_of_admission']
        dt = datetime.strptime(date_of_admission, "%Y-%m-%d")
        newPatient = Patient(name=request.form['name'],
                             age=int(request.form['age']),
                             notes=request.form['notes'],
                             date_of_admission=dt,
                             department_id=department.id,
                             user_id=login_session['user_id'])
        session.add(newPatient)
        session.commit()
        return redirect(url_for('showPatients', department=department_name))
    else:
        return render_template('newPatient.html')


@app.route('/records/<int:patient_id>/delete', methods=['GET', 'POST'])
def deletePatient(patient_id):
    if login_session.get('credentials') is None:
        return redirect(url_for('login'))
    patient = session.query(Patient).filter_by(id=patient_id).one()
    current_user_id = login_session['user_id']
    if(current_user_id != patient.user_id):
        flash('You are not authorized to delete this record')
        return redirect(url_for('viewPatient', patient_id=patient_id))
    department_id = patient.department_id
    department = session.query(Department).filter_by(id=department_id).one()
    department_name = department.department_name
    if request.method == 'POST':
        session.delete(patient)
        session.commit()
        return redirect(url_for('showPatients', department=department_name))
    else:
        url = url_for('showPatients', department=department_name)
        return render_template('deletePatient.html',
                               patient_name=patient.name, url=url)


@app.route('/records/<int:patient_id>/edit', methods=['GET', 'POST'])
# @auth.login_required
def editPatient(patient_id):
    if login_session.get('credentials') is None:
        return redirect(url_for('login'))
    patient = session.query(Patient).filter_by(id=patient_id).one()
    current_user_id = login_session['user_id']
    if(current_user_id != patient.user_id):
        flash('You are not authorized to edit this record')
        return redirect(url_for('viewPatient', patient_id=patient_id))
    if request.method == 'POST':
        if request.form['name']:
            patient.name = request.form['name']
        if request.form['age']:
            patient.age = request.form['age']
        if request.form['date_of_admission']:
            dt = datetime.strptime(request.form['date_of_admission'],
                                   "%Y-%m-%d")
            patient.date_of_admission = dt
        if request.form['department_name']:
            dep_name = request.form['department_name']
            dquery = session.query(Department)
            department = dquery.filter_by(department_name=dep_name).one()
            patient.department_id = department.id
        # ignored checking empty notes to enable removing notes from patient
        # records. Default value set to patient's stored notes in html template
        patient.notes = request.form['notes']
        session.commit()
        return redirect(url_for('viewPatient', patient_id=patient_id))
    else:
        return render_template('editPatient.html', patient=patient)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
