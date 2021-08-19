import asyncio
import concurrent.futures
import datetime
import logging
from typing import List, Optional

import playwright.async_api
from memoize.configuration import DefaultInMemoryCacheConfiguration, MutableCacheConfiguration
from memoize.entrybuilder import ProvidedLifeSpanCacheEntryBuilder
from memoize.eviction import LeastRecentlyUpdatedEvictionStrategy
from memoize.wrapper import memoize
from playwright.async_api import Browser
from pydantic import BaseModel

from config import Config
from service.filtering import Action, RuleSet
from service.models import RequestInfo


class RequestReport(BaseModel):
    requested_url: str
    ruleset_title: str
    ruleset_homepage: str
    active_rules: List[str]


class Report(BaseModel):
    title: str
    url: str
    results: List[RequestReport]


class LinkChecker:
    def __init__(self,
                 process_requests_queue: asyncio.Queue,
                 reply_comments_queue: asyncio.Queue,
                 rulesets_updated_queue: asyncio.Queue,
                 executor: concurrent.futures.ThreadPoolExecutor):
        self.__process_requests_queue = process_requests_queue
        self.__reply_comments_queue = reply_comments_queue
        self.__rulesets_updated_queue = rulesets_updated_queue
        self.__executor = executor

        self.__rulesets: Optional[List[RuleSet]] = None

    async def __capture_page_requests(self, browser: Browser, url: str, queue: asyncio.Queue):
        logging.info(f"Capturing requests for {url}")

        page = await browser.new_page()
        client = await page.context.new_cdp_session(page)

        await client.send("Debugger.enable")
        await client.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 32})

        await client.send("Network.enable")

        def handle_pre_request(args):
            request_info = RequestInfo.parse_obj(args)
            queue.put_nowait(request_info)

        client.on("Network.requestWillBeSent", handle_pre_request)

        await page.goto(url)
        title = await page.title()
        url = page.url

        await page.close()

        logging.info(f"Requests captured for {url}")
        return title, url

    def __create_report(self, title: str, url: str, queue: asyncio.Queue):
        logging.info(f"Creating report for {title} ({url})...")

        report = Report(title=title, url=url, results=[])

        while True:
            try:
                request_info = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            logging.debug(f"Analysing request to {request_info.request.url}...")

            for ruleset in self.__rulesets:
                action, rules = ruleset.evaluate(request_info)

                if action == Action.DENY:
                    result_report = RequestReport(
                        requested_url=request_info.request.url,
                        ruleset_title=ruleset.title,
                        ruleset_homepage=ruleset.homepage,
                        active_rules=[rule.rule_str for rule in rules]
                    )
                    report.results.append(result_report)
                    break

        return report

    @memoize(configuration=MutableCacheConfiguration
             .initialized_with(DefaultInMemoryCacheConfiguration())
             .set_entry_builder(ProvidedLifeSpanCacheEntryBuilder(expire_after=Config.get_max_cache_age()))
             .set_eviction_strategy(LeastRecentlyUpdatedEvictionStrategy(capacity=256))
             .set_method_timeout(datetime.timedelta.max))
    async def __check_link(self, browser: Browser, url: str):
        queue = asyncio.Queue()

        title, final_page_url = await self.__capture_page_requests(browser, url, queue)
        report = await asyncio.get_event_loop().run_in_executor(
            self.__executor,
            lambda: self.__create_report(title, final_page_url, queue)
        )

        return report

    async def __process_message(self, browser: Browser, message: dict):
        result = {
            "comment_id": message["comment_id"],
            "report": {},
            "modifier": message["modifier"],
        }

        for url in message["check_urls"]:
            report = await self.__check_link(browser, url)
            result["report"][url] = report

        return result

    async def __process_requests(self):
        logging.info("Waiting for rulesets to be available...")
        while self.__rulesets is None:
            await asyncio.sleep(1)

        logging.info("Rulesets retrieved!")
        async with playwright.async_api.async_playwright() as p:
            logging.info("Launching Chromium...")
            browser = await p.chromium.launch()

            logging.info("Ready to process requests.")
            while True:
                message = await self.__process_requests_queue.get()
                result = await self.__process_message(browser, message)

                await self.__reply_comments_queue.put(result)

    async def __listen_for_ruleset_updates(self):
        while True:
            self.__rulesets = await self.__rulesets_updated_queue.get()

    async def start(self):
        await asyncio.gather(
           self.__listen_for_ruleset_updates(),
            self.__process_requests()
        )
