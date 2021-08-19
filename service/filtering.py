from __future__ import annotations

import logging
import re
import typing
from enum import Enum, auto
from io import TextIOWrapper, StringIO
from typing import List, Optional, Union

import aiofiles
from pydantic import BaseModel, Field, PrivateAttr

from service.models import RequestInfo


class Action(Enum):
    """Represents the action to take for a service."""

    ALLOW = auto()
    """Does not filter a service."""

    DENY = auto()
    """Filters a service."""

    NOOP = auto()
    """
    No particular action should be taken.
    
    If used, this indicates that the final decision will be determined by other rules.
    """


class MatchResult(Enum):
    """Represents the outcome of rule matching."""

    MATCH = auto()
    """The rule matches the service."""

    NO_MATCH = auto()
    """The rule does not match the given service."""

    OVERRIDE = auto()
    """The rule matches the given service, and should take precedence over other rules."""

    IGNORE = auto()
    """The rule should not be considered."""

    @staticmethod
    def from_bool(value: bool):
        """
        Converts a :ref:`bool` value into a :ref:`MatchResult`.
        :param value: The value to convert.
        :return: MATCH if value is True, otherwise NO_MATCH.
        """
        return MatchResult.MATCH if value else MatchResult.NO_MATCH

    @staticmethod
    def invert(value):
        if value in [MatchResult.MATCH, MatchResult.OVERRIDE]:
            return MatchResult.NO_MATCH

        if value == MatchResult.NO_MATCH:
            return MatchResult.MATCH

        return MatchResult.IGNORE


class Modifier(BaseModel):
    """
    Modifies the behaviour of a filter rule.

    Supported modifier types:
        - important
        - all
        - document
        - css
        - script
        - image
        - media
        - websocket
        - xhr
        - domain
        - 1p
        - 3p
    """

    name: str
    value: Optional[str]
    __included_domain_patterns: List[typing.Pattern] = PrivateAttr(default=None)
    __excluded_domain_patterns: List[typing.Pattern] = PrivateAttr(default=None)

    def matches(self, request_info: RequestInfo):
        """
        Determines whether this modifier matches the current service.

        The matching behaviour is as follows:
            - important: Matches everything and takes precedence
            - all: Matches everything
            - document, css, script, image, media, websocket, xhr:
              Matches a service of the correct type, e.g. a css modifier will
              match if a stylesheet is being requested.
            - domain: Matches if a service has originated from the specified domain
              pattern(s).
              For example, the modifier "||foo.com^$domain=example.com" would apply
              the rule if a service to foo.com originated from a page at example.com.
              Multiple domains can be specified by using a pipe (|) character as a
              separator.
              Domains can be excluded from a filter using a tilde (~) character.
            - ~thirdparty, 1p: Matches if a service is to the same site as the
              originating page (i.e. it is a first-party service).
            - thirdparty, 3p: Matches if a service is to a different site as the
              originating page (i.e. it is a third-party service).
        """
        modifier_aliases = {
            "frame": "subdocument",
            "ghide": "generichide",
            "~third-party": "1p",
            "third-party": "3p",
            "stylesheet": "css",
            "xmlhttprequest": "xhr",
        }

        name = modifier_aliases.get(self.name, self.name)
        invert_modifier = False
        if name.startswith("~"):
            invert_modifier = True
            name = name[1:]
            # Check again for aliases
            name = modifier_aliases.get(name, name)

        name = name.replace("-", "")
        func = getattr(self, f"_{type(self).__name__}__matches_{name}")

        result = func(request_info, self.value)
        if invert_modifier:
            return MatchResult.invert(result)

        return result

    @staticmethod
    def __matches_important(request_info: RequestInfo, value: str):
        return MatchResult.OVERRIDE

    @staticmethod
    def __matches_all(request_info: RequestInfo, value: str):
        return MatchResult.MATCH

    @staticmethod
    def __matches_document(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "Document")

    @staticmethod
    def __matches_css(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "Stylesheet")

    @staticmethod
    def __matches_script(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "Script")

    @staticmethod
    def __matches_image(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "Image")

    @staticmethod
    def __matches_media(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "Media")

    @staticmethod
    def __matches_websocket(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "WebSocket")

    @staticmethod
    def __matches_xhr(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "XHR")

    @staticmethod
    def __matches_other(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.type == "Other")

    def __matches_domain(self, request_info: RequestInfo, value: str):
        if self.__included_domain_patterns is None or self.__excluded_domain_patterns is None:
            if value.endswith("|"):
                # Trim pipe from end to avoid accidentally matching all domains
                value = value[:-1]

            domain_pattern_list = value.split("|")
            include_domain_patterns = []
            exclude_domain_paterns = []

            for domain_pattern in domain_pattern_list:
                domain_pattern = domain_pattern.replace(".", r"\.")
                domain_pattern = domain_pattern.replace("*", r".*")

                if domain_pattern.startswith("~"):
                    # Tilde (~) character denotes exceptions
                    domain_pattern = domain_pattern[1:]
                    exclude_domain_paterns.append(re.compile(domain_pattern))
                else:
                    include_domain_patterns.append(re.compile(domain_pattern))

            self.__included_domain_patterns = include_domain_patterns
            self.__excluded_domain_patterns = exclude_domain_paterns

        if any(pattern.search(request_info.documentURL) is not None for pattern in self.__excluded_domain_patterns):
            return MatchResult.NO_MATCH

        if any(pattern.search(request_info.documentURL) is not None for pattern in self.__included_domain_patterns):
            return MatchResult.MATCH

        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_redirect(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_redirectrule(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_1p(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(request_info.request.isSameSite)

    @staticmethod
    def __matches_3p(request_info: RequestInfo, value: str):
        return MatchResult.from_bool(not request_info.request.isSameSite)

    @staticmethod
    def __matches_denyallow(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_subdocument(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_popup(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_popunder(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_inlinescript(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_csp(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_badfilter(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_generichide(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_webrtc(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_object(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_cname(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH

    @staticmethod
    def __matches_ping(request_info: RequestInfo, value: str):
        # TODO: implement functionality
        return MatchResult.NO_MATCH


class Rule(BaseModel):
    """Represents a service filtering rule."""

    rule_str: str
    url_pattern: typing.Pattern
    extended_filter_pattern: Optional[str]
    modifiers: typing.Dict[str, Modifier]
    action: Action

    def matches(self, request_info: RequestInfo):
        """
        Determines whether this rule matches the current service.

        Matching is performed by comparing the service URL to the rule's URL pattern
        and then matching against the defined modifiers for the rule.
        """
        if self.url_pattern.search(request_info.request.url) is None:
            return MatchResult.NO_MATCH

        if len(self.modifiers) == 0:
            return MatchResult.MATCH

        domain_modifier = self.modifiers.get("domain")
        if domain_modifier is not None:
            domain_modifier_result = domain_modifier.matches(request_info)
            if domain_modifier_result == MatchResult.NO_MATCH:
                return MatchResult.NO_MATCH

        third_party_modifier = self.modifiers.get("3p")
        if third_party_modifier is not None:
            third_party_modifier_result = third_party_modifier.matches(request_info)
            if third_party_modifier_result == MatchResult.NO_MATCH:
                return MatchResult.NO_MATCH

        first_party_modifier = self.modifiers.get("1p")
        if first_party_modifier is not None:
            first_party_modifier_result = first_party_modifier.matches(request_info)
            if first_party_modifier_result == MatchResult.NO_MATCH:
                return MatchResult.NO_MATCH

        modifier_match_results = [
            modifier.matches(request_info)
            for name, modifier in self.modifiers.items()
            if name not in ["domain", "1p", "3p"]
        ]

        if len(modifier_match_results) == 0:
            return MatchResult.MATCH

        has_override = any(result == MatchResult.OVERRIDE for result in modifier_match_results)
        if has_override:
            return MatchResult.OVERRIDE

        active_match_results = [result for result in modifier_match_results if result != MatchResult.IGNORE]
        if len(active_match_results) == 0:
            return MatchResult.NO_MATCH

        return MatchResult.from_bool(any(result == MatchResult.MATCH for result in active_match_results))


class RuleSetParser:
    """Parses a rule set from a file or string using uBlock/AdBlock style syntax."""

    @staticmethod
    async def parse_async(data: aiofiles.threadpool.text.AsyncTextIOWrapper):
        """
        Parse a rule set asynchronously.
        :param data: An asynchronous text stream containing the rule set to be parsed.
        :return: The parsed rule set.
        """
        is_first_line = True
        ruleset = RuleSet()
        while True:
            line = await data.readline()

            if line == "":
                break

            line = line.strip(" \r\n\t")

            if is_first_line:
                is_first_line = False
                if re.search(r"^\[Adblock(.*)]$", line) is not None:
                    # Ignore filter list format tag
                    continue

            if line == "":
                continue

            if line.startswith("!"):
                # Comment or metadata
                meta_key, meta_value = RuleSetParser.__parse_metadata(line)
                if meta_key is not None:
                    setattr(ruleset, meta_key, meta_value)
                continue

            try:
                rule = RuleSetParser.__parse_rule(line)
            except Exception:
                logging.info(f"Could not parse rule: {line}")
                continue

            if rule.action != Action.NOOP:
                # Ignore rules marked as "NOOP" for now.
                ruleset.add_rule(rule)

        return ruleset

    @staticmethod
    def parse(data: Union[str, TextIOWrapper]):
        """
        Parse a rule set synchronously.
        :param data: An text stream or a string containing the rule set to be parsed.
        :return: The parsed rule set.
        """
        if isinstance(data, str):
            data = StringIO(data)

        is_first_line = True
        ruleset = RuleSet()
        while True:
            line = data.readline()

            if line == "":
                break

            line = line.strip(" \r\n\t")

            if is_first_line:
                is_first_line = False
                if re.search(r"^\[Adblock(.*)]$", line) is not None:
                    # Ignore filter list format tag
                    continue

            if line == "":
                continue

            if line.startswith("!"):
                # Comment or metadata
                meta_key, meta_value = RuleSetParser.__parse_metadata(line)
                if meta_key is not None:
                    setattr(ruleset, meta_key, meta_value)
                continue

            try:
                rule = RuleSetParser.__parse_rule(line)
            except Exception:
                logging.info(f"Could not parse rule: {line}")
                continue

            if rule.action != Action.NOOP:
                # Ignore rules marked as "NOOP" for now.
                ruleset.add_rule(rule)

        return ruleset

    @staticmethod
    def __parse_metadata(line):
        supported_metadata = ["Title", "Homepage"]

        for meta_key in supported_metadata:
            meta_match = re.search(rf"{meta_key}:\s*(?P<{meta_key}>.*)\s*$", line)
            if meta_match is not None:
                return meta_key.lower(), meta_match.group(meta_key)

        return None, None

    @staticmethod
    def __parse_rule(line):
        action = Action.DENY
        rule_str = line
        if line.startswith("@@"):
            action = Action.ALLOW
            line = line[2:]

        if "#@#" in line:
            action = Action.ALLOW

        url_pattern_str, extended_filter_pattern, modifiers_str = RuleSetParser.__split_rule_parts(line)

        url_pattern = RuleSetParser.__parse_url_pattern(url_pattern_str)
        extended_filter_pattern = RuleSetParser.__parse_extended_filter_pattern(extended_filter_pattern)

        if extended_filter_pattern is not None:
            # Cosmetic/other extended filters are not currently supported.
            action = Action.NOOP

        modifiers = dict()
        if modifiers_str is not None:
            for modifier_str in modifiers_str.split(","):
                modifier = RuleSetParser.__parse_modifier(modifier_str)
                modifiers[modifier.name] = modifier

        return Rule(rule_str=rule_str,
                    url_pattern=url_pattern,
                    extended_filter_pattern=extended_filter_pattern,
                    modifiers=modifiers,
                    action=action)

    @staticmethod
    def __split_rule_parts(line):
        extended_filter_pattern_str = None
        modifiers_str = None

        if "##" in line:
            # The rule is a cosmetic/other extended filter.
            rule_parts = line.split("##", maxsplit=1)
            extended_filter_pattern_str = rule_parts[1]
        elif "#@#" in line:
            # The rule is a cosmetic/other extended filter exception.
            rule_parts = line.split("#@#", maxsplit=1)
            extended_filter_pattern_str = rule_parts[1]
        elif "#?#" in line:
            # The rule is a cosmetic/other extended filter exception.
            rule_parts = line.split("#?#", maxsplit=1)
            extended_filter_pattern_str = rule_parts[1]
        else:
            # The rule is a standard URL pattern rule, optionally with
            # modifiers after the "$" character.
            rule_parts = line.split("$", maxsplit=1)
            modifiers_str = None if len(rule_parts) == 1 else rule_parts[1]

        url_pattern_str = rule_parts[0]

        return url_pattern_str, extended_filter_pattern_str, modifiers_str

    @staticmethod
    def __parse_url_pattern(url_pattern_str):
        if url_pattern_str == "*":
            # Filter all URLs
            return re.compile(r".*")

        if url_pattern_str.startswith("/") and url_pattern_str.endswith("/"):
            # URL pattern is in regex format, no need to escape
            return re.compile(url_pattern_str[1:-1])

        if re.search(r"^[a-z0-9-]+(\.[a-z0-9-]+)*$", url_pattern_str) is not None:
            # Follow uBlock syntax - the entry:
            #   example.com
            # should be treated as if it were:
            #   ||example.com^
            url_pattern_str = "||" + url_pattern_str + "^"

        # Escape any "." characters not in square brackets
        url_pattern_str = re.sub(r"\.(?![^\[]*])", r"\.", url_pattern_str)
        # Wildcard "*" matches any string
        url_pattern_str = url_pattern_str.replace("*", r".*")
        # Separator wildcard "^" matches anything that's not alphanumeric or "-", "_", ".", "%"
        # including the end of the pattern.
        # However, using the pipe character for alternates now will cause issues when escaping
        # them later, so replace with a temporary string that can be replaced later
        url_pattern_str = url_pattern_str.replace("^", "##SEPARATOR##")
        # Escape any "?" characters
        url_pattern_str = url_pattern_str.replace("?", r"\?")
        # Escape any "+" characters
        url_pattern_str = url_pattern_str.replace("+", r"\+")

        if url_pattern_str.startswith("||"):
            # Matches any scheme and constrains the URL pattern to match from the start
            url_pattern_str = r"^.*?://" + url_pattern_str[2:]
        elif url_pattern_str.startswith("|"):
            # Constrains the URL pattern to match from the start (the pattern must include the scheme)
            url_pattern_str = r"^" + url_pattern_str[1:]

        if url_pattern_str.endswith("|"):
            # Constrains the URL pattern to match from the end
            url_pattern_str = url_pattern_str[:-1] + "$"

        # Escape any remaining "|" characters
        url_pattern_str = url_pattern_str.replace("|", r"\|")

        # Implement the deferred separator wildcard ("^") pattern
        url_pattern_str = url_pattern_str.replace("##SEPARATOR##", r"([^a-zA-Z0-9-_.%]|$)")

        # Alternatives are separated by ","
        # However, if a comma is at the start or end of a pattern, treat it as
        # verbatim, to avoid empty matches on everything
        url_pattern_str = re.sub(r"(?!^),(?!$)", r"|", url_pattern_str)

        return re.compile(url_pattern_str)

    @staticmethod
    def __parse_extended_filter_pattern(extended_filter_pattern_str):
        # Not currently supported.
        # Return the string as-is.
        return extended_filter_pattern_str

    @staticmethod
    def __parse_modifier(modifier_str):
        # Modifiers have two formats:
        # <name>
        # <name>=<value>
        modifier_parts = modifier_str.split("=", maxsplit=1)
        modifier_name = modifier_parts[0]
        modifier_value = None if len(modifier_parts) < 2 else modifier_parts[1]

        return Modifier(name=modifier_name,
                        value=modifier_value)


class RuleSet(BaseModel):
    """Contains a list of rules that can be evaluated for a service."""

    title: Optional[str]
    homepage: Optional[str]
    rules: List[Rule] = Field(default_factory=list)

    def add_rule(self, rule: Rule):
        """
        Adds a rule to the rule set.
        :param rule: The rule to add.
        """
        self.rules.append(rule)

    def add_rules(self, rules: List[Rule]):
        """
        Adds a list of rules to the rule set.
        :param rules: The list of rules to add.
        """
        self.rules.extend(rules)

    def evaluate(self, request_info: RequestInfo):
        """
        Determines the action to take for the specified service.
        :param request_info: The current service.
        :return: A tuple containing the Action to take and the list of rules
        contributing to the chosen action.
        """
        rule_results = [(rule, rule.matches(request_info)) for rule in self.rules]

        overriding_blocking_rules = [
            rule for rule, result in rule_results
            if rule.action == Action.DENY and result == MatchResult.OVERRIDE
        ]
        overriding_allowing_rules = [
            rule for rule, result in rule_results
            if rule.action == Action.ALLOW and result == MatchResult.OVERRIDE
        ]

        if len(overriding_allowing_rules) > 0:
            return Action.ALLOW, overriding_allowing_rules

        if len(overriding_blocking_rules) > 0:
            return Action.DENY, overriding_blocking_rules

        blocking_rules = [
            rule for rule, result in rule_results
            if rule.action == Action.DENY and result == MatchResult.MATCH
        ]
        allowing_rules = [
            rule for rule, result in rule_results
            if rule.action == Action.ALLOW and result == MatchResult.MATCH
        ]

        if len(allowing_rules) > 0:
            return Action.ALLOW, allowing_rules

        if len(blocking_rules) > 0:
            return Action.DENY, blocking_rules

        return Action.NOOP, None
