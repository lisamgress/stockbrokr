from flask.ext.wtf import Form
from wtforms import StringField, PasswordField, SubmitField, IntegerField
from wtforms.validators import Required, Length, Email, NumberRange, EqualTo, Optional

class RegistrationForm(Form):
	first_name = StringField('First name', validators=[Required(), Length(1, 50)])
	last_name = StringField('Last name', validators=[Required(), Length(1, 80)])
	email = StringField('Email', validators=[Required(), Length(1, 255), Email()])
	password = PasswordField('Password', validators=[Required(), Length(1, 30), ])
	confirm = PasswordField('Confirm password', validators=[Required(), Length(1, 30), 
		EqualTo('password', message="Passwords must match")])
	submit = SubmitField('Register')

class LoginForm(Form):
	email = StringField('Email', validators=[Required(), Length(1, 255), Email()])
	password = PasswordField('Password', validators=[Required(), Length(1, 30)])
	submit = SubmitField('Log in')

class LookupStockForm(Form):
	symbol = StringField('Ticker symbol', validators=[Required(), Length(1, 10)])
	submit = SubmitField('Look up')

class BuySharesForm(Form):
	shares = IntegerField('Shares', validators=[Required(), 
		NumberRange(min=1, message="Enter a whole number greater than zero")])
	submit = SubmitField('Buy shares')
	# always shows 'required' error mssg - fix this.

class SellSharesForm(Form):
	shares = IntegerField('Shares', validators=[Required(), 
		NumberRange(min=1, message="Enter a whole number greater than zero")])
	submit = SubmitField('Sell shares')
	# always shows 'required' error mssg - fix this.