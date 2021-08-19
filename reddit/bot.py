import asyncio
import logging

import asyncpraw
from asyncpraw.exceptions import ClientException

from config import Config
from reddit.comment_formatter import CommentFormatter
from reddit.comment_parser import CommentParser
from reddit.link_finder import LinkFinder


class RedditBot:
    def __init__(self, config: Config, process_requests_queue: asyncio.Queue, reply_comments_queue: asyncio.Queue):
        self.__config = config
        self.__process_requests_queue = process_requests_queue
        self.__reply_comments_queue = reply_comments_queue

        self.__comment_formatter = CommentFormatter()

        self.__reddit = asyncpraw.Reddit(
            user_agent=self.__config.get_user_agent_string(),
            client_id=self.__config.get_client_id(),
            client_secret=self.__config.get_client_secret(),
            username=self.__config.get_username(),
            password=self.__config.get_password(),
        )

    async def __get_parent_links(self, comment: asyncpraw.reddit.Comment):
        parent_type, parent_id = comment.parent_id.split("_")
        if parent_type == "t1":
            # t1 = comment
            parent = await self.__reddit.comment(parent_id)
            return LinkFinder.find_links(parent.body)
        elif parent_type == "t3":
            # t3 = submission
            parent = await self.__reddit.submission(parent_id)
            if parent.is_self:
                return LinkFinder.find_links(parent.selftext)
            else:
                return [parent.url]
        else:
            # Other types not supported
            logging.info(f"Invalid parent ID: {comment.parent_id}")
            return None

    async def __search_comments_for_requests(self):
        subreddit = await self.__reddit.subreddit(await self.__config.get_monitored_subreddits())
        me = await self.__reddit.user.me()

        async for comment in subreddit.stream.comments():
            try:
                await comment.refresh()
            except ClientException as e:
                logging.error("Fetching the comment failed.", exc_info=e)
                continue

            if comment.author == me:
                # Make sure it doesn't reply to itself
                logging.info(f"Comment {comment.id} ignored as I wrote it.")
                continue

            # Make sure it doesn't reply to a comment it's already replied to
            already_replied = False
            for reply in comment.replies:
                await reply.refresh()
                if reply.author == me:
                    logging.info(f"Comment {comment.id} ignored as I replied to it already ({reply.id}).")
                    already_replied = True
                    break
            if already_replied:
                continue

            action = CommentParser.parse_comment(comment.body)
            logging.info(f"{comment.id} -> {action}")

            if action.action == "help":
                await comment.reply(self.__comment_formatter.get_help_text())
                continue

            if action.action == "check":
                if action.target == "parent":
                    urls = await self.__get_parent_links(comment)
                    if urls is None:
                        continue
                else:
                    urls = [action.target]

                message = {
                    "comment_id": comment.id,
                    "check_urls": urls,
                    "modifier": action.modifier,
                }
                await self.__process_requests_queue.put(message)

        logging.error("!!! Should never get to here !!!")

    async def __reply_to_comments(self):
        while True:
            message = await self.__reply_comments_queue.get()

            report = message["report"]
            reply_format = message["modifier"]

            logging.info(f"Replying to {message['comment_id']}...")

            comment = await self.__reddit.comment(message["comment_id"])

            reply = self.__comment_formatter.get_report_text(report, reply_format)
            logging.info(reply)
            await comment.reply(reply)

    async def start(self):
        while True:
            try:
                coroutine = asyncio.gather(
                    self.__search_comments_for_requests(),
                    self.__reply_to_comments()
                )
                await coroutine
            except asyncpraw.reddit.RedditAPIException as e:
                logging.error("PRAW raised an exception", exc_info=e)
                coroutine.cancel()
                pass
