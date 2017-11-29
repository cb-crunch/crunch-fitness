Welcome to the Crunch.io api fitness test.

Here you will find a python package to help us evaluate your skills with:

1. Problem Solving
2. Web Server API Design
3. Request-time data manipulation
4. Testing strategies

Instructions

1. Fork the repo into a private repo.
2. Create a virtualenv for this project and install the cr-api and cr-db packages into your environment.
3. Modify the cr-api package to complete the task, the code is commented with task items.
4. Let us know when you have finished.

Deliverable

Publish your work in a GitHub repository.  Please use Python 2.x for your coding.  Feel free to modify this
readme to give any additional information a reviewer might need.

Assumptions

The '_get_distance' method uses the Haversine formula (see http://www.movable-type.co.uk/scripts/latlong.html)
to calculate the distance between two points. This formula assumes that the earth is a perfect sphere. By using
this method we assume that the Haversine formula's margin of error is acceptable for our purposes. We could
significantly reduce the margin of error in '_get_distance', at the cost of performance, by utilizing a formula
that assumes the more accurate "oblate spheroid" model for the shape of the earth (see
https://www.johndcook.com/blog/2009/03/02/what-is-the-shape-of-the-earth/).

The 'distances' route assumes that the number of user locations is not very large. '_get_distance' will raise
a MemoryError when calculating pairwise-distinct distances for a large number of user locations, depending on
available system memory. For example, '_get_distance' raises a MemoryError when attempting to calculate
pairwise-distinct distances for about 6000 locations on a test system with 8GB RAM. One approach to handling a
large number of user locations is outlined in the "Implementation Details" section below.

All routes are intended to handle "normal" browser requests rather than AJAX or other web API client requests.
We would need to change the response properties of some routes to respond to web API client requests and AJAX
requests. For example, the 'users' route would return a 401 response status code when accessed by an unauthenticated
user via a web API client, rather than its current 303 (302 for HTTP/1.0 requests) response status code.

The 'distances' route does not require authentication. This assumption is based on a) lack of authentication
requirements in the exercise description, and b) this route provides only aggregate, anonymous data whose
proprietary value is assumed to be low.

Even though the majority of users stored in the database (users.json) do not have a password associated with their
accounts, we assume that only users with passwords are allowed to authenticate. This higher threshold of authentication
is justified in part by the personally identifiable information provided by the 'users' route.

The following user fields must be provided when registering a new user: 'longitude', 'latitude', 'email', 'company',
'lastName', and 'firstName'. All registered users have valid values for these fields. A registered user is
uniquely identified by his email address.

Users loaded at the start of a test run are mock users, so that hard-coding a username/password in the test
script is not a security concern.

The site will be served over HTTPS to prevent login credentials and cookies from being compromised.

The 'login' page should display a link to the 'logout' route if the user is already logged in.

Default session settings are sufficient for this exercise.

Implementation Details

To scale the 'distance' method to 1,000,000 users who change position every few minutes, we could maintain
running stats that are updated for each change (see eg: https://www.johndcook.com/blog/standard_deviation/).
This is significantly less computationally intensive than recalculating distances between all users for each
location change. Values representing a user location change, either a new user or a user changing location, may be
published to a queue and consumed by one or more (see eg: https://www.johndcook.com/blog/skewness_kurtosis/) stat
recalculation service instances.

I moved the call to 'load_data' in 'tests/base.py' from the 'app' function to the 'setup' function. This was
necessary in order to ensure a standard starting data set for all tests. 'app' is called once per test suite,
so a fresh set of data is loaded only once per test run if 'load_data' is called from 'app'. A test that adds a
new user would break a test that verifies the 'distances' route if it is called prior, since it will add
unexpected user locations to the database shared by all tests. By moving 'load_data' to 'setup', which is called
once per test, we ensure that each test starts with the same data.

The regex defined in the W3C HTML5 spec (https://www.w3.org/TR/html5/forms.html#valid-e-mail-address) is used to
validate an email address when registering a user.

I chose to redirect the user to the 'login' page (303 HTTP/1.1 response status, 302 for HTTP/1.0), instead of
responding with a 401 status, when an unauthenticated user attempts to access the protected 'users' resource,
since this seems to be the more user-friendly approach and appears to be the established best practice (see
https://stackoverflow.com/a/41837734). This functionality could be extended by further redirecting such a user
to the 'users' route following successful authentication.

User objects are returned from the 'users' GET route by returning a generator that yields each user record, rather
than directly yielding each user record. When yielding response objects directly, CherryPy sets the 'Content-Type'
to 'text/html'; the content type cannot be modified by the page handler. In order to set the content type to
'application/json', the page handler must return a generator that yields the user records. See
http://docs.cherrypy.org/en/latest/advanced.html#how-streaming-output-works-with-cherrypy.
