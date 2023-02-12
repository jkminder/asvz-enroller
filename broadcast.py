#!/usr/bin/env python
import sys
from flask import current_app, Flask
from flask_sqlalchemy import SQLAlchemy 
from argparse import ArgumentParser
import asyncio
from telegram import Bot
import yaml

from src.database import User, db

""" Script for broadcasting messages to all users. """

if __name__ == '__main__':
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///asvz.db"
    # create the extension
    db.init_app(app)

    # load config
    config = None
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    args = ArgumentParser()
    args.add_argument('-m', '--message', type=str, required=True)

    args = args.parse_args()

    print("Broadcasting message...")
    print(args.message)

    bot = Bot(token=config["bot"]["token"])

    with app.app_context():
        users = db.session.execute(db.select(User)).scalars().all()
        for user in users:
            if user.verified == 1:
                print('Sending message to user {}'.format(user.username))
                asyncio.run(bot.send_message(chat_id=user.chat_id, text=args.message))

            else:
                print('User {} is not verified'.format(user.username))