import logging

from jinja2 import Environment, select_autoescape, FileSystemLoader


class CommentFormatter:
    def __init__(self):
        self.__env = Environment(
            loader=FileSystemLoader("data/templates"),
            autoescape=select_autoescape(enabled_extensions=["md"])
        )
        self.__templates = {name: self.__env.get_template(name) for name in self.__env.list_templates()}

    def get_help_text(self, **kwargs):
        return self.__templates["help_text.md"].render(**kwargs)

    def get_report_text(self, report, report_format, **kwargs):
        pages = []
        for url, page in report.items():
            logging.info(f"{page.url}: {len(page.results)} requests")
            pages.append(page)
        return self.__templates[f"{report_format}.md"].render(pages=pages, **kwargs)
