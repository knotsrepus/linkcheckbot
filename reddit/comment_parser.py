import re
from typing import Optional

from pydantic import BaseModel


class BotAction(BaseModel):
    action: str
    modifier: Optional[str]
    target: Optional[str]


class CommentParser:
    __pattern__ = re.compile(r"!linkcheck(?:|(?:\s+(?:\S+?))+)!")

    @staticmethod
    def parse_comment(comment_body):
        match = CommentParser.__pattern__.search(comment_body)

        if match is None:
            return BotAction(action="ignore")

        command = match.group(0)[1:-1]

        if command == "linkcheck":
            # Default
            return BotAction(action="check", modifier="details", target="parent")

        params = command.split()[1:]

        if params[0] == "help":
            return BotAction(action="help")

        action = "check"
        target = "parent"
        if params[0] == "this":
            target = params[1]
            params = params[2:]

        if len(params) == 0:
            return BotAction(action=action, modifier="details", target=target)

        modifier = params[0]
        if modifier in ["details", "summary"]:
            return BotAction(action=action, modifier=modifier, target=target)

        return BotAction(action="ignore")
