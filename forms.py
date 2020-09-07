from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import EqualTo, InputRequired


class SignupForm(FlaskForm):
    username = StringField("Username", [InputRequired()])
    password = PasswordField("Password", [InputRequired(), EqualTo('password_verify', message='Passwords must match')])
    password_verify = PasswordField("Retype Password", [InputRequired()])


class LoginForm(FlaskForm):
    username = StringField("Username", [InputRequired()])
    password = PasswordField("Password", [InputRequired()])
