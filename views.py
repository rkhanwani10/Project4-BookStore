from flask import Flask, render_template, jsonify, request, url_for, abort, g

app = Flask(__name__)

@app.route('/')
def showCategories():
    return render_template('home.html', genres=['Thriller', 'Romance'],
     latest_items=['Hello','Hi'])

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
