{% extends "base.md" -%}
{% block title %}LinkCheckBot report{% endblock -%}
{% block content -%}
{% for page in pages -%}
### Page: {{ page.title|safe }} ({{ page.url|safe }})
{% if page.results|length == 1 %}
There was one filtered request while navigating to this page.
{% elif page.results|length > 2 %}
There were {{ page.results|length }} filtered requests while navigating to this page.
{% else %}
✅ This site appears to be clean!
Bear in mind that it is not possible to determine what happens on the server's
end - it can still keep track of some data about you like your IP address.
{% endif %}
{% endfor %}
{% endblock -%}
