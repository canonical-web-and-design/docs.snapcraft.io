# Core
import unittest

# Modules
import requests_mock
from requests import Session
from requests.exceptions import HTTPError

# Local
from webapp import models
from webapp.tests.fixtures.snapcraft_forum_mock import register_uris


class TestDiscourseDocs(unittest.TestCase):
    def setUp(self):
        self.mock_session = Session()
        snapcraft_mock_adapter = requests_mock.Adapter()
        self.mock_session.mount("https://", snapcraft_mock_adapter)
        register_uris(snapcraft_mock_adapter)

        self.discourse = models.DiscourseDocs(
            base_url="https://forum.snapcraft.io",
            frontpage_id=3781,
            category_id=15,  # The "doc" category
            session=self.mock_session,
        )

    def test_get_document_redirects(self):
        """
        Check that if a document topic has been renamed in Discourse,
        the DiscourseDocs model will return a RedirectFoundError,
        which will contain the "redirect_path".

        The intention is then for the client app to handle the redirect
        error, e.g. by sending a redirect response to the user.
        """

        # Catch the error
        with self.assertRaises(models.RedirectFoundError) as context:
            self.discourse.get_document("configuration-options/87")

        # Check the redirect_path points to the right place
        self.assertEqual("/system-options/87", context.exception.redirect_path)

    def test_get_document_not_found(self):
        """
        If a document topic doesn't exist in Discourse,
        the DiscourseDocs model should return a 404 requests HTTPError,
        which the client can then handle if they wish.
        """

        # Catch the error
        with self.assertRaises(HTTPError) as context:
            self.discourse.get_document("fictional-document")

        # Check it communicates the appropriate HTTP status
        self.assertEqual(404, context.exception.response.status_code)

    def test_get_document_not_in_category(self):
        """
        Check requesting a topic not in the selected category
        leads to a 404
        """

        # Catch error
        with self.assertRaises(HTTPError) as context:
            self.discourse.get_document(
                "script-to-remove-expired-kerberos-caches-for-"
                "enhanced-stability/10096"
            )

        # Check it's a 404
        self.assertEqual(404, context.exception.response.status_code)

    def test_get_document_broken_nav(self):
        """
        Check that, when we request a document that is different
        from the frontpage document, but the frontpage is set
        to a topic which doesn't contain a navigation section
        in the expected format,  that it will raise a NavigationParseError,
        but still return the requested document
        as NavigationParseError.document
        """

        # Set up a Discourse pointing at a badly formatted frontpage
        broken_discourse = models.DiscourseDocs(
            base_url="https://forum.snapcraft.io",
            frontpage_id=3876,
            category_id=15,  # The "doc" category
            session=self.mock_session,
        )

        # Catch the NavigationParseError
        with self.assertRaises(models.NavigationParseError) as context:
            document, nav_html = broken_discourse.get_document(
                "documentation-outline/3781"
            )

        # Retrieve the document from the error
        nav_error = context.exception
        doc = nav_error.document

        # Check the shape of the document content
        self.assertEqual(doc["title"], "Documentation outline")
        self.assertTrue(bool(doc.get("updated")))
        self.assertTrue("the experimental snap" in doc["body_html"])
        self.assertEqual(
            doc["forum_link"],
            "https://forum.snapcraft.io/t/documentation-outline/3781",
        )

    def test_get_document_topic(self):
        """
        Check that DiscourseDocs.get_document is able to parse
        a basic topic thread (as opposed to a wiki thread)
        and build an appropriately-shaped document dictionary.
        """

        # Get the document and navigation
        topic_doc, topic_nav_html = self.discourse.get_document(
            "documentation-outline/3781"
        )

        # Check the shape of the document content
        self.assertEqual(topic_doc["title"], "Documentation outline")
        self.assertTrue(bool(topic_doc.get("updated")))
        self.assertTrue("the experimental snap" in topic_doc["body_html"])
        self.assertEqual(
            topic_doc["forum_link"],
            "https://forum.snapcraft.io/t/documentation-outline/3781",
        )

        # Check the shape of the navigation content
        self.assertTrue("<h3>Publishing</h3>" in topic_nav_html)
        self.assertTrue(
            '<a href="/the-maven-plugin/4282">Maven</a>' in topic_nav_html
        )

    def test_get_document_wiki(self):
        """
        Check that DiscourseDocs.get_document is able to parse
        a basic wiki thread (as opposed to a basic topic thread)
        and build an appropriately-shaped document dictionary.
        """

        # Get the document and navigation
        wiki_doc, wiki_nav_html = self.discourse.get_document(
            "getting-started/3876"
        )

        # Check the shape of the document content
        self.assertEqual(wiki_doc["title"], "Getting started")
        self.assertTrue(bool(wiki_doc.get("updated")))
        self.assertFalse("NOTE TO EDITORS" in wiki_doc["body_html"])
        self.assertTrue("<p>The following" in wiki_doc["body_html"])
        self.assertEqual(
            wiki_doc["forum_link"],
            "https://forum.snapcraft.io/t/getting-started/3876",
        )

        # Check the shape of the navigation content
        self.assertTrue("<h3>Publishing</h3>" in wiki_nav_html)
        self.assertTrue(
            '<a href="/the-maven-plugin/4282">Maven</a>' in wiki_nav_html
        )

    def test_parse_frontpage_success(self):
        """
        Check that DiscourseDocs is able to retrieve the frontpage topic
        and successfully split the basic document body HTML
        and the content into the navigation HTML
        """

        # Get frontpage and nav
        frontpage, nav_html = self.discourse.parse_frontpage()

        # Check the shape of the document content
        self.assertFalse("<h1>Content</h1>" in frontpage["body_html"])
        self.assertFalse("<h3>Publishing</h3>" in frontpage["body_html"])
        self.assertTrue("Choose the topic" in frontpage["body_html"])
        self.assertEqual("Documentation outline", frontpage["title"])
        self.assertEqual(
            "https://forum.snapcraft.io/t/documentation-outline/3781",
            frontpage["forum_link"],
        )

        # Check the shape of the navigation
        self.assertTrue("<h3>Publishing</h3>" in nav_html)
        self.assertTrue(
            '<a href="/the-maven-plugin/4282">Maven</a>' in nav_html
        )

    def test_parse_frontpage_navigation_error(self):
        """
        Check that if the frontpage is set to a topic which doesn't
        contain a navigation section in the expected format,
        that it will raise a NavigationParseError, but still
        returning the original document as NavigationParseError.document
        """

        # Set up a Discourse pointing at a badly formatted frontpage
        broken_discourse = models.DiscourseDocs(
            base_url="https://forum.snapcraft.io",
            frontpage_id=3876,
            category_id=15,  # The "doc" category
            session=self.mock_session,
        )

        # Catch the NavigationParseError
        with self.assertRaises(models.NavigationParseError) as context:
            frontpage, nav_html = broken_discourse.parse_frontpage()

        # Retrieve the document from the error
        nav_error = context.exception
        doc = nav_error.document

        # Check the document still looks as expected
        self.assertEqual(doc["title"], "Getting started")
        self.assertFalse("NOTE TO EDITORS" in doc["body_html"])
        self.assertTrue("<p>The following sections" in doc["body_html"])
        self.assertTrue(doc["forum_link"] in str(context.exception))


if __name__ == "__main__":
    unittest.main()
