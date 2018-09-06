# Core
import re

# Third-party
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
        self.session = CachedSession(expire_after=60)

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

    def get_frontpage_nav_and_content(self):
        frontpage = self.get_topic(self.frontpage_id)
        frontpage_html = frontpage["post_stream"]["posts"][0]["cooked"]
        frontpage_soup = BeautifulSoup(frontpage_html, features="html.parser")

        frontpage_splitpoint = frontpage_soup.find(
            re.compile("^h[1-6]$"), text="Content"
        )

        content_elements = frontpage_splitpoint.fetchPreviousSiblings()
        nav_elements = frontpage_splitpoint.fetchNextSiblings()

        nav_html = "\n".join(map(str, nav_elements))
        content_html = "\n".join(map(str, content_elements))

        return (nav_html, content_html)

    def get_document(self, path):
        """
        Retrieve and return relevant data about a document:
        - Title
        - HTML content
        - Navigation content
        """

        topic = self.get_topic(path)

        (nav_html, content_html) = self.get_frontpage_nav_and_content()

        if topic["id"] != self.frontpage_id:
            content_html = topic["post_stream"]["posts"][0]["cooked"]

        return {
            "title": topic["title"],
            "content_html": content_html,
            "nav_html": nav_html,
        }

    def get_frontpage_url(self):
        """
        Get the URL of the front page
        """

        topic = self.get_topic(self.frontpage_id)

        return f"/t/{topic['slug']}/{topic['id']}"
