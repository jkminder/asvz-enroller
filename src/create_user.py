#!/usr/bin/env python
from getpass import getpass
import sys
import secrets
from passlib.hash import sha256_crypt
from flask_sqlalchemy import SQLAlchemy 
from flask import current_app, Flask
from app import db, User

flask_app = Flask(__name__)
flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///../../instance/asvz.db"
# create the extension
flask_app = SQLAlchemy()
# create the extension
db = SQLAlchemy()
db.init_app(flask_app)

# initialize the app with the extension
def main():
    """Main entry point for script."""
    with flask_app.app_context():
        db.metadata.create_all(db.engine)

        print('Enter username: ')
        username = input()
        password = secrets.token_urlsafe(16)

        user = User(
            username=username, 
            password=sha256_crypt.hash(password),
            asvz_username="", 
            asvz_password="",
            asvz_organisation="",
            authenticated=False,
            linked=False,
            verified=False,
            chat_id=0,
            access_token=secrets.token_urlsafe(16)
        )
        db.session.add(user)
        db.session.commit()
        print('User created with password: \n{}'.format(password))


if __name__ == '__main__':
    sys.exit(main())