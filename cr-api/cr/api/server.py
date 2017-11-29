""" Crunch Fitness test """
import cherrypy
import datetime
import hashlib
import json
import re
import sys

from bson.objectid import ObjectId
import numpy as np

from cr.api.static_html import LOGIN_HTML, LOGOUT_HTML
from cr.db.loader import load_data
from cr.db.store import global_settings as settings, connect

EARTH_MEAN_RADIUS = 6371008.8
EMAIL_REGEX = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
REQUIRED_LOGIN_POST_PARAMETERS = ['username', 'password']
REQUIRED_REGISTRATION_PARAMETERS = ['longitude', 'latitude', 'email', 'company', 'last_name', 'first_name']


class Root(object):
    """ Crunch Fitness test """

    def __init__(self, settings):
        """ Connect to the given database and activate session management """
        self.db = connect(settings)
        cherrypy.config.update({'tools.sessions.on': True})

    @cherrypy.tools.allow(methods=['GET'])
    @cherrypy.expose
    def index(self):
        """ Return the home page HTML. """
        return 'Welcome to Crunch.  Please <a href="/login">login</a>.'

    def _get_hash(self, password):
        """ Return the Sha1 hash for the given password. """
        return hashlib.sha1(password).hexdigest()

    def _validate_new_user(self, new_user_params):
        """
        Raise a cherypy.HTTPError exception if the given new user parameters are not valid or
            the given user email is already registered.

        Possible cherrypy.HTTPError exceptions objects:
            400 status with error description - invalid parameter
            409 status with error description - user already exists
        """
        if not all(map(new_user_params.get, REQUIRED_REGISTRATION_PARAMETERS)):
            raise cherrypy.HTTPError(400, 'The following user fields must be specified: {}.'.format(', '.join(REQUIRED_REGISTRATION_PARAMETERS)))
        unexpected_parameters =  list(set(new_user_params.keys()) - set(REQUIRED_REGISTRATION_PARAMETERS + ['password']))
        if unexpected_parameters:
            plural = 's' if len(unexpected_parameters) > 1 else ''
            raise cherrypy.HTTPError(400, 'Unexpected parameter{}: {}.'.format(plural, ', '.join(unexpected_parameters)))
        try:
            latitude, longitude = float(new_user_params['latitude']), float(new_user_params['longitude'])
        except ValueError:
            raise cherrypy.HTTPError(400, 'latitude and longitude must be numbers.')
        if latitude < -90.0 or latitude > 90.0:
            raise cherrypy.HTTPError(400, 'latitude must be between -90 and 90.')
        if longitude < -180.0 or longitude > 180.0:
            raise cherrypy.HTTPError(400, 'longitude must be between -180 and 180.')
        if not re.match(EMAIL_REGEX, new_user_params['email']):
            raise cherrypy.HTTPError(400, 'email must be a valid email address.')
        if self.db.users.count({'email': new_user_params['email']}):
            raise cherrypy.HTTPError(409, 'User \'{}\' already exists.'.format(new_user_params['email']))

    def _register_new_user(self, new_user_params):
        """ Add a new user to the database.  """
        new_user = new_user_params
        new_user['registered'] = datetime.datetime.utcnow().strftime('%A, %B %d, %Y %I:%M %p')
        if 'password' in new_user:
            password = new_user.pop('password')
            new_user['hash'] = self._get_hash(password)
        new_user['_id'] = str(ObjectId())
        self.db.users.insert_one(new_user)

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['GET', 'POST'])
    def users(self, **kwargs):
        """
        Return user data (GET) or register a new user (POST). The user must be authenticated to
        access this route.

        GET: Return a json stream of user data excluding password hashes.

        POST: Register a new user.
            Required parameters: 'longitude', 'latitude', 'email', 'company', 'last_name', 'first_name'
            Optional parameter: 'password'
            Possible response status codes / messages:
                201 with confirmation message - new user is successfully registered
                400 with error description - parameters are invalid
                409 with error description - parameters are valid but the user already exists
        """
        if 'authenticated' not in cherrypy.session:
            raise cherrypy.HTTPRedirect('/login')
        if cherrypy.request.method == 'GET':
            cherrypy.response.stream = True
            cherrypy.response.headers['Content-Type'] = 'application/json'
            # return embedded generator to allow setting 'Content-Type' header to 'application/json'
            # (see http://docs.cherrypy.org/en/latest/advanced.html#how-streaming-output-works-with-cherrypy)
            def user_stream():
                for user in self.db.users.find(projection={'hash': False}):
                    yield json.dumps(user)
            return user_stream()
        else:
            self._validate_new_user(cherrypy.request.params)
            self._register_new_user(cherrypy.request.params)
            cherrypy.response.status = "201 Resource Created"
            return '<h1>Registered new user \'{}\'<h1>'.format(cherrypy.request.params['email'])

    def _is_valid_credentials(self, username, password):
        """ Return True if the given username and password match a registered user. Return False otherwise. """
        existing_user = self.db.users.find_one({'email': username})
        if not existing_user or ('hash' not in existing_user) or (existing_user['hash'] != self._get_hash(password)):
            return False
        return True

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['GET', 'POST'])
    def login(self, **kwargs):
        """
        GET: Return the login page HTML if the user is not authenticated. Return the logout page
            HTML if the user is already authenticated.
        POST: Generate a new user session and verify the user's submitted credentials. If the
            credentials are valid, set an 'authenticated' flag in the user's session.
            Required parameters: 'username', 'password'
        """
        if cherrypy.request.method == 'GET':
            if 'authenticated' not in cherrypy.session:
                return LOGIN_HTML
            else:
                return LOGOUT_HTML
        else:
            if not all(map(cherrypy.request.params.get, REQUIRED_LOGIN_POST_PARAMETERS)):
                raise cherrypy.HTTPError(400)
            cherrypy.session.regenerate()
            if self._is_valid_credentials(cherrypy.request.params['username'], cherrypy.request.params['password']):
                cherrypy.session['authenticated'] = True
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    def logout(self):
        """ Invalidate the user's session and redirect to the login page. """
        cherrypy.session.regenerate()
        raise cherrypy.HTTPRedirect('/login')

    def _get_distance(self, locations):
        """
        Return a numpy array of all pairwise distinct "as the crow flies" distances in meters between locations
        in the given list of locations. Distances between two locations are calculated using the Haversine
        formula. Each location is a list of the form [latitude, longitude], where latitude and longitude
        are floats specified in signed decimal degrees format (eg: [38.7260, -77.7197]).

        Example usage:
        > self._get_distance([[-23.6352, 110.3726], [53.0917, -172.3206], [-81.5872, 30.5518], [4.8300, 0.5632]])
        np.array([11288336.917793995, 7244072.094304907, 12238910.359436689, 16755498.409648465, 13539906.08749783, 9733685.182006456])
        """
        locations = np.deg2rad(locations)
        latitudes = locations[:,0]
        longitudes = locations[:,1]

        unique_pair_index_1, unique_pair_index_2 = np.triu_indices(latitudes.size, 1)
        latitude_delta = latitudes[unique_pair_index_1] - latitudes[unique_pair_index_2]
        longitude_delta = longitudes[unique_pair_index_1] - longitudes[unique_pair_index_2]

        radicand = np.sin(latitude_delta / 2)**2 + \
                   np.cos(latitudes[unique_pair_index_1]) * np.cos(latitudes[unique_pair_index_2]) * np.sin(longitude_delta / 2)**2
        return 2 * EARTH_MEAN_RADIUS * np.arcsin(np.sqrt(radicand))

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['GET'])
    @cherrypy.tools.json_out()
    def distances(self):
        """
        Return a JSON object containing aggregate user location statistics: 'min', 'max', 'mean',
            and 'standard deviation.'
        Return {'error': 'Not enough users to provide distance statistics.'} if the number of user
            locations is less than 2, since we need at least two locations to calculate all statistics.
        """
        locations = [
            [float(u['latitude']), float(u['longitude'])]
            for u in self.db.users.find(projection={'latitude': True, 'longitude': True, '_id': False})
        ]
        if len(locations) < 2:
            return {'error': 'Not enough users to provide distance statistics.'}
        distance = self._get_distance(locations)
        return {
            'min': np.min(distance),
            'max': np.max(distance),
            'mean': np.sum(distance) / distance.size,
            'standard deviation': np.std(distance)
        }


def run():
    settings.update(json.load(file(sys.argv[1])))
    cherrypy.quickstart(Root(settings))
