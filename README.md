# ASVZ Enroller

The asvz enroller is a Telegram-based ASVZ bot that signs you up for your ASVZ sports lessons as soon as registration opens. You send it links to lessons via Telegram and it will communicate with you as soon as you are enrolled. If a class is already full, it will periodically check and try to get you a spot. 

The application automatically schedules enrolment jobs (done with selenium) and can be deployed easily using Docker on any host.

The application consists of two main parts. First, each user goes to a web interface that allows them to save their ASVZ credentials and link their Telegram account. Once this is done, interaction is only via Telegram. The web interface guides the user through all the details. 

# Installation

To run this application you need to have [Docker](https://www.docker.com) installed. Further you need to have a [telegram bot API key](https://core.telegram.org/bots). 

Clone this repository and create a `config.yaml` file in the root and fill it with the required information. See `config_example.yaml` for details on how the file should be structured. See below for details on how to add users.

To start the containers simply run:
```
docker-compose up --build -d
```
By default this will expose the web interface on port 5090 on localhost. Modify the `docker-compose.yaml` file to change the port binding.

# Creating users

Only the host can add new users. Use the `admin.py` script to create/reset/delete any users. 

To create a user run:
```
python admin.py -u USERNAME
```
The script will automatically create a password for this user. The user can't change it. These login credentials are for the web interface that will allow him to store his ASVZ login credentials and connect to his telegram account. 

If you want to reset a user run:
```
python admin.py -u USERNAME -r
```
This will delete any associated data and create a new password.

To delete a user run:
```
python admin.py -u USERNAME -d
```

# Broadcasting

It might be of interest to broadcast messages to all users. This is mainly intended to announce downtime or similar things. 
```
python broadcast.py -m "A test message"
```
This will send a message from the bot to all users that have connected a telegram account.

# Data privacy

You should be aware that the application must store the ASVZ credentials of all users locally. So that the passwords are not completely unencrypted in the database, they are encrypted with a symmetric encryption. But the key is defined in the config and lies on the host machine as well. Primarily intended such that the host does not accidently reads passwords when analysing the database in case of bugs.