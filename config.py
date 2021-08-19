import datetime
import os
import platform
from importlib.metadata import version

import aiofiles


class Config:
    __client_id = None
    __client_secret = None
    __username = None
    __password = None
    __user_agent = None
    __max_cache_age = None
    __filter_lists = None
    __ruleset_update_interval = None
    __monitored_subreddits = None

    @staticmethod
    def get_client_id():
        if Config.__client_id is None:
            Config.__client_id = os.environ.get("REDDIT_CLIENT_ID")

        return Config.__client_id

    @staticmethod
    def get_client_secret():
        if Config.__client_secret is None:
            Config.__client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

        return Config.__client_secret

    @staticmethod
    def get_username():
        if Config.__username is None:
            Config.__username = os.environ.get("REDDIT_USERNAME")

        return Config.__username

    @staticmethod
    def get_password():
        if Config.__password is None:
            Config.__password = os.environ.get("REDDIT_PASSWORD")

        return Config.__password

    @staticmethod
    def get_user_agent_string():
        if Config.__user_agent is None:
            Config.__user_agent = f"{platform.system()}:LinkCheckBot:{version('linkcheckbot')} (by /u/VoxUmbra)"

        return Config.__user_agent

    @staticmethod
    def get_max_cache_age():
        if Config.__max_cache_age is None:
            Config.__max_cache_age = datetime.timedelta(minutes=int(os.environ.get("MAX_CACHE_AGE")))

        return Config.__max_cache_age

    @staticmethod
    async def get_filter_lists():
        if Config.__filter_lists is None:
            async with aiofiles.open("data/filter_lists.txt", "r") as file:
                results = await file.read()
                Config.__filter_lists = results.splitlines()

        return Config.__filter_lists

    @staticmethod
    def get_ruleset_update_interval():
        if Config.__ruleset_update_interval is None:
            Config.__ruleset_update_interval = datetime.timedelta(minutes=int(os.environ.get("RULESET_UPDATE_INTERVAL")))

        return Config.__ruleset_update_interval

    @staticmethod
    async def get_monitored_subreddits():
        if Config.__monitored_subreddits is None:
            async with aiofiles.open("data/subreddits.txt", "r") as file:
                results = await file.read()
                Config.__monitored_subreddits = "+".join(results.splitlines())

        return Config.__monitored_subreddits
