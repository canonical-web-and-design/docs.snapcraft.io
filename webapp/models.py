# Core
import re
import urllib

# Third-party
import dateutil.parser
import humanize
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from urllib.parse import urlparse
from canonicalwebteam.http import CachedSession
from jinja2 import Template


# Constants
DEFAULT_SESSION = CachedSession(expire_after=300, old_data_on_error=True)


class RedirectFoundError(HTTPError):
    """
    If we encounter redirects from Discourse, we need to take action
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        url_parts = urlparse(self.response.headers["Location"])
        self.redirect_path = re.sub("/t(/.*).json", r"\1", url_parts.path)


class NotInCategoryError(HTTPError):
    """
    If we encounter redirects from Discourse, we need to take action
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        url_parts = urlparse(self.response.headers["Location"])
        self.redirect_path = re.sub("/t(/.*).json", r"\1", url_parts.path)


class NavigationParseError(Exception):
    """
    Indicates a failure to extract the navigation from
    the frontpage content
    """

    def __init__(self, document, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.document = document


# Private helper functions
# ===


def _process_html(html):
    """
    Post-process the HTML output from Discourse to
    remove 'NOTE TO EDITORS' sections.

    We expect these sections to be of the HTML format:

    <aside class="quote no-group">
      <blockquote>
        <p>
          <img title=":construction:" class="emoji" ...>
          <strong>NOTE TO EDITORS</strong>
          <img title=":construction:" class="emoji" ...>
        </p>
        <p> ... </p>
      </blockquote>
    </aside>
    """

    soup = BeautifulSoup(html, features="html.parser")
    notes_to_editors_text = soup.find_all(text="NOTE TO EDITORS")

    soup = _replace_notifications(soup)

    for text in notes_to_editors_text:
        # If this section is of the expected HTML format,
        # we should find the <aside> container 4 levels up from
        # the "NOTE TO EDITORS" text
        container = text.parent.parent.parent.parent

        if container.name == "aside" and "quote" in container.attrs["class"]:
            container.decompose()

    return str(soup)


def _replace_notifications(soup):
    """
    Given some BeutifulSoup of a document,
    replace blockquotes with the appropriate notification markup
    """

    with open("templates/_notification.html") as notification_file:
        notification_template = Template(notification_file.read())

    for note in soup.findAll(text=re.compile("ⓘ ")):
        paragraph = note.parent
        blockquote = paragraph.parent

        if paragraph.name == "p" and blockquote.name == "blockquote":
            text_contents = paragraph.encode_contents().decode("utf-8")
            new_contents = re.sub("^ⓘ ", "", text_contents)

            notification_html = notification_template.render(
                notification_class="p-notification", contents=new_contents
            )
            blockquote.replace_with(
                BeautifulSoup(notification_html, features="html.parser")
            )

    for warning in soup.findAll("img", title=":warning:"):
        paragraph = warning.parent
        blockquote = paragraph.parent

        if paragraph.name == "p" and blockquote.name == "blockquote":
            warning.decompose()
            text_contents = paragraph.encode_contents().decode("utf-8")
            new_contents = re.sub("^ ", "", text_contents)

            notification_html = notification_template.render(
                notification_class="p-notification--caution",
                contents=new_contents,
            )
            blockquote.replace_with(
                BeautifulSoup(notification_html, features="html.parser")
            )

    return soup


class DiscourseDocs:
    """
    A basic model class for retrieving Documentation content
    from a Discourse installation through the API
    """

    def __init__(
        self,
        base_url,
        frontpage_id,
        category_id,
        category_name,
        session=DEFAULT_SESSION,
    ):
        """
        @param base_url: The Discourse URL (e.g. https://discourse.example.com)
        @param frontpage_id: The ID of the frontpage topic in Discourse.
                            This topic should also contain the navigation.
        """

        self.base_url = base_url.rstrip("/")
        self.frontpage_id = frontpage_id
        self.category_id = category_id
        self.category_name = category_name
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
            nav_soup = BeautifulSoup(nav_html, features="html.parser")

            # Convert links to the form needed in this site
            for link in nav_soup.find_all("a"):
                if "href" in link.attrs:
                    url = link.attrs["href"]
                    link_match = f"^({self.base_url})?/t(/.*)$"
                    link.attrs["href"] = re.sub(link_match, r"\2", url)
        else:
            raise NavigationParseError(
                frontpage_document,
                "Error: Failed to parse navigation from "
                + frontpage_document["forum_link"]
                + ". Please check the format.",
            )

        return frontpage_document, str(nav_soup)

    def search_docs(self, term):
        q = urllib.parse.quote_plus(f"{term} #{self.category_name}")
        search_endpoint = f"{self.base_url}/search.json?q={q}"
        response = self.session.get(search_endpoint)
        search_results = response.json()
        return search_results

    # Private helper methods
    # ===

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
            "body_html": _process_html(
                topic["post_stream"]["posts"][0]["cooked"]
            ),
            "updated": humanize.naturaltime(
                updated_datetime.replace(tzinfo=None)
            ),
            "forum_link": f"{self.base_url}/t/{topic['slug']}/{topic['id']}",
            "path": f"/{topic['slug']}/{topic['id']}",
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

        topic = response.json()

        # If topic not in category, raise a 404
        if topic["category_id"] != self.category_id:
            error = HTTPError(f"Topic not in category {self.category_id}")
            response.status_code = 404
            error.response = response
            raise error

        return response.json()
