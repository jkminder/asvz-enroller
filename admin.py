#!/usr/bin/env python
from getpass import getpass
import sys
import secrets
from passlib.hash import sha256_crypt
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy 
from argparse import ArgumentParser

from src.database import User, db

""" Script for creating/reseting/deleting users. """

if __name__ == '__main__':
    args = ArgumentParser()
    args.add_argument('-u', '--username', type=str, required=False, help='Username of the user to create/reset/delete.')
    args.add_argument('-r', '--reset', action='store_true', required=False, help='Reset the user. This will reset all associated data!')
    args.add_argument('-d', '--delete', action='store_true', required=False, help='Delete the user. This will also delete all associated data!')
    args.add_argument('-l', '--list', action='store_true', required=False, help='List all users.')
    args = args.parse_args()

    if not args.username and not args.list:
        print('You need to specify a username!')
        
        sys.exit(1)

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///asvz.db"
    
    db.init_app(app)

    with app.app_context():
        db.metadata.create_all(db.engine)
        
        if args.list:
            users = db.session.execute(db.select(User)).scalars().all()
            print("Users:")
            for user in users:
                print(user.username)
            sys.exit(0)

        if args.reset or args.delete:
            if args.delete:
                print('Deleting user')
            else:
                print('Resetting user')
            user = db.session.query(User).filter(User.username == args.username).first()
            if user:
                db.session.delete(user)
                db.session.commit()
            else:
                print(f"User '{args.username}' does not exist!")
                sys.exit(1)
            if args.delete:
                print('User deleted')
                sys.exit(0)
        else:
            user = db.session.query(User).filter(User.username == args.username).first()
            if user:
                print(f"User '{args.username}' already exists! Add -r/--reset to reset the user.")
                sys.exit(1)
            
        password = secrets.token_urlsafe(16)
        user = User(
            username=args.username, 
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
        print(f"User '{args.username}' created with password: \n{password}")
