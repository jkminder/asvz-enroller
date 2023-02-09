#!/usr/bin/env python
import sys
from flask import current_app, Flask
from argparse import ArgumentParser
from flask_sqlalchemy import SQLAlchemy 
from bot import send_message, Response
from app import User
import asyncio

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///../../instance/asvz.db"
# create the extension
db = SQLAlchemy()
db.init_app(app)

if __name__ == '__main__':
    args = ArgumentParser()
    args.add_argument('--message', type=str, required=True)

    args = args.parse_args()

    print("Broadcasting message...")
    print(args.message)

    with app.app_context():
        users = db.session.execute(db.select(User)).scalars().all()
        for user in users:
            if user.verified:
                print('Sending message to user {}'.format(user.username))
                response = Response(user.chat_id, args.message)
                asyncio.run(send_message(response))

            else:
                print('User {} is not verified'.format(user.username))