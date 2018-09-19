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
    configuration_options_redirect,
)


class TestDiscourseDocs(unittest.TestCase):
    def setUp(self):
        responses.add(
            documentation_outline_topic,
            frontpage_by_id,
            getting_started_wiki,
            configuration_options_redirect,
        )

        self.discourse = models.DiscourseDocs(
            base_url="https://forum.snapcraft.io", frontpage_id=3781
        )

    def tearDown(self):
        self.discourse.session.close()

    def test_get_topic(self):
        # Test topics
        topic = self.discourse.get_topic("documentation-outline/3781")
        topic_by_id = self.discourse.get_topic("3781")
        topic_html = topic["post_stream"]["posts"][0]["cooked"]
        topic_html_by_id = topic_by_id["post_stream"]["posts"][0]["cooked"]

        self.assertEqual(topic["title"], "Documentation outline")
        self.assertEqual(topic_by_id["title"], "Documentation outline")
        self.assertTrue("<p>This is the experimental snap" in topic_html)
        self.assertTrue("<p>This is the experimental snap" in topic_html_by_id)

        # Test wiki pages
        wiki_topic = self.discourse.get_topic("getting-started/3876")
        wiki_html = wiki_topic["post_stream"]["posts"][0]["cooked"]

        self.assertEqual(wiki_topic["title"], "Getting started")
        self.assertTrue("<strong>NOTE TO EDITORS</strong>" in wiki_html)

    def test_get_topic_redirects(self):
        # Test redirects
        with self.assertRaises(models.RedirectFoundError) as context:
            self.discourse.get_topic("configuration-options/87")

        self.assertEqual(
            "/t/system-options/87",
            context.exception.redirect_path,
        )


if __name__ == "__main__":
    unittest.main()
