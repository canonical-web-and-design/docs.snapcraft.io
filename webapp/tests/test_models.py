# Core
import unittest

# Modules
import responses
import requests_mock
from flask_testing import TestCase
from requests import Session

# Local
from webapp.app import app
from webapp import models


class TestGoogleSearchApi(unittest.TestCase):
    def setUp(self):
        self.mock_session = Session()
        google_api_mock_adapter = requests_mock.Adapter()
        google_api_mock_adapter.register_uri(
            "GET",
            (
                "https://www.googleapis.com/customsearch/v1"
                "?key=key&cx=cx&q=q&start=start&num=num"
                "&siteSearch=docs.snapcraft.io"
            ),
            json={
                "items": [{"htmlSnippet": "<br>\n"}, {"htmlSnippet": "<br>\n"}]
            },
        )
        self.mock_session.mount("https://", google_api_mock_adapter)

    def test_replace_line_breaks(self):
        results = models.get_search_results(
            "key",
            "https://www.googleapis.com/customsearch/v1?",
            "cx",
            "q",
            "start",
            "num",
            session=self.mock_session,
        )

        self.assertEqual(
            {"entries": [{"htmlSnippet": ""}, {"htmlSnippet": ""}]}, results
        )

    def test_raise_no_api_key_error(self):
        with self.assertRaises(models.NoAPIKeyError):
            models.get_search_results(
                None,
                "https://www.googleapis.com/customsearch/v1?",
                "cx",
                "q",
                "start",
                "num",
                session=self.mock_session,
            )


class TestSearchViewNoApiKey(TestCase):
    def create_app(self):
        test_app = app
        test_app.testing = True
        test_app.config["SEARCH_API_KEY"] = None
        return test_app

    def test_no_api_key_500(self):
        with self.assertRaises(models.NoAPIKeyError):
            self.client.get("/search?q=test")


class TestSearchView(TestCase):
    def create_app(self):
        test_app = app
        test_app.testing = True
        test_app.config["SEARCH_API_KEY"] = "test"
        return test_app

    @responses.activate
    def test_search_no_results(self):
        responses.add(
            responses.GET,
            (
                "https://www.googleapis.com/customsearch/v1"
                "?key=test"
                "&cx=009048213575199080868:i3zoqdwqk8o"
                "&q=nothing"
                "&start=1"
                "&num=10"
                "&siteSearch=docs.snapcraft.io"
            ),
            json={"items": []},
        )

        response = self.client.get("/search?q=nothing")
        self.assert200(response)
        self.assertContext("query", "nothing")
        self.assertContext("start", 1)
        self.assertContext("num", 10)
        self.assertContext("results", {"entries": []})

    @responses.activate
    def test_search(self):
        responses.add(
            responses.GET,
            (
                "https://www.googleapis.com/customsearch/v1"
                "?key=test"
                "&cx=009048213575199080868:i3zoqdwqk8o"
                "&q=everything"
                "&start=1"
                "&num=10"
                "&siteSearch=docs.snapcraft.io"
            ),
            json={
                "items": [{"htmlSnippet": "<br>\n"}, {"htmlSnippet": "<br>\n"}]
            },
        )

        response = self.client.get("/search?q=everything")
        self.assert200(response)
        self.assertContext("query", "everything")
        self.assertContext("start", 1)
        self.assertContext("num", 10)
        self.assertContext(
            "results", {"entries": [{"htmlSnippet": ""}, {"htmlSnippet": ""}]}
        )


if __name__ == "__main__":
    unittest.main()
