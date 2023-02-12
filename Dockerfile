FROM python:3.8-slim-buster

ENV TZ="CET"

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY src/ .
COPY config.yaml .
CMD [ "sh", "start.sh"]