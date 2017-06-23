"""
PART 1: APP
A simple Flask web application that shows the latest wats from the database
and accepts POST requests to queue new wats in DynamoDB.

Served through API Gateway and uses the `serverless-wsgi` plugin to translate
requests to WSGI, which is what Flask understands.
"""
import flask
import helpers

app = flask.Flask(__name__)


@app.route("/", methods=['GET'])
def index():
    """
    Shows the latest wats!
    """
    return flask.render_template('home.html', items=helpers.get_wats())


@app.route("/", methods=['POST'])
def create():
    """
    Creates a brand new wat.
    """
    helpers.create_wat(flask.request.form['url'])
    return flask.redirect(flask.url_for('index'))
