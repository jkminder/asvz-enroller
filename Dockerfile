FROM python:3.8-slim-buster

ENV TZ="CET"

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY src/ .
CMD [ "sh", "start.sh"]