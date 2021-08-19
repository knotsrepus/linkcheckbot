import asyncio
import logging

import aiohttp

from config import Config
from service.filtering import RuleSetParser


class RuleSetUpdater:
    def __init__(self, config: Config, rulesets_updated_queue: asyncio.Queue):
        self.__config = config
        self.__rulesets_updated_queue = rulesets_updated_queue

    async def __get_rulesets(self):
        rulesets = []

        timeout = aiohttp.ClientTimeout(total=30, connect=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for filter_list in await self.__config.get_filter_lists():
                logging.info(f"Parsing filter list from: {filter_list}")
                async with session.get(filter_list) as response:
                    text = await response.text()

                    ruleset = RuleSetParser.parse(text)
                    if ruleset.title is None:
                        ruleset.title = ruleset.homepage

                    rulesets.append(ruleset)

        return rulesets

    async def __update_rulesets(self):
        logging.info("Updating rulesets...")

        rulesets = await self.__get_rulesets()
        logging.info("\n".join(ruleset.title for ruleset in rulesets))

        return rulesets

    async def start(self):
        while True:
            new_rulesets = await self.__update_rulesets()
            await self.__rulesets_updated_queue.put(new_rulesets)
            logging.info("Rulesets updated.")
            await asyncio.sleep(self.__config.get_ruleset_update_interval().total_seconds())
