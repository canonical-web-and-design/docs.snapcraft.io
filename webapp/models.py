# Core
import re

# Third-party
import dateutil.parser
import humanize
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from urllib.parse import urlparse
from canonicalwebteam.http import CachedSession


# Constants
DEFAULT_SESSION = CachedSession(expire_after=5, old_data_on_error=True)


class RedirectFoundError(HTTPError):
    """
    If we encounter redirects from Discourse, we need to take action
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        url_parts = urlparse(self.response.headers["Location"])
        self.redirect_path = url_parts.path.rstrip(".json")


class NavigationParseError(Exception):
    """
    Indicates a failure to extract the navigation from
    the frontpage content
    """

    def __init__(self, document, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.document = document


class DiscourseDocs:
    """
    A basic model class for retrieving Documentation content
    from a Discourse installation through the API
    """

    def __init__(self, base_url, frontpage_id, session=DEFAULT_SESSION):
        """
        @param base_url: The Discourse URL (e.g. https://discourse.example.com)
        @param frontpage_id: The ID of the frontpage topic in Discourse.
                            This topic should also contain the navigation.
        """

        self.base_url = base_url.rstrip("/")
        self.frontpage_id = frontpage_id
        self.session = session

    def __del__(self):
        self.session.close()

    def get_document(self, path):
        """
        Retrieve and return relevant data about a document:
        - Title
        - HTML content
        - Navigation content
        """

        parse_error = None

        try:
            frontpage, nav_html = self.parse_frontpage()
        except NavigationParseError as err:
            parse_error = err
            frontpage = parse_error.document

        if f"{self.base_url}/t/{path}" == frontpage["forum_link"]:
            document = frontpage
        else:
            document = self._parse_document_topic(self._get_topic(path))

        if parse_error:
            parse_error.document = document
            raise parse_error

        return document, nav_html

    def parse_frontpage(self):
        """
        Parse the frontpage document topic to extract the Navigation markup
        from it
        """

        # Get topic data
        frontpage_topic = self._get_topic(self.frontpage_id)
        frontpage_document = self._parse_document_topic(frontpage_topic)

        # Split HTML into nav and body
        soup = BeautifulSoup(
            frontpage_document["body_html"], features="html.parser"
        )
        splitpoint = soup.find(re.compile("^h[1-6]$"), text="Content")

        if splitpoint:
            body_elements = splitpoint.fetchPreviousSiblings()
            frontpage_document["body_html"] = "".join(
                map(str, reversed(body_elements))
            )

            nav_elements = splitpoint.fetchNextSiblings()
            nav_html = "".join(map(str, nav_elements))
        else:
            raise NavigationParseError(
                frontpage_document,
                "Error: Failed to parse navigation from "
                + frontpage_document["forum_link"]
                + ". Please check the format.",
            )

        return frontpage_document, nav_html

    # Private helper methods
    # ===

    def _process_html(self, html):
        """
        Post-process the HTML output from Discourse to
        remove 'NOTE TO EDITORS' sections
        """

        soup = BeautifulSoup(html, features="html.parser")
        notes_to_editors_spans = soup.find_all(text="NOTE TO EDITORS")

        for span in notes_to_editors_spans:
            container = span.parent.parent.parent.parent

            if (
                container.name == "aside"
                and "quote" in container.attrs["class"]
            ):
                container.decompose()

        return str(soup)

    def _parse_document_topic(self, topic):
        """
        Parse a topic object retrieve from Discourse
        and return document data:
        - title: The title
        - body_html: The HTML content of the initial topic post
                     (with some post-processing)
        - updated: A human-readable data, relative to now
                   (e.g. "3 days ago")
        - forum_link: The link to the original forum post
        """

        updated_datetime = dateutil.parser.parse(
            topic["post_stream"]["posts"][0]["updated_at"]
        )

        return {
            "title": topic["title"],
            "body_html": self._process_html(
                topic["post_stream"]["posts"][0]["cooked"]
            ),
            "updated": humanize.naturaltime(
                updated_datetime.replace(tzinfo=None)
            ),
            "forum_link": f"{self.base_url}/t/{topic['slug']}/{topic['id']}",
        }

    def _get_topic(self, path):
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
