{% extends "base.md" -%}
{% block title %}LinkCheckBot report{% endblock -%}
{% block content -%}
{% for page in pages -%}
### Page: {{ page.title|safe }} ({{ page.url|safe }})

{% for item in page.results -%}
{% if loop.previtem is undefined -%}
| Filter list | Requested URL | Rule(s) |
|-------------|---------------|---------|
{% endif -%}
| [{{ item.ruleset_title|safe }}]({{ item.ruleset_homepage|safe }}) | {{ item.requested_url|safe }} | `{{ item.active_rules|map("replace", "|", "¦")|join("`, `")|safe }}` |
{% else -%}
✅ This site appears to be clean!
Bear in mind that it is not possible to determine what happens on the server's
end - it can still keep track of some data about you like your IP address.
{% endfor %}
{% endfor %}
{% endblock -%}