{% extends "base.md" %}
{% block title %}LinkCheckBot help{% endblock %}

{% block content %}
LinkCheckBot can be summoned to analyse links.
For example, if someone posts a comment saying:

> Hey, check out my totally legit site! https://not-sketchy.biz

Reply with a comment containing the command `!linkcheck!` and LinkCheckBot
will determine what requests would be made by your browser if you were to click
the link.
It will report back its findings in a reply to your comment.

You can modify LinkCheckBot's behaviour in the following ways:

* `!linkcheck help!` will reply with this help information.
* `!linkcheck summary!` will provide an overview of its findings rather than
  the full report.
* `!linkcheck details!` will provide the full report.
  This is currently the default behaviour, but this may change in future.
* `!linkcheck this https://example.com!` will analyse the link following the
  `this` keyword rather than finding links in the parent comment/post.
  If a comment or post contains multiple links, this may be more convenient if
  you only care to know about one of them.  
  LinkCheckBot also supports using `summary` and `details` with `this`,
  although `this` and the link must come first:
  * **Correct** ✅: `!linkcheck this https://example.com summary!`
  * **Incorrect** ❌: `!linkcheck summary this https://example.com!`
  * **Incorrect** ❌: `!linkcheck this details https://example.com!`

LinkCheckBot works by simulating what happens when you click the link, using a
sandboxed browser in headless mode.
It collects the complete list of requests made, and compares them against the
following filter lists:

* [uBlock Origin's built-in lists](https://github.com/uBlockOrigin/uAssets/tree/master/filters)
* [EasyList](https://easylist.github.io/#easylist)
* [EasyPrivacy](https://easylist.github.io/#easyprivacy)
* [Peter Lowe's list of ad/tracking/malware servers](https://pgl.yoyo.org/adservers/policy.php)
* [URLhaus Malicious URL blocklist](https://gitlab.com/curben/urlhaus-filter#urlhaus-malicious-url-blocklist)
{% endblock %}
