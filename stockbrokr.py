import os
from passlib.hash import pbkdf2_sha512
from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "postgresql://stockbrokr@localhost/stockbrokr")
db = SQLAlchemy(app)

app.config.update(dict(
    SECRET_KEY='development key',
    DEBUG=True
))

class User(db.Model):
	user_id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(150), unique=True)
	password = db.Column(db.String(255))
	first_name = db.Column(db.String(50))
	last_name = db.Column(db.String(80))
	balance = db.Column(db.Integer)
	portfolio = db.relationship('Stock', backref='owner')

	def __init__(self, email, password, first_name, last_name):
		self.email = email
		self.password = pbkdf2_sha512.encrypt(password)
		self.first_name = first_name
		self.last_name = last_name
		self.balance = 10000

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
			password_entered = request.form['password'].encode('UTF8')
			password_stored = user.password.encode('UTF8')
			if pbkdf2_sha512.verify(password_entered, password_stored):
				session['logged_in'] = user.user_id
				flash(user.first_name + ", you were logged in")
				return redirect(url_for('index'))
			else:
				error = 'Invalid password'
		else:
			error = "Email not found.  Please create an account"
			return render_template('register.html', error=error)
	return render_template('login.html', error=error)


@app.route('/logout')
def logout():
	session.pop('logged_in', None)
	flash('You were logged out')
	return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
	error = None
	if request.method == 'POST':
		user = User.query.filter_by(email=request.form['email']).first()
		if user:
			error = "That email address is already associated with an account"
		else:
			if request.form['password'] != request.form['confirm_password']:
				error = "Confirmed password must match password"
			else:
				new_user = User(request.form['email'],
								request.form['password'],
								request.form['f_name'],
								request.form['l_name'])
				db.session.add(new_user)
				db.session.commit()
				session['logged_in'] = new_user.user_id
				flash(new_user.first_name + ", thanks for registering")
				return redirect(url_for('index'))
	return render_template('register.html', error=error)


if __name__== '__main__':
	app.run(debug=True)