#!/usr/bin/python3
# coding=UTF-8

import argparse
import getpass
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import re

"""
This is heavily adapted from "https://github.com/fbuetler/asvz-bot"
"""

TIMEFORMAT = "%H:%M"

LESSON_BASE_URL = "https://schalter.asvz.ch"

SPORTFAHRPLAN_BASE_URL = "https://asvz.ch/426-sportfahrplan"

CREDENTIALS_FILENAME = ".asvz-bot.json"
CREDENTIALS_ORG = "organisation"
CREDENTIALS_UNAME = "username"
CREDENTIALS_PW = "password"

# organisation name as displayed by SwitchAAI
ORGANISATIONS = {
    "ETH": "ETH Zürich",
    "UZH": "Universität Zürich",
    "ZHAW": "ZHAW - Zürcher Hochschule für Angewandte Wissenschaften",
    "PHZH": "PH Zürich - Pädagogische Hochschule Zürich",
    "ASVZ": "ASVZ",
}

WEEKDAYS = {
    "Mo": "Monday",
    "Tu": "Tuesday",
    "We": "Wednesday",
    "Th": "Thursday",
    "Fr": "Friday",
    "Sa": "Saturday",
    "Su": "Sunday",
}

LEVELS = {"Alle": 2104, "Mittlere": 880, "Fortgeschrittene": 726}

FACILITIES = {
    "Sport Center Polyterrasse": 45594,
    "Sport Center Irchel": 45577,
    "Sport Center Hönggerberg": 45598,
    "Sport Center Fluntern": 45575,
    "Sport Center Winterthur": 45610,
    "Rämistrasse 80": 45574,
    "PH Zürich": 45583,
    "Wädenswil Kraft-/Cardio-Center": 45613,
    "Online": 294542,
}

ISSUES_URL = "https://github.com/fbuetler/asvz-bot/issues"
NO_SUCH_ELEMENT_ERR_MSG = f"Element on website not found! This may happen when the website was updated recently. Please report this incident to: {ISSUES_URL}"

class AsvzBotException(Exception):
    pass

class LessonStarted(Exception):
    pass

class LoginFailed(Exception):
    pass


class CredentialsManager:
    def __init__(self, org, uname, password, save_credentials):
        self.credentials = {
                CREDENTIALS_ORG: ORGANISATIONS[org],
                CREDENTIALS_UNAME: uname,
                CREDENTIALS_PW: password,
        }

    def get(self):
        return self.credentials


class AsvzEnroller:
    @staticmethod
    def get_driver():
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("prefs", {"intl.accept_languages": "de"})
        driver = webdriver.Remote(
            command_executor='http://selenium:4444/wd/hub',
            options=options
        )
        return driver

    @staticmethod
    def wait_until(enrollment_start):
        current_time = datetime.today()

        logger.info(
            "\n\tcurrent time: {}\n\tenrollment time: {}".format(
                current_time.strftime("%H:%M:%S"), enrollment_start.strftime("%H:%M:%S")
            )
        )

        login_before_enrollment_seconds = 1 * 59
        if (enrollment_start - current_time).seconds > login_before_enrollment_seconds:
            sleep_time = (
                enrollment_start - current_time
            ).seconds - login_before_enrollment_seconds
            logger.info(
                "Sleep for {} seconds until {}".format(
                    sleep_time,
                    (current_time + timedelta(seconds=sleep_time)).strftime("%H:%M:%S"),
                )
            )
            time.sleep(sleep_time)

    def __init__(self, lesson_url, creds):
        self.lesson_url = lesson_url
        self.creds = creds

        logger.info(
            "Summary:\n\tOrganisation: {}\n\tUsername: {}\n\tPassword: {}\n\tLesson: {}".format(
                self.creds[CREDENTIALS_ORG],
                self.creds[CREDENTIALS_UNAME],
                "*" * len(self.creds[CREDENTIALS_PW]),
                self.lesson_url,
            )
        )


    @staticmethod
    def check_login(credentials):
        logger.info("Checking login credentials")
        try:
            driver = AsvzEnroller.get_driver()
            driver.get(LESSON_BASE_URL)
            driver.implicitly_wait(3)
            logger.info("Login to '{}'".format(credentials[CREDENTIALS_ORG]))
            if credentials[CREDENTIALS_ORG] == "ASVZ":
                driver.find_element(By.XPATH, "//input[@id='AsvzId']").send_keys(
                    credentials[CREDENTIALS_UNAME]
                )
                driver.find_element(By.XPATH, "//input[@id='Password']").send_keys(
                    credentials[CREDENTIALS_PW]
                )

                button = (
                    WebDriverWait(driver, 20)
                    .until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                "//button[@type='submit' and text()='Login']",
                            )
                        )
                    )
                    .click()
                )
            else:
                WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[@class='btn btn-warning btn-block' and @title='SwitchAai Account Login']",
                        )
                    )
                ).click()

                organization = driver.find_element(
                    By.XPATH, "//input[@id='userIdPSelection_iddtext']"
                )
                organization.send_keys("{}a".format(Keys.CONTROL))
                organization.send_keys(credentials[CREDENTIALS_ORG])
                organization.send_keys(Keys.ENTER)

                # apparently all organisations have the same xpath
                driver.find_element(By.XPATH, "//input[@id='username']").send_keys(
                    credentials[CREDENTIALS_UNAME]
                )
                driver.find_element(By.XPATH, "//input[@id='password']").send_keys(
                    credentials[CREDENTIALS_PW]
                )
                driver.find_element(By.XPATH, "//button[@type='submit']").click()

            logger.info("Submitted login credentials")
            time.sleep(3)  # wait until redirect is completed

            if not driver.current_url.startswith(LESSON_BASE_URL):
                logger.warning(
                    "Authentication might have failed. Current URL is '{}'".format(
                        driver.current_url
                    )
                )
                return False
            else:
                logger.info("Valid login credentials")
                return True
        except NoSuchElementException as e:
            logger.error(NO_SUCH_ELEMENT_ERR_MSG)
            raise e
        finally:
            if driver is not None:
                driver.quit()

    def enroll(self):
        logger.info("Checking login credentials")
        try:
            driver = AsvzEnroller.get_driver()
            driver.get(self.lesson_url)
            driver.implicitly_wait(3)
            self.__organisation_login(driver)
        except NoSuchElementException as e:
            logger.error(NO_SUCH_ELEMENT_ERR_MSG)
            raise e
        finally:
            if driver is not None:
                driver.quit()

        if datetime.today() < self.enrollment_start:
            AsvzEnroller.wait_until(self.enrollment_start)

        try:
            driver = AsvzEnroller.get_driver()
            driver.get(self.lesson_url)
            driver.implicitly_wait(3)

            logger.info("Starting enrollment")

            enrolled = False
            while not enrolled:
                if self.enrollment_start < datetime.today():
                    logger.info(
                        "Enrollment is already open. Checking for available places."
                    )
                    self.__wait_for_free_places(driver)

                logger.info("Lesson has free places")

                self.__organisation_login(driver)

                try:
                    logger.info("Waiting for enrollment")
                    WebDriverWait(driver, 5 * 60).until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                "//button[@id='btnRegister' and @class='btn-primary btn enrollmentPlacePadding']",
                            )
                        )
                    ).click()
                    time.sleep(5)
                except TimeoutException as e:
                    logger.info(
                        "Place was already taken in the meantime. Rechecking for available places."
                    )
                    continue
                except Exception as e:
                    logger.error(e)
                    raise e
                logger.info("Successfully enrolled. Train hard and have fun!")
                return True

        except NoSuchElementException as e:
            logger.error(NO_SUCH_ELEMENT_ERR_MSG)
            raise e
        finally:
            if driver is not None:
                driver.quit()
    @staticmethod
    def __get_enrollment_and_start_time(driver):
        try:
            try:
                driver.find_element(By.TAG_NAME, "app-page-not-found")
            except NoSuchElementException:
                pass
            else:
                logging.error("Lesson not found! Please check your lesson details")
                raise Exception("Lesson not found")

            enrollment_start = AsvzEnroller.__get_enrollment_time(driver)
            lesson_start = AsvzEnroller.__get_lesson_time(driver)
        except NoSuchElementException as e:
            logging.error(NO_SUCH_ELEMENT_ERR_MSG)
            raise e

        return (enrollment_start, lesson_start)

    @staticmethod
    def __get_enrollment_time(driver):
        # requires the user to be logged in, as the intro text is only available then
        try:
            introduction_text = driver.find_element(
                By.XPATH, "//span[contains(., 'Online-Einschreibungen')]"
            ).get_attribute("innerHTML")
        except NoSuchElementException as e:
            logging.info(
                "No enrollment time found. Assuming enrollment is already open."
            )
            # setting enrollment to some date in the past
            return datetime.today() - timedelta(days=1)

        # assumes enrollment start is the first date
        enrollment_start_raw = re.findall(
            "\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2}", introduction_text
        )[0]

        # enrollment_start_raw is like '17.01.2023 20:00'
        enrollment_start_raw = enrollment_start_raw.strip()
        try:
            enrollment_start = datetime.strptime(enrollment_start_raw, "%d.%m.%Y %H:%M")
        except ValueError as e:
            logging.error(e)
            raise AsvzBotException(
                "Failed to parse enrollment start time: '{}'".format(
                    enrollment_start_raw
                )
            )
        return enrollment_start

    @staticmethod
    def __get_lesson_time(driver):
        lesson_interval_raw = driver.find_element(
            By.XPATH, "//dl[contains(., 'Datum/Zeit')]/dd"
        )
        # lesson_interval_raw is like 'Mo, 10.05.2021 06:55 - 08:05'
        lesson_start_raw = (
            lesson_interval_raw.get_attribute("innerHTML")
            .split("-")[0]
            .split(",")[1]
            .strip()
        )
        try:
            lesson_start = datetime.strptime(lesson_start_raw, "%d.%m.%Y %H:%M")
        except ValueError as e:
            logging.error(e)
            raise AsvzBotException(
                "Failed to parse lesson start time: '{}'".format(lesson_start_raw)
            )
        return lesson_start

    def setup(self):
        driver = None
        try:
            driver = AsvzEnroller.get_driver()
            driver.get(self.lesson_url)
            driver.implicitly_wait(3)
            self.__organisation_login(driver)
            (
                self.enrollment_start,
                self.lesson_start,
            ) = AsvzEnroller.__get_enrollment_and_start_time(driver)
            self.enrollment_start.replace(tzinfo=pytz.timezone("CET"))
            self.lesson_start.replace(tzinfo=pytz.timezone("CET"))

            self.lesson_title = driver.find_element(By.XPATH, "//h1").text
            lesson_location_raw = driver.find_element(
               By.XPATH, "//dl[contains(., 'Anlage')]/dd"
            )
            self.lesson_location = lesson_location_raw.text
            logger.info("Lesson title: '{}' at '{}'".format(self.lesson_title, self.lesson_location))
        except NoSuchElementException as e:
            logging.error(NO_SUCH_ELEMENT_ERR_MSG)
            raise e
        finally:
            if driver is not None:
                driver.quit()

    def __organisation_login(self, driver, retry=True):
        logger.debug("Start login process")
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[@class='btn btn-default' and @title='Login']",
                )
            )
        ).click()

        logger.info("Login to '{}'".format(self.creds[CREDENTIALS_ORG]))
        if self.creds[CREDENTIALS_ORG] == "ASVZ":
            driver.find_element(By.XPATH, "//input[@id='AsvzId']").send_keys(
                self.creds[CREDENTIALS_UNAME]
            )
            driver.find_element(By.XPATH, "//input[@id='Password']").send_keys(
                self.creds[CREDENTIALS_PW]
            )

            button = (
                WebDriverWait(driver, 20)
                .until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[@type='submit' and text()='Login']",
                        )
                    )
                )
                .click()
            )
        else:
            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[@class='btn btn-warning btn-block' and @title='SwitchAai Account Login']",
                    )
                )
            ).click()

            organization = driver.find_element(
                By.XPATH, "//input[@id='userIdPSelection_iddtext']"
            )
            organization.send_keys("{}a".format(Keys.CONTROL))
            organization.send_keys(self.creds[CREDENTIALS_ORG])
            organization.send_keys(Keys.ENTER)

            # apparently all organisations have the same xpath
            driver.find_element(By.XPATH, "//input[@id='username']").send_keys(
                self.creds[CREDENTIALS_UNAME]
            )
            driver.find_element(By.XPATH, "//input[@id='password']").send_keys(
                self.creds[CREDENTIALS_PW]
            )
            driver.find_element(By.XPATH, "//button[@type='submit']").click()

        logger.info("Submitted login credentials")
        time.sleep(3)  # wait until redirect is completed

        if not driver.current_url.startswith(LESSON_BASE_URL):
            logger.warning(
                "Authentication might have failed. Current URL is '{}'".format(
                    driver.current_url
                )
            )
            if retry:
                logger.warning("Sleeping for 5 seconds and retrying...")
                self.__organisation_login(driver, retry=False)
                return True
            raise LoginFailed("Login failed")
        else:
            logger.info("Valid login credentials")
            return True

    def __wait_for_free_places(self, driver):
        while True:
            try:
                driver.find_element(
                    By.XPATH,
                    "//div[@class='alert alert-warning'][contains(., 'ausgebucht')]",
                )
            except NoSuchElementException:
                # has free places
                return

            if datetime.today() > self.lesson_start:
                raise LessonStarted(
                    "Stopping enrollment because lesson has started."
                )

            retry_interval_sec = 1 * 30
            logger.info(
                "Lesson is booked out. Rechecking in {} secs..".format(
                    retry_interval_sec
                )
            )
            time.sleep(retry_interval_sec)
            driver.refresh()

def validate_start_time(start_time):
    try:
        return datetime.strptime(start_time, TIMEFORMAT)
    except ValueError:
        msg = "Invalid start time specified. Supported format is {}".format(TIMEFORMAT)
        raise argparse.ArgumentTypeError(msg)


def verify_login(username, password, organisation):
    creds = CredentialsManager(organisation, username, password, False)
    return AsvzEnroller.check_login(creds.get())

def get_enroller(lesson_url, username, password, organisation):
    creds = CredentialsManager(organisation, username, password, False)
    enroller = AsvzEnroller(lesson_url, creds.get())
    enroller.setup()
    return enroller
