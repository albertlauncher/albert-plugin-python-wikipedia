# -*- coding: utf-8 -*-
# Copyright (c) 2024 Manuel Schneider


from albert import *
from locale import getdefaultlocale
from socket import timeout
from time import sleep
from urllib import request, parse
import json
import re
from pathlib import Path

md_iid = "5.0"
md_version = "3.1.1"
md_name = "Wikipedia"
md_description = "Search Wikipedia articles"
md_license = "MIT"
md_url = "https://github.com/albertlauncher/albert-plugin-python-wikipedia"
md_authors = ["@ManuelSchneid3r"]
md_maintainers = ["@ManuelSchneid3r"]

class Plugin(PluginInstance, GeneratorQueryHandler):

    wikiurl = "https://en.wikipedia.org/wiki/"
    baseurl = 'https://en.wikipedia.org/w/api.php'
    searchUrl = 'https://%s.wikipedia.org/wiki/Special:Search/%s'
    user_agent = "org.albert.wikipedia"

    def __init__(self):
        PluginInstance.__init__(self)
        GeneratorQueryHandler.__init__(self)

        self.fbh = FBH(self)

        self.local_lang_code = getdefaultlocale()[0]
        if self.local_lang_code:
            self.local_lang_code = self.local_lang_code[0:2]
        else:
            self.local_lang_code = 'en'
            warning("Failed getting language code. Using 'en'.")

        params = {
            'action': 'query',
            'meta': 'siteinfo',
            'utf8': 1,
            'siprop': 'languages',
            'format': 'json'
        }

        get_url = "%s?%s" % (self.baseurl, parse.urlencode(params))
        req = request.Request(get_url, headers={'User-Agent': self.user_agent})
        try:
            with request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                languages = [lang['code'] for lang in data['query']['languages']]
                if self.local_lang_code in languages:
                    Plugin.baseurl = Plugin.baseurl.replace("en", self.local_lang_code)
                    Plugin.wikiurl = Plugin.wikiurl.replace("en", self.local_lang_code)
                    self.baseurl = self.baseurl.replace("en", self.local_lang_code)
        except timeout:
            warning('Error getting languages - socket timed out. Defaulting to EN.')
        except Exception as error:
            warning('Error getting languages (%s). Defaulting to EN.' % error)

    @staticmethod
    def makeIcon():
        return Icon.image(Path(__file__).parent / "wikipedia.png")

    def extensions(self):
        return [self, self.fbh]

    def defaultTrigger(self):
        return "wiki "

    def fetch(self, query: str, batch_size: int, offset: int):

        params = {
            'action': 'query',
            'format': 'json',
            'formatversion': 2,
            'list': 'search',
            'srlimit': batch_size,
            'sroffset': offset,
            'srsearch': query,
        }

        get_url = "%s?%s" % (self.baseurl, parse.urlencode(params))
        req = request.Request(get_url, headers={'User-Agent': self.user_agent})

        with request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))

        results = []
        for match in data['query']['search']:

            title = match['title']
            snippet = re.sub("<.*?>", "", match['snippet'])
            url = self.wikiurl + parse.quote(title.replace(' ', '_'))

            results.append(
                StandardItem(
                    id=self.id(),
                    text=title,
                    subtext=snippet if snippet else url,
                    icon_factory=Plugin.makeIcon,
                    actions=[
                        Action("open", "Open article", lambda u=url: openUrl(u)),
                        Action("copy", "Copy URL", lambda u=url: setClipboardText(u))
                    ]
                )
            )
        return results

    def items(self, ctx):
        query = ctx.query.strip()

        if not query:
            yield [StandardItem(id=self.id(),
                                text=self.name(),
                                subtext="Enter a query to search on Wikipedia",
                                icon_factory=Plugin.makeIcon)]
            return

        # naive throttling
        # https://www.mediawiki.org/wiki/Wikimedia_REST_API#Terms_and_conditions
        for _ in range(5):
            sleep(0.001)
            if not ctx.isValid:
                return

        offset = 0
        items = self.fetch(query, 10, offset)

        if not items:
            yield [self.createFallbackItem(query)]
            return

        while items:
            yield items
            offset += 10
            items = self.fetch(query, 10, offset)

    def createFallbackItem(self, q: str) -> Item:
        return StandardItem(
            id=self.id(),
            text=self.name(),
            subtext="Search '%s' on Wikipedia" % q,
            icon_factory=Plugin.makeIcon,
            actions=[
                Action("wiki_search", "Search on Wikipedia",
                       lambda url=self.searchUrl % (self.local_lang_code, q): openUrl(url))
            ]
        )


class FBH(FallbackHandler):

    def __init__(self, p: Plugin):
        FallbackHandler.__init__(self)
        self.plugin = p

    def id(self):
        return "wikipedia.fallbacks"

    def name(self):
        return md_name

    def description(self):
        return md_description

    def fallbacks(self, q :str):
        return [self.plugin.createFallbackItem(q)]
