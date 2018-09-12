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
        frontpage_html = frontpage["body_html"]
        frontpage_soup = BeautifulSoup(frontpage_html, features="html.parser")
        frontpage_splitpoint = frontpage_soup.find(
            re.compile("^h[1-6]$"), text="Content"
        )
        content_elements = frontpage_splitpoint.fetchPreviousSiblings()
        nav_elements = frontpage_splitpoint.fetchNextSiblings()

        # Update frontpage
        frontpage["body_html"] = "\n".join(
            map(str, reversed(content_elements))
        )
        nav_html = "\n".join(map(str, nav_elements))

        return frontpage, nav_html

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

        return document, nav_html
