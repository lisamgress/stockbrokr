import os
from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ["DATABASE_URL"]
db = SQLAlchemy(app)

app.config.update(dict(
    SECRET_KEY='development key',
    DEBUG=True
))

class User(db.Model):
	user_id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(150), unique=True)
	password = db.Column(db.String(30))
	first_name = db.Column(db.String(50))
	last_name = db.Column(db.String(80))
	balance = db.Column(db.Integer)
	portfolio = db.relationship('Stock', backref='owner')

	def __init__(self, email, password):
		self.email = email
		self.password = password

class Stock(db.Model):
	owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
	abbr = db.Column(db.String(10), primary_key=True)
	num_shares = db.Column(db.Integer)


@app.route('/')
def index():
	return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
	error = None
	if request.method == 'POST':
		user = User.query.filter_by(email=request.form['email']).first()
		if user:
			if user.password == request.form['password']:
				session['logged_in'] = user.user_id
				flash("You were logged in")
				return redirect(url_for('index'))
			else:
				error = 'Invalid password'
		else:
			error = "Email not found.  Please create an account"
	return render_template('login.html', error=error)


@app.route('/logout')
def logout():
	session.pop('logged_in', None)
	flash('You were logged out')
	return redirect(url_for('login'))


if __name__== '__main__':
	app.run(debug=True)