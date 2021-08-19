import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from config import Config
from reddit.bot import RedditBot
from service.link_checker import LinkChecker
from service.ruleset_updater import RuleSetUpdater


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(module)s:%(funcName)s:%(lineno)d] %(levelname)s: %(message)s"
    )

    config = Config()

    process_requests_queue = asyncio.Queue()
    reply_comments_queue = asyncio.Queue()
    rulesets_updated_queue = asyncio.Queue()

    reddit_bot = RedditBot(config, process_requests_queue, reply_comments_queue)

    ruleset_updater = RuleSetUpdater(config, rulesets_updated_queue)

    with ThreadPoolExecutor() as executor:
        link_checker = LinkChecker(
            process_requests_queue,
            reply_comments_queue,
            rulesets_updated_queue,
            executor
        )

        await asyncio.gather(
            reddit_bot.start(),
            ruleset_updater.start(),
            link_checker.start(),
        )


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
