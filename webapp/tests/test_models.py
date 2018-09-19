# Core
import unittest

# Modules
import responses

# Local
from webapp import models
from webapp.tests.fixtures.discourse_responses import (
    documentation_outline_topic,
    frontpage_by_id,
    getting_started_wiki,
    getting_started_by_id,
    configuration_options_redirect,
)


class TestDiscourseDocs(unittest.TestCase):
    def setUp(self):
        responses.add(
            documentation_outline_topic,
            frontpage_by_id,
            getting_started_wiki,
            getting_started_by_id,
            configuration_options_redirect,
        )

        self.discourse = models.DiscourseDocs(
            base_url="https://forum.snapcraft.io", frontpage_id=3781
        )

    def test_get_document(self):
        # Test redirects
        with self.assertRaises(models.RedirectFoundError) as context:
            self.discourse.get_document("configuration-options/87")

        self.assertEqual(
            "/t/system-options/87", context.exception.redirect_path
        )

        topic_doc, topic_nav_html = self.discourse.get_document(
            "documentation-outline/3781"
        )
        wiki_doc, wiki_nav_html = self.discourse.get_document(
            "getting-started/3876"
        )

        self.assertEqual(topic_doc["title"], "Documentation outline")
        self.assertTrue(bool(topic_doc.get("updated")))
        self.assertTrue("the experimental snap" in topic_doc["body_html"])
        self.assertEqual(
            topic_doc["forum_link"],
            "https://forum.snapcraft.io/t/documentation-outline/3781",
        )

        self.assertTrue("<h3>Publishing</h3>" in topic_nav_html)
        self.assertTrue(
            '<a href="/t/the-maven-plugin/4282">Maven</a>' in topic_nav_html
        )

        self.assertEqual(wiki_doc["title"], "Getting started")
        self.assertTrue(bool(wiki_doc.get("updated")))
        self.assertFalse("NOTE TO EDITORS" in wiki_doc["body_html"])
        self.assertTrue("<p>The following" in wiki_doc["body_html"])
        self.assertEqual(
            wiki_doc["forum_link"],
            "https://forum.snapcraft.io/t/getting-started/3876",
        )

        self.assertTrue("<h3>Publishing</h3>" in wiki_nav_html)
        self.assertTrue(
            '<a href="/t/the-maven-plugin/4282">Maven</a>' in wiki_nav_html
        )

    def test_parse_frontpage(self):
        frontpage, nav_html = self.discourse.parse_frontpage()

        self.assertFalse("<h1>Content</h1>" in frontpage["body_html"])
        self.assertTrue("Choose the topic" in frontpage["body_html"])
        self.assertEqual("Documentation outline", frontpage["title"])
        self.assertEqual(
            "https://forum.snapcraft.io/t/documentation-outline/3781",
            frontpage["forum_link"],
        )

        self.assertTrue("<h3>Publishing</h3>" in nav_html)
        self.assertTrue(
            '<a href="/t/the-maven-plugin/4282">Maven</a>' in nav_html
        )

        broken_discourse = models.DiscourseDocs(
            base_url="https://forum.snapcraft.io", frontpage_id=3876
        )

        with self.assertRaises(models.NavigationParseError) as context:
            frontpage, nav_html = broken_discourse.parse_frontpage()

        nav_error = context.exception
        doc = nav_error.document

        self.assertEqual(doc["title"], "Getting started")
        self.assertFalse("NOTE TO EDITORS" in doc["body_html"])
        self.assertTrue("<p>The following sections" in doc["body_html"])

        self.assertTrue(doc["forum_link"] in str(context.exception))


if __name__ == "__main__":
    unittest.main()
