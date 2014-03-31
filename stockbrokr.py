import os, requests, csv, decimal
from StringIO import StringIO
from passlib.hash import pbkdf2_sha512
from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask.ext.sqlalchemy import SQLAlchemy

STOCK_API_URL = 'http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1d1t1c1ohgv&e=.csv'
STARTING_BALANCE = 10000.00

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
    balance = db.Column(db.Numeric)
    portfolio = db.relationship('Stock', backref='owner')

    def __init__(self, email, password, first_name, last_name):
        self.email = email
        self.password = pbkdf2_sha512.encrypt(password)
        self.first_name = first_name
        self.last_name = last_name
        self.balance = STARTING_BALANCE

class Stock(db.Model):
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    symbol = db.Column(db.String(10), primary_key=True)
    shares = db.Column(db.Integer)
    purchase_price = db.Column(db.Numeric)
    current_price = db.Column(db.Numeric)

    def __init__(self, owner_id, symbol, shares, purchase_price):
        self.owner_id = owner_id
        self.symbol = symbol
        self.shares = shares
        self.purchase_price = purchase_price
        self.current_price = purchase_price



@app.template_filter('currency')
def format_currency(amount):
    return '{:20,.2f}'.format(amount)

def get_first_row(data):
    first_row = None
    for row in data:
        first_row = row
        break
    return first_row

def get_current_user():
    if 'logged_in' not in session:
        return None
    return User.query.get(session['logged_in'])

def get_stock_info(symbol):
    url = STOCK_API_URL % (symbol)
    r = requests.get(url)
    data = csv.reader(StringIO(r.text))
    row = get_first_row(data)
    return row

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    user = get_current_user()
    if user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user:
            password_entered = request.form['password'].encode('UTF8')
            password_stored = user.password.encode('UTF8')
            if pbkdf2_sha512.verify(password_entered, password_stored):
                session['logged_in'] = user.user_id
                flash("%s, you were logged in" % (user.first_name), 'alert-success')
                return redirect(url_for('index'))
            else:
                flash("Invalid password", 'alert-danger')
                return redirect(url_for('login'))
        else:
            flash("Email not found.  Please create an account", 'alert-warning')
            return redirect(url_for('register'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out', 'alert-success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user:
            flash("That email address is already associated with an account. Please log in.", 'alert-warning')
            return redirect(url_for('login'))
        else:
            if request.form['password'] != request.form['confirm_password']:
                flash("Confirmed password must match password", 'alert-danger')
                return redirect(url_for('register'))
            else:
                new_user = User(request.form['email'],
                                request.form['password'],
                                request.form['f_name'],
                                request.form['l_name'])
                db.session.add(new_user)
                db.session.commit()
                session['logged_in'] = new_user.user_id
                flash("%s, thanks for registering" % (new_user.first_name ), 'alert-success')
                return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/portfolio')
def portfolio():
    user = get_current_user()
    if not user:
        flash("You must log in to view your portfolio", 'alert-info')
        return redirect(url_for('login'))
    for stock in user.portfolio:
        row = get_stock_info(stock.symbol)
        stock.current_price = row[1]
        db.session.commit()
    return render_template('portfolio.html', user=user)

@app.route('/lookup_stock', methods=['GET', 'POST'])
def lookup_stock():
    # data = None
    stock_info = {}
    user = get_current_user()
    if not user:
        flash("You must log in to look up stocks", 'alert-info')
        return redirect(url_for('login'))
    if request.method == 'POST':
        row = get_stock_info(request.form['symbol'])

        # check if ticker symbol is valid.  
        if 'N/A' in row:
            flash("%s is not a valid ticker symbol." %(row[0]), 'alert-warning')
            return redirect(url_for('lookup_stock'))

        stock_info = {
            'symbol' : row[0],
            'current' : float(row[1]),
            'last_updated_day' : row[2],
            'last_updated_time' : row[3],
            'change' : float(row[4]),
            'open' : float(row[5]),
            'daily_high' : float(row[6]),
            'daily_low' : float(row[7]),
            'volume' : row[8]
            }
    return render_template('buy.html', stock_info=stock_info, user=user)


@app.route('/buy_stock', methods=['GET', 'POST'])
def buy_stock():
    user = get_current_user()
    if not user:
        flash("You must log in to buy shares", 'alert-info')
        return redirect(url_for('login'))
    if request.method == 'POST':        
        symbol = request.form['symbol']
        already_own = Stock.query.filter_by(owner_id=user.user_id, symbol=symbol).first()
        if already_own:
            flash("You already own that stock", 'alert-info')
            return redirect(url_for('portfolio'))
        shares = request.form['shares']
        share_purchase_price = request.form['current']
        total_purchase_price = int(shares) * decimal.Decimal(share_purchase_price)
        if total_purchase_price <= user.balance:
            new_stock = Stock(user.user_id, symbol, shares, share_purchase_price)
            db.session.add(new_stock)
            user.balance -= total_purchase_price
            db.session.commit()
            flash("You purchased %s share(s) of %s." % (shares, symbol), 'alert-success')
            return redirect(url_for('portfolio'))
        else:
            flash("You don't have enough BrokrBucks to buy that many shares", 'alert-warning')
    return redirect(url_for('lookup_stock'))

@app.route('/sell_stock/<symbol>')
def sell_stock(symbol):
    user = get_current_user()
    stock_info = None
    if not user:
        flash("You must log in to buy shares", 'alert-info')
        return redirect(url_for('login'))
    stock_info = Stock.query.filter_by(owner_id=user.user_id, symbol=symbol).first()
    return render_template('sell.html', stock_info=stock_info)


@app.route('/process_sale/<symbol>', methods=['GET', 'POST'])
def process_sale(symbol):
    user = get_current_user()
    if not user:
        flash("You must log in to buy shares", 'alert-info')
        return redirect(url_for('login'))
    if request.method == 'POST':
        stock_info = Stock.query.filter_by(owner_id=user.user_id, symbol=symbol).first()
        shares_for_sale = int(request.form['shares'])
        if shares_for_sale > stock_info.shares:
            flash("You don't have that many shares to sell.", 'alert-danger')
            return redirect(url_for('sell_stock', symbol=symbol))
        user.balance += shares_for_sale * stock_info.current_price
        remaining_shares = stock_info.shares - shares_for_sale
        if remaining_shares == 0:
            db.session.delete(stock_info)
        else:
            stock_info.shares -= shares_for_sale
        db.session.commit()
        flash("You sold %s share(s) of %s" % (shares_for_sale, symbol), 'alert-success')
    return redirect(url_for('portfolio'))



if __name__== '__main__':
    app.run(debug=True)