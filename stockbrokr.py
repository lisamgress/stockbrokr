import os, requests, csv, decimal
from StringIO import StringIO
from passlib.hash import pbkdf2_sha512
from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, login_user, logout_user, login_required, current_user
from forms import LoginForm, SellSharesForm, RegistrationForm, LookupStockForm, BuySharesForm

STOCK_API_URL = 'http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1d1t1c1ohgv&e=.csv'
STARTING_BALANCE = 10000.00

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "postgresql://stockbrokr@localhost/stockbrokr")
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

app.config.update(dict(
    SECRET_KEY='development key',
    DEBUG=True
))

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
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

    def verify_password(self, entered_password):
        return pbkdf2_sha512.verify(entered_password, self.password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.user_id)

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


@login_manager.user_loader
def load_user(userid):
    return User.query.get(int(userid))

@app.template_filter('currency')
def format_currency(amount):
    return '{:20,.2f}'.format(amount)

def get_first_row(data):
    first_row = None
    for row in data:
        first_row = row
        break
    return first_row

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
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash('No user found with that email address.  Please register.', 'alert-info')
            return redirect(url_for('register'))
        if not user.verify_password(form.password.data):
            flash('Invalid email or password', 'alert-warning')
            return redirect(url_for('login'))
        login_user(user)
        flash("user logged in", 'alert-success')
        return redirect(request.args.get("next") or url_for("index")) # why isn't 'next' working?
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You were logged out', 'alert-success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=request.form['email']).first()
        if user:
            flash("That email address is already associated with an account. Please log in.", 'alert-warning')
            return redirect(url_for('login'))
        new_user = User(form.email.data, form.password.data, form.first_name.data, form.last_name.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('%s, thanks for registering!' %(new_user.first_name), 'alert-success')
        return redirect(url_for('index'))

    return render_template('register.html', form=form)

@app.route('/portfolio')
@login_required
def portfolio():
    for stock in current_user.portfolio:
        row = get_stock_info(stock.symbol)
        stock.current_price = row[1]
        db.session.add(stock)
        db.session.commit()
    return render_template('portfolio.html')

@app.route('/lookup_stock', methods=['GET', 'POST'])
@login_required
def lookup_stock():
    form = LookupStockForm()
    stock_info = {}
    if form.validate_on_submit():
        row = get_stock_info(form.symbol.data)

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
    return render_template('lookup.html', stock_info=stock_info, form=form)


@app.route('/buy_stock/<symbol>', methods=['GET', 'POST'])
@login_required
def buy_stock(symbol):
    form = BuySharesForm()
    row = get_stock_info(symbol)
    current_price = decimal.Decimal(row[1])
    if form.validate_on_submit():        
        already_own = Stock.query.filter_by(owner_id=current_user.user_id, symbol=symbol).first()
        if already_own:
            flash("You already own that stock", 'alert-info')
            return redirect(url_for('portfolio'))
        shares = form.shares.data

        total_purchase_price = shares * current_price
        if total_purchase_price <= current_user.balance:
            new_stock = Stock(current_user.user_id, symbol, shares, current_price)
            db.session.add(new_stock)
            current_user.balance -= total_purchase_price
            db.session.add(current_user)
            db.session.commit()
            flash("You purchased %s share(s) of %s." % (shares, symbol), 'alert-success')
            return redirect(url_for('portfolio'))
        else:
            flash("You don't have enough BrokrBucks to buy that many shares", 'alert-warning')
    return render_template('buy.html', current_price=current_price, symbol=symbol, form=form)

@app.route('/sell_stock/<symbol>', methods=['GET', 'POST'])
@login_required
def sell_stock(symbol):
    form = SellSharesForm()
    stock_info = Stock.query.filter_by(owner_id=current_user.user_id, symbol=symbol).first()
    if form.validate_on_submit():
        shares_for_sale = form.shares.data
        if shares_for_sale > stock_info.shares:
            flash("You don't have that many shares to sell.", 'alert-warning')
            return redirect(url_for('sell_stock', symbol=symbol))

        current_user.balance += shares_for_sale * stock_info.current_price
        remaining_shares = stock_info.shares - shares_for_sale
        if remaining_shares == 0:
            db.session.delete(stock_info)
        else:
            stock_info.shares -= shares_for_sale
            db.session.add(stock_info)
        db.session.add(current_user)
        db.session.commit()
        flash("You sold %s share(s) of %s" % (shares_for_sale, symbol), 'alert-success')
        return redirect(url_for('portfolio'))
    return render_template('sell.html', stock_info=stock_info, form=form)



if __name__== '__main__':
    app.run(debug=True)