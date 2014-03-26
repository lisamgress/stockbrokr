import os, requests, csv
from StringIO import StringIO
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
        self.balance = 1000000      # in cents

class Stock(db.Model):
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    symbol = db.Column(db.String(10), primary_key=True)
    shares = db.Column(db.Integer)
    purchase_price = db.Column(db.Integer)  # in cents
    current_price = db.Column(db.Integer)   # in cents

    def __init__(self, owner_id, symbol, shares, purchase_price):
        self.owner_id = owner_id
        self.symbol = symbol
        self.shares = shares
        self.purchase_price = purchase_price
        self.current_price = purchase_price

@app.template_filter('currency')
def format_currency(amount):
    return '{:20,.2f}'.format(amount / 100)

def get_first_row(data):
    first_row = None
    for row in data:
        first_row = row
        break
    return first_row


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

@app.route('/portfolio')
def portfolio():
    user = User.query.get(session['logged_in'])
    return render_template('portfolio.html', user=user)

@app.route('/buy_stock', methods=['GET', 'POST'])
def buy_stock():
    data = None
    stock_info = {}
    user = User.query.get(session['logged_in'])
    if request.method == 'POST':
        symbol = request.form['stock_symbol']
        url = 'http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1d1t1c1ohgv&e=.csv' % (symbol)
        r = requests.get(url)
        data = csv.reader(StringIO(r.text))
        row = get_first_row(data)
        stock_info = {
            'symbol' : row[0],
            'current' : row[1],
            'last_updated_day' : row[2],
            'last_updated_time' : row[3],
            'change' : row[4],
            'open' : row[5],
            'daily_high' : row[6],
            'daily_low' : row[7],
            'volume' : row[8]
            }

    return render_template('buy.html', stock_info=stock_info, user=user)


if __name__== '__main__':
    app.run(debug=True)