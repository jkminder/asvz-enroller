FROM python:3.8-slim-buster

ENV TZ="CET"

# install google chrome
RUN apt-get update
RUN apt-get install -y wget 
RUN apt-get install -y gnupg2
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
RUN apt-get -y update
RUN apt-get install -y google-chrome-stable

# install chromedriver
RUN apt-get install -y unzip
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/94.0.4606.41/chromedriver_linux64.zip
RUN unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

# set display port to avoid crash
ENV DISPLAY=:99

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY src/ .
CMD [ "sh", "start.sh"]
#CMD [ "python3", "bot.py"]