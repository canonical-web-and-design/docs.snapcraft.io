# Core
import re

# Third-party
import dateutil.parser
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from urllib.parse import urlparse

# Local
from canonicalwebteam.http import CachedSession


class RedirectFoundError(HTTPError):
    """
    If we encounter redirects from Discourse, we need to take action
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        url_parts = urlparse(self.response.headers["Location"])
        self.redirect_path = url_parts.path.rstrip(".json")


class DiscourseDocs:
    """
    A basic model class for retrieving Documentation content
    from a Discourse installation through the API
    """

    def __init__(self, base_url, frontpage_id, session_class=CachedSession):
        """
        @param base_url: The Discourse URL (e.g. https://discourse.example.com)
        @param frontpage_id: The ID of the frontpage topic in Discourse.
                            This topic should also contain the navigation.
        """

        self.base_url = base_url.rstrip("/")
        self.frontpage_id = frontpage_id
        self.session = CachedSession(expire_after=300)

    def get_topic(self, path):
        """
        Retrieve topic object by path
        """

        response = self.session.get(
            f"{self.base_url}/t/{path}.json", allow_redirects=False
        )
        response.raise_for_status()

        if response.status_code >= 300:
            raise RedirectFoundError(response=response)

        return response.json()

    def parse_topic(self, topic):
        return {
            "title": topic["title"],
            "body_html": topic["post_stream"]["posts"][0]["cooked"],
            "updated": dateutil.parser.parse(
                topic["post_stream"]["posts"][0]["updated_at"]
            ),
            "forum_link": f"{self.base_url}/t/{topic['slug']}/{topic['id']}",
            "path": f"/t/{topic['slug']}/{topic['id']}",
        }

    def get_frontpage(self):
        # Get topic data
        topic = self.get_topic(self.frontpage_id)
        frontpage = self.parse_topic(topic)

        # Split HTML into nav and body
        soup = BeautifulSoup(frontpage["body_html"], features="html.parser")
        splitpoint = soup.find(re.compile("^h[1-6]$"), text="Content")

        if splitpoint:
            body_elements = splitpoint.fetchPreviousSiblings()
            frontpage["body_html"] = "\n".join(
                map(str, reversed(body_elements))
            )

            nav_elements = splitpoint.fetchNextSiblings()
            nav_html = "\n".join(map(str, nav_elements))
        else:
            nav_html = (
                "<p><em>"
                "Error: Failed to parse navigation from"
                f' <a href="{frontpage["forum_link"]}">'
                "the frontpage topic</a>."
                " Please check the format."
                "</p></em>"
            )

        return frontpage, nav_html

    def process_html(self, html):
        """
        Post-process the HTML output from Discourse to
        remove 'NOTE TO EDITORS' sections
        """

        soup = BeautifulSoup(html, features="html.parser")
        notes_to_editors_spans = soup.find_all(text="NOTE TO EDITORS")

        for span in notes_to_editors_spans:
            container = span.parent.parent.parent.parent

            if container.name == 'aside' and 'quote' in container.attrs['class']:
                container.decompose()

        return soup.prettify()

    def get_document(self, path):
        """
        Retrieve and return relevant data about a document:
        - Title
        - HTML content
        - Navigation content
        """

        document, nav_html = self.get_frontpage()

        if f"/t/{path}" != document["path"]:
            topic = self.get_topic(path)
            document = self.parse_topic(topic)

        document["body_html"] = self.process_html(document["body_html"])

        return document, nav_html
