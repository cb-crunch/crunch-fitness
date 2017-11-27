""" Crunch Fitness unit and functional tests """
import datetime
import json
import os
import unittest

from bson.objectid import ObjectId
import cherrypy
import numpy as np

from base import TestBase
from cr.api.server import REQUIRED_REGISTRATION_PARAMETERS, Root
from cr.db.loader import load_data
from cr.db.store import global_settings as settings

_here = os.path.dirname(__file__)
VALID_REGISTER_USER_PARAMS = {
    'first_name': 'Sal',
    'last_name': 'Dibasio',
    'company': 'Crunch',
    'longitude': 33,
    'latitude': 77,
    'email': 'a@b.com',
    'password': 'pass1234'
}

class UnitTests(unittest.TestCase):
    """ Crunch Fitness unit tests """

    def setup_method(self, method):
        settings.update({"url": "mongodb://localhost:27017/test_crunch_fitness"})
        self.root = Root(settings)

    def test_get_hash(self):
        assert self.root._get_hash('H63gD&whw') == '4e93ff3258da1409c8113edd4ba3521aadb3abde'

    def test_valid_register_user_params(self):
        assert self.root._validate_new_user(VALID_REGISTER_USER_PARAMS) == None

    def test_missing_register_user_param(self):
        missing_required_param = VALID_REGISTER_USER_PARAMS.copy()
        missing_required_param.pop('first_name')
        with self.assertRaises(cherrypy.HTTPError) as context:
            self.root._validate_new_user(missing_required_param)
        assert 400 == context.exception.args[0]
        assert 'following user fields must be specified' in context.exception.args[1]

    def test_unexpected_register_user_param(self):
        unexpected_register_user_param = VALID_REGISTER_USER_PARAMS.copy()
        unexpected_register_user_param['unexpected'] = ''
        with self.assertRaises(cherrypy.HTTPError) as context:
            self.root._validate_new_user(unexpected_register_user_param)
        assert 400 == context.exception.args[0]
        assert 'Unexpected parameter' in context.exception.args[1]

    def _invalid_register_user_param_test(self, param, value, status_code, error_message):
        invalid_param =  VALID_REGISTER_USER_PARAMS.copy()
        invalid_param[param] = value
        with self.assertRaises(cherrypy.HTTPError) as context:
            self.root._validate_new_user(invalid_param)
        assert status_code == context.exception.args[0]
        assert error_message in context.exception.args[1]

    def test_nonnumeric_longitude_register_user_param(self):
        self._invalid_register_user_param_test('longitude', 'a', 400, 'latitude and longitude must be numbers')

    def test_nonnumeric_latitude_register_user_param(self):
        self._invalid_register_user_param_test('latitude', 'a', 400, 'latitude and longitude must be numbers')

    def test_invalid_longitude_register_user_param(self):
        self._invalid_register_user_param_test('longitude', '199.9', 400, 'longitude must be between -180 and 180')

    def test_invalid_latitude_register_user_param(self):
        self._invalid_register_user_param_test('latitude', '99.9', 400, 'latitude must be between -90 and 90')

    def test_invalid_email_register_user_param(self):
        self._invalid_register_user_param_test('email', 'ab@', 400, 'email must be a valid email address')

    def test_existing_user_register_user_param(self):
        self._invalid_register_user_param_test('email', 'admin@crunch.io', 409, 'already exists')

    def test_add_new_user(self):
        load_data(_here + '/../../cr-db/tests/data/users.json', settings, clear=True)
        new_user_email = 'test@domain.com'
        assert 0 == self.root.db.users.count({'email': new_user_email})
        new_user_params = VALID_REGISTER_USER_PARAMS.copy()
        new_user_params['email'] = new_user_email
        new_user_params['password'] = 'abcd1234'
        self.root._register_new_user(new_user_params)
        new_user = self.root.db.users.find_one({'email': new_user_email})
        assert new_user['first_name'] == new_user_params['first_name'] and new_user['last_name'] == new_user_params['last_name'] and \
               new_user['company'] == new_user_params['company'] and new_user['email'] == new_user_params['email'] and \
               new_user['latitude'] == new_user_params['latitude'] and new_user['longitude'] == new_user_params['longitude'] and \
               new_user['hash'] == self.root._get_hash('abcd1234') and ObjectId.is_valid(new_user['_id']) and \
               abs(datetime.datetime.strptime(new_user['registered'], '%A, %B %d, %Y %I:%M %p') - datetime.datetime.utcnow()).seconds < 120

    def test_is_valid_credentials(self):
        assert self.root._is_valid_credentials('admin@crunch.io', '123456')
        assert not self.root._is_valid_credentials('admin@crunch.io', 'abcdef')
        assert not self.root._is_valid_credentials('notauser@domain.com', '123456')

    def test_get_distance(self):
        locations = [[-23.6352, 110.3726], [53.0917, -172.3206], [-81.5872, 30.5518], [4.8300, 0.5632]]
        assert np.array_equal(self.root._get_distance(locations),
                              np.array([11288336.917793995, 7244072.094304907, 12238910.359436689, 16755498.409648465, 13539906.08749783, 9733685.182006456]))


class TestRoot(TestBase):
    """ Crunch Fitness functional tests """

    def _login(self):
        self.app.post('/login', {'username': 'admin@crunch.io', 'password': '123456'})

    def _logout(self):
        self.app.reset()

    def test_index(self):
        resp = self.app.get('/')
        assert resp.status_int == 200
        assert 'Welcome to Crunch.' in resp

    def test_index_bad_param(self):
        resp = self.app.get('/', {'test': 'test'}, status=404)

    def test_index_bad_method(self):
        resp = self.app.post('/', status=405)

    def test_unauthenticated_get_user_data(self):
        # CherryPy's default redirect sets a 302 response status for HTTP/1.0 (webtest) requests (303 for HTTP/1.1)
        resp = self.app.get('/users', status=302)
        assert '/login' in resp.headers['Location']

    def test_get_user_data(self):
        self._login()
        resp = self.app.get('/users', status=200)
        assert resp.headers['Content-Type'] == 'application/json'
        # Note that we are unable to "assert resp.headers['Content-Type'] == 'chunked'" since
        # chunked transfer encoding is only available in HTTP/1.1 (webtest uses HTTP/1.0)
        assert '58507677f6d459c8468d12a9' in resp
        assert 'Curtis.Russell@Zilidium.com' in resp
        self._logout()

    def test_unauthenticated_post_user_data(self):
        resp = self.app.get('/users', status=302)
        assert '/login' in resp.headers['Location']

    def test_missing_param_post_user_data(self):
        self._login()
        missing_required_param = VALID_REGISTER_USER_PARAMS.copy()
        missing_required_param.pop('first_name')
        resp = self.app.post('/users', missing_required_param, status=400)
        assert 'following user fields must be specified' in resp
        self._logout()

    def test_unexpected_param_post_user_data(self):
        self._login()
        unexpected_required_param = VALID_REGISTER_USER_PARAMS.copy()
        unexpected_required_param['unexpected'] = ''
        resp = self.app.post('/users', unexpected_required_param, status=400)
        assert 'Unexpected parameter' in resp
        self._logout()

    def test_invalid_param_post_user_data(self):
        self._login()
        invalid_required_param = VALID_REGISTER_USER_PARAMS.copy()
        invalid_required_param['latitude'] = 'abc'
        resp = self.app.post('/users', invalid_required_param, status=400)
        assert 'latitude' in resp
        self._logout()

    def test_existing_user_post_user_data(self):
        self._login()
        existing_user_param = VALID_REGISTER_USER_PARAMS.copy()
        existing_user_param['email'] = 'admin@crunch.io'
        resp = self.app.post('/users', existing_user_param, status=409)
        assert 'already exists' in resp
        self._logout()

    def test_post_user_data(self):
        self._login()
        new_user_email = 'new_user@domain.com'
        new_user_params = VALID_REGISTER_USER_PARAMS.copy()
        new_user_params['email'] = new_user_email
        new_user_params['password'] = 'abcd1234'
        resp = self.app.post('/users', new_user_params, status=201)
        resp = self.app.get('/users')
        assert '"email": "{}"'.format(new_user_email) in resp
        self._logout()

    def test_get_login_unauthenticated(self):
        resp = self.app.get('/login', status=200)
        assert 'Login' in resp

    def test_get_login_authenticated(self):
        self._login()
        resp = self.app.get('/login', status=200)
        assert 'logout' in resp
        self._logout()

    def test_post_login_missing_param(self):
        resp = self.app.post('/login', {'username': 'admin@crunch.io'}, status=400)

    def test_post_login_bad_creds(self):
        resp = self.app.post('/login', {'username': 'admin@crunch.io', 'password': 'abcdef'}, status=302)
        resp = resp.follow()
        assert 'Login' in resp
        self.app.get('/users', status=302)

    def test_post_login_valid_creds(self):
        resp = self.app.post('/login', {'username': 'admin@crunch.io', 'password': '123456'}, status=302)
        resp = resp.follow()
        assert 'Logout' in resp
        self.app.get('/users', status=200)
        self._logout()

    def test_logout_bad_method(self):
        self.app.get('/logout', status=405)

    def test_logout(self):
        resp = self.app.post('/login', {'username': 'admin@crunch.io', 'password': '123456'})
        session_cookie = resp.headers['Set-Cookie']
        resp = self.app.get('/distances')
        resp = self.app.get('/login')
        resp = self.app.get('/users')
        assert session_cookie == resp.headers['Set-Cookie']
        resp = self.app.post('/logout', status=302)
        assert session_cookie != resp.headers['Set-Cookie']

    def test_distances_bad_method(self):
        self.app.post('/distances', status=405)

    def test_distances(self):
        resp = self.app.get('/distances', status=200)
        distances = json.loads(resp.body)
        assert distances == {"standard deviation": 4741588.665776003, "max": 18260426.14597582, "mean": 10473652.01956172, "min": 0.0}
