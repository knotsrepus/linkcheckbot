import re


class LinkFinder:
    # From https://stackoverflow.com/a/8943487, modified to also detect links starting with www.
    __pattern__ = re.compile(r"\b(?:https?://|www\.)[-a-zA-Z0-9+&@#/%?=~_|!:,.;]*[-a-zA-Z0-9+&@#/%=~_|]")

    @staticmethod
    def find_links(text):
        return [match.group(0) for match in LinkFinder.__pattern__.finditer(text)]
