# Core
from urllib.parse import urlparse, urlunparse, unquote

# Third-party
import flask
import prometheus_flask_exporter
from canonicalwebteam.http import CachedSession

# Local
from webapp import helpers, redirects


INSIGHTS_ADMIN_URL = 'https://admin.insights.ubuntu.com'

app = flask.Flask(__name__)
app.template_folder = '../templates'
app.static_folder = '../static'
app.url_map.strict_slashes = False
app.url_map.converters['regex'] = helpers.RegexConverter

if not app.debug:
    metrics = prometheus_flask_exporter.PrometheusMetrics(
        app,
        group_by_endpoint=True,
        buckets=[0.25, 0.5, 0.75, 1, 2],
        path=None
    )
    metrics.start_http_server(port=9990, endpoint='/')

app.before_request(
    redirects.prepare_redirects(
        permanent_redirects_path='permanent-redirects.yaml',
        redirects_path='redirects.yaml'
    )
)

discourse_api_session = CachedSession(expire_after=60)


@app.before_request
def clear_trailing():
    """
    Remove trailing slashes from all routes
    We like our URLs without slashes
    """

    parsed_url = urlparse(unquote(flask.request.url))
    path = parsed_url.path

    if path != '/' and path.endswith('/'):
        new_uri = urlunparse(
            parsed_url._replace(path=path[:-1])
        )

        return flask.redirect(new_uri)


@app.route('/<path:path>')
def homepage(path):
    results = discourse_api_session.get(
        "https://forum.snapcraft.io/t/{path}.json".format(**locals())
    ).json()

    return flask.render_template(
        'document.html',
        title=results['title'],
        document_content=results['post_stream']['posts'][0]['cooked']
    )


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


@app.errorhandler(410)
def page_deleted(e):
    return flask.render_template('410.html'), 410


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('500.html'), 500
