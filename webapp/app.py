# Core
from urllib.parse import urlparse, urlunparse, unquote

# Third-party
import flask
import humanize
import prometheus_flask_exporter
from requests.exceptions import HTTPError

# Local
from webapp.models import DiscourseDocs, RedirectFoundError


discourse = DiscourseDocs(
    base_url="https://forum.snapcraft.io/", frontpage_id=3781
)

app = flask.Flask(__name__)
app.template_folder = "../templates"
app.static_folder = "../static"
app.url_map.strict_slashes = False

if not app.debug:
    metrics = prometheus_flask_exporter.PrometheusMetrics(
        app, group_by_endpoint=True, buckets=[0.25, 0.5, 0.75, 1, 2], path=None
    )
    metrics.start_http_server(port=9990, endpoint="/")


@app.errorhandler(404)
def page_not_found(e):
    frontpage, nav_html = discourse.get_frontpage()

    return flask.render_template("404.html", navigation_html=nav_html), 404


@app.errorhandler(410)
def page_deleted(e):
    frontpage, nav_html = discourse.get_frontpage()

    return (flask.render_template("410.html", navigation_html=nav_html), 410)


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

    frontpage, nav_html = discourse.get_frontpage()

    return flask.redirect(frontpage["path"])


@app.route("/t/<path:path>")
def document(path):
    try:
        document, nav_html = discourse.get_document(path)
    except RedirectFoundError as redirect_error:
        return flask.redirect(redirect_error.redirect_path)
    except HTTPError as http_error:
        flask.abort(http_error.response.status_code)

    return flask.render_template(
        "document.html",
        title=document["title"],
        body_html=document["body_html"],
        forum_link=document["forum_link"],
        updated=humanize.naturaltime(document["updated"].replace(tzinfo=None)),
        nav_html=nav_html,
    )
