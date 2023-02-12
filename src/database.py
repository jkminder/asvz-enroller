from flask_sqlalchemy import SQLAlchemy
import yaml

# create the extension
db = SQLAlchemy()

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
