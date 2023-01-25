from flask import Flask, request, render_template, redirect, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from passlib.hash import sha256_crypt
from wtforms import Form, StringField, validators, PasswordField, SelectField
import secrets
from loguru import logger
from flask_sqlalchemy import SQLAlchemy

# Hack to fix dependency issues for create_user
# TODO: Make this better!
if __name__ == "__main__":
    from utils import load_token, encrypt
    from enroller import ORGANISATIONS
else:
    ORGANISATIONS = {}

class LoginForm(Form):
    username = StringField('Username', [validators.DataRequired()])
    password = PasswordField('Password', [validators.DataRequired()])

class ASVZCredentialsForm(Form):
    username = StringField('ASVZ Username', [validators.DataRequired()])
    password = PasswordField('ASVZ Password', [validators.DataRequired()])
    organisation = SelectField('Organisation', choices=ORGANISATIONS.keys(), validators=[validators.DataRequired()])

class AccessToken(Form):
    access_token = StringField('Access Token', render_kw={'readonly': True})
    telegram_account = StringField('Linked Telegram Account', render_kw={'readonly': True})

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///asvz.db"
# initialize the app with the extension

login_manager = LoginManager()
login_manager.init_app(app)

# create the extension
db = SQLAlchemy()
db.init_app(app)

class User(db.Model):
    """An admin user capable of viewing reports.

    :param str username: email address of user
    :param str password: encrypted password for the user
    :param bool authenticated: whether the user has been authenticated
    """
    __tablename__ = 'user'

    username = db.Column(db.String, primary_key=True)
    password = db.Column(db.String)
    asvz_username = db.Column(db.String)
    asvz_password = db.Column(db.String)
    asvz_organisation = db.Column(db.String)
    authenticated = db.Column(db.Boolean, default=False)
    linked = db.Column(db.Boolean, default=False)
    verified = db.Column(db.Integer, default=-1)
    chat_id = db.Column(db.Integer, default=0)
    access_token = db.Column(db.String, default="")
    telegram_username = db.Column(db.String, default="")

    def is_active(self):
        """True, as all users are active."""
        return True

    def get_id(self):
        """Return the email address to satisfy Flask-Login's requirements."""
        return self.username

    def is_authenticated(self):
        """Return True if the user is authenticated."""
        return self.authenticated

    def is_anonymous(self):
        """False, as anonymous users aren't supported."""
        return False


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.username == user_id)).scalar()


# define a list of users and their corresponding passwords

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect('/welcome')
    else:
        return render_template('index.html', form=LoginForm())
        
@app.route('/login', methods=['POST'])
def login():
    form = LoginForm(request.form)
    if form.validate():
        username = request.form['username']
        password = request.form['password']
        user = db.session.execute(db.select(User).where(User.username == username)).scalar()
        if user:
            if sha256_crypt.verify(password, user.password):
                login_user(user)
                return redirect('/welcome')
        return render_template('index.html', error='Invalid username or password', form=form)
    else:
        return render_template('index.html', form=form)

@app.route('/credentials', methods=['POST'])
@login_required
def credentials():
    form = ASVZCredentialsForm(request.form)
    if form.validate():
        user = current_user
        user.asvz_username = request.form['username']
        user.asvz_password = encrypt(request.form['password'], app_secret)
        user.asvz_organisation = request.form['organisation']
        user.access_token = secrets.token_urlsafe(16)
        user.telegram_username = ""
        user.linked = False
        user.chat_id = 0
        user.verified = -1
        db.session.commit()
        return redirect('/welcome')
    else:
        return render_template('welcome.html', user=current_user, form=form, token=AccessToken(data={'access_token': current_user.access_token}))

@app.route('/welcome')
@login_required
def welcome():
    # get newest information from database
    user = db.session.execute(db.select(User).where(User.username == current_user.username)).scalar()
    form_data = {'username': user.asvz_username, 'organisation': user.asvz_organisation, 'password': 'placeholder' if user.asvz_password else None}
    return render_template('welcome.html', user=current_user, form=ASVZCredentialsForm(data=form_data), token=AccessToken(data={'access_token': user.access_token, 'telegram_account': "Not yet linked!" if not user.telegram_username else user.telegram_username}))

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

if __name__ == '__main__':
    global app_secret
    app_secret = load_token('secret.txt')
    app.secret_key = app_secret
    app.run(debug=True, host= '0.0.0.0')    