#!/usr/bin/env python
"""Create a new admin user able to view the /reports endpoint."""
from getpass import getpass
import sys
import secrets
from passlib.hash import sha256_crypt
from flask import current_app
from app import db, User
from app import app as flask_app

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