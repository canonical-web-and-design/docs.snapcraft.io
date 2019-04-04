# Core
import os
from urllib.parse import urlparse, urlunparse, unquote

# Third-party
import flask
from flask import current_app, request
from requests.exceptions import HTTPError
from canonicalwebteam.yaml_responses.flask_helpers import (
    prepare_deleted,
    prepare_redirects,
)
from werkzeug.debug import DebuggedApplication

# Local
from webapp.models import (
    DiscourseDocs,
    get_search_results,
    NavigationParseError,
    RedirectFoundError,
)


discourse = DiscourseDocs(
    base_url="https://forum.snapcraft.io/",
    frontpage_id=3781,
    category_id=15,  # The "doc" category
)


app = flask.Flask(__name__)

if app.debug:
    app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

app.config["SEARCH_API_KEY"] = os.getenv("SEARCH_API_KEY")
app.config["SEARCH_API_URL"] = "https://www.googleapis.com/customsearch/v1"
app.config["SEARCH_CUSTOM_ID"] = "009048213575199080868:i3zoqdwqk8o"

app.template_folder = "../templates"
app.static_folder = "../static"
app.url_map.strict_slashes = False

# Parse redirects.yaml and permanent-redirects.yaml
app.before_request(prepare_redirects())


def deleted_callback(context):
    try:
        frontpage, nav_html = discourse.parse_frontpage()
    except NavigationParseError as nav_error:
        nav_html = f"<p>{str(nav_error)}</p>"

    return (
        flask.render_template("410.html", nav_html=nav_html, **context),
        410,
    )


app.before_request(prepare_deleted(view_callback=deleted_callback))


@app.errorhandler(404)
def page_not_found(e):
    try:
        frontpage, nav_html = discourse.parse_frontpage()
    except NavigationParseError as nav_error:
        nav_html = f"<p>{str(nav_error)}</p>"

    return flask.render_template("404.html", nav_html=nav_html), 404


@app.errorhandler(410)
def deleted(e):
    return deleted_callback({})


@app.errorhandler(500)
def server_error(e):
    return flask.render_template("500.html"), 500


@app.before_request
def clear_trailing():
    """
    Remove trailing slashes from all routes
    We like our URLs without slashes
    """

    parsed_url = urlparse(unquote(flask.request.url))
    path = parsed_url.path

    if path != "/" and path.endswith("/"):
        new_uri = urlunparse(parsed_url._replace(path=path[:-1]))

        return flask.redirect(new_uri)


@app.route("/")
def homepage():
    """
    Redirect to the frontpage topic
    """

    frontpage, nav_html = discourse.parse_frontpage()

    return flask.redirect(frontpage["path"])


@app.route("/<path:path>")
def document(path):
    try:
        document, nav_html = discourse.get_document(path)
    except RedirectFoundError as redirect_error:
        return flask.redirect(redirect_error.redirect_path)
    except HTTPError as http_error:
        flask.abort(http_error.response.status_code)
    except NavigationParseError as nav_error:
        document = nav_error.document
        nav_html = f"<p>{str(nav_error)}</p>"

    return flask.render_template(
        "document.html",
        title=document["title"],
        body_html=document["body_html"],
        forum_link=document["forum_link"],
        updated=document["updated"],
        nav_html=nav_html,
    )


@app.route("/search")
def search():
    """
    Get search results from Google Custom Search
    """
    search_api_key = current_app.config["SEARCH_API_KEY"]
    search_api_url = current_app.config["SEARCH_API_URL"]
    search_custom_id = current_app.config["SEARCH_CUSTOM_ID"]

    query = request.args.get("q")
    num = int(request.args.get("num", "10"))
    start = int(request.args.get("start", "1"))

    context = {"query": query, "start": start, "num": num}

    if query:
        context["results"] = get_search_results(
            search_api_key, search_api_url, search_custom_id, query, start, num
        )

    return flask.render_template("search.html", **context)
