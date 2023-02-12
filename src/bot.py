from loguru import logger  
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, TypeHandler, ConversationHandler
from telegram.ext.filters import ChatType 
from telegram import Bot
from threading import Thread
from queue import Queue
import time
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
import re
from datetime import datetime
import pytz
import yaml

from enroller import verify_login, LESSON_BASE_URL, get_enroller, CREDENTIALS_UNAME, LessonStarted, LoginFailed
from utils import decrypt, load_token
from app import db, User, app as flask_app


#### CONFIG ####


# logging
logger.add("logs/bot.log", rotation="500 MB")
################

#### GLOBALS ####
# ConversationHandler states
DELETE, CONFIRM = range(2)
response_queue = Queue()

jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///instance/jobs.db')
}
executors = {
    'default': ProcessPoolExecutor(3)
}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, timezone=pytz.timezone("CET"))

# load config
config = None
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)
#################

#### MESSAGES ####
# registration
WELCOME = "Welcome {0}! You are now authorized. Verifying your login credentials..."
VALID_CREDENTIALS = "Your login credentials have been verified. Your account is now linked to this telegram account. Send /help for more information on how to use me."
INVALID_CREDENTIALS = f"Your login credentials are not valid and your authorization has been retracted. Please visit {config['app']['url']} to change them and reauthorize."
CREDENTIAL_NO_LONGER_VALID = f"Sorry, your login credentials are invalid. You are no longer authorized to use this bot. Please register again on {config['app']['url']}."
NOT_YET_VALIDATED = "Your login credentials are not yet verified. This might take some minutes. Resubmit the job in a few minutes. You will be notified when you're credentials have been verified."

# enrolment
JOB_SUBMITTED = "Job '{0}' has been submitted."
NO_URL_FOUND = f"Could not find a lesson url in your message. It should look like {LESSON_BASE_URL}/tn/lessons/ followed by some number."
LESSON_STARTED = "Sorry, the lesson {0} has started and I could not find a place for you."
ERROR_ENROLLING = "An error occured while enrolling you for the lesson. Please try again later."
ENROLL_SUCCESS = "You have been successfully enrolled for {0}!"
NO_JOBS = "You have no open enrolment jobs."

# delete
DELETE_NO_NUMBER = "Please provide a job number."
DELETE_NUMBER_NOTFOUND = "Job number not found. Try again."
DELETE_VALIDATE = "Are you sure you want to delete job '{0}'?"
DELETE_CONFIRMATION = "Job has been deleted."

# help
HELP = """Send me a link to an ASVZ lesson and I will enroll you. You can directly share a lesson with me from the ASVZ app. Send /jobs to see a list of open enrolment jobs. With /delete {jobnumber} you can remove specific jobs. The jobnumber can be found with /jobs."""

# other
UNKNOWN_COMMAND = "Sorry, I didn't understand that command."

#### HELPERS ####

def get_user_from_token(token):
    with flask_app.app_context():
        return db.session.execute(db.select(User).where(User.access_token == token)).scalar()

def get_user_from_chat_id(chat_id):
    with flask_app.app_context():
        return db.session.execute(db.select(User).where(User.chat_id == chat_id)).scalar()

def get_user_from_username(username, with_context=True):
    if with_context:
        with flask_app.app_context():
            return db.session.execute(db.select(User).where(User.username == username)).scalar()
    else:
        return db.session.execute(db.select(User).where(User.username == username)).scalar()

def set_user_data(db_user, user, chat):
    with flask_app.app_context():
        db_user = db.session.execute(db.select(User).filter_by(username=db_user.username)).scalar()
        db_user.telegram_username = user.username
        db_user.chat_id = chat.id
        db_user.linked = True
        db_user.verified = 1
        db.session.commit()

def reset_token(user):
    with flask_app.app_context():
        db_user = db.session.execute(db.select(User).filter_by(username=user.username)).scalar()
        db_user.access_token = ""
        db_user.asvz_username = ""
        db_user.verified = -1
        db.session.commit()

def enroller_summary(enroller):
    return f"{enroller.lesson_start.strftime('%d.%m.%y %H:%M')} - {enroller.lesson_title} ({enroller.lesson_location})"

def job_summary(job):
    return enroller_summary(job.args[0])

def enroll(enroller, chat_id):
    logger.info(f"{enroller.creds[CREDENTIALS_UNAME]} - Started enrollment for {enroller_summary(enroller)}")
    try:
        enroller.enroll()
    except LessonStarted as e:
        response = Response(chat_id, LESSON_STARTED.format(enroller_summary(enroller)))
    except LoginFailed as e:
        response = Response(chat_id, CREDENTIAL_NO_LONGER_VALID)
        user = get_user_from_chat_id(chat_id)
        reset_token(user)
    except Exception as e:
        logger.error(e)
        response = Response(chat_id, ERROR_ENROLLING)
    else:
        response = Response(chat_id, ENROLL_SUCCESS.format(enroller_summary(enroller)))
    asyncio.run(send_message(response))

def initialise_job(lesson_url, user, password, organisation, chat_id):
    enroller = get_enroller(lesson_url, user, decrypt(password, config["app"]["secret"]), organisation)
    logger.info(f"{user} - Job: {enroller_summary(enroller)} - Exec: {enroller.enrollment_start} ")
    if enroller.enrollment_start < datetime.today():
        logger.info(f"{user} - Enrollment already started.")
        scheduler.add_job(enroll, args=(enroller, chat_id))
    else:
        scheduler.add_job(enroll, args=(enroller, chat_id), trigger='date', run_date=enroller.enrollment_start)
    return enroller_summary(enroller)

def user_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    user = get_user_from_chat_id(chat.id)
    if chat.type == "private" and user is not None:
        return user
    else:
        return None

def authorized(function):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if user_authorized(update, context) is not None:
            return await function(update, context)
        else:
            logger.warn(f"Unauthorized access: {context.user_data}")
            return
    return wrapper

def get_jobs(chat_id):
    jobs = scheduler.get_jobs()
    return [job for job in jobs if job.args[1] == chat_id]

#################


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if user_authorized(update, context):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Access token:")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome back!")

@authorized
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=HELP)

@authorized
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(update.effective_chat.id)
    if len(jobs) == 0:
        msg = NO_JOBS
    else:
        msg = "Jobs:\n"
        for i, job in enumerate(jobs):
            msg += f"{i+1}. {job_summary(job)}\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    return DELETE

@authorized
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        job_id = int(update.message.text.split(" ")[1])
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=DELETE_NO_NUMBER)
        return ConversationHandler.END
    jobs = scheduler.get_jobs()
    if len(jobs) == 0:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=NO_JOBS)
        return ConversationHandler.END
    elif job_id > len(jobs):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=DELETE_NUMBER_NOTFOUND)
        return ConversationHandler.END
    else:
        job = jobs[job_id-1]
        context.user_data["job"] = job.id
        reply_keyboard = [["Yes", "No"]]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=DELETE_VALIDATE.format(job_summary(job)), reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, input_field_placeholder="Yes or No?"))
        return CONFIRM

@authorized
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Yes":
        job_id = context.user_data["job"]
        scheduler.remove_job(job_id)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=DELETE_CONFIRMATION)
    return ConversationHandler.END

@authorized
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

@authorized
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=UNKNOWN_COMMAND)

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    db_user = user_authorized(update, context)
    if db_user is None:
        db_user = get_user_from_token(update.message.text)
        if db_user and not db_user.linked:
                logger.info(f"User {db_user.username} authorized.")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=WELCOME.format(db_user.username))
                verified = verify_login(db_user.asvz_username, decrypt(db_user.asvz_password, config["app"]["secret"]), db_user.asvz_organisation)
                if verified == 0:
                    reset_token(db_user)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=INVALID_CREDENTIALS)
                elif verified == 1:
                    set_user_data(db_user, user, chat)
                    # update user
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=VALID_CREDENTIALS)
        return
    else:
        logger.info(f"{update.effective_user.username} - Job received: {update.message.text}")
        if db_user.verified == -1:
            logger.info(f"{update.effective_user.username} - Job invalid.")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=NOT_YET_VALIDATED)    
        elif LESSON_BASE_URL+"/tn/lessons/" in update.message.text:
            # get full url from message with regex(starts with LESSON_BASE_URL) 
            url = re.search(f"https:\/\/schalter\.asvz\.ch\/tn\/lessons/\d*", update.message.text).group(0)
            if url:
                job_summary = initialise_job(url, db_user.asvz_username, db_user.asvz_password, db_user.asvz_organisation, chat.id)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=JOB_SUBMITTED.format(job_summary))
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=NO_URL_FOUND)
   

# Message Dispatcher
async def send_message(response):
    bot = Bot(token=config["bot"]["token"])
    await bot.send_message(chat_id=response.chat_id, text=response.message)

class Response:
    def __init__(self, chat_id, message):
        self.chat_id = chat_id
        self.message = message

def message_dispatcher():
    while True:
        try:
            # get messages from queue
            while not response_queue.empty():
                response = response_queue.get()
                asyncio.run(send_message(response))
        except Exception as e:
            logger.error(e)
        time.sleep(1)


if __name__ == '__main__':
    scheduler.start()
    application = ApplicationBuilder().token(config["bot"]["token"]).build()

    # Message dispatcher
    Thread(target=message_dispatcher).start()
    
    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help))
    application.add_handler(CommandHandler('jobs', jobs))
    delete_handler = ConversationHandler(
        entry_points=[CommandHandler("delete", delete)],
        states={
            CONFIRM: [MessageHandler(filters.Regex("^(Yes|No)$"), confirm)]
        },
        fallbacks = []
    )
    application.add_handler(delete_handler)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), answer))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.run_polling()


