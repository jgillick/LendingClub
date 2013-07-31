#!/usr/bin/env python

"""
Manage the LendingClub user session and all raw HTTP calls to the LendingClub site.
This will almost always be accessed through the API calls in
:class:`lendingclub.LendingClub` instead of directly.
"""

"""
The MIT License (MIT)

Copyright (c) 2013 Jeremy Gillick

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import re
import requests
import getpass
import time as time
from bs4 import BeautifulSoup
from requests.exceptions import *


class Session:

    email = None
    __pass = None
    __logger = None

    last_response = None

    session_timeout = 10
    """ Minutes until the session expires.
    The session will attempt to reauth before the next HTTP call after timeout."""

    base_url = 'https://www.lendingclub.com/'
    """ The root URL that all paths are appended to """

    last_request_time = 0
    """ The timestamp of the last HTTP request """

    __session = None

    def __init__(self, email=None, password=None, logger=None):
        self.email = email
        self.__pass = password
        self.__logger = logger

    def __log(self, message):
        """
        Log a debugging message
        """
        if self.__logger:
            self.__logger.debug(message)

    def __continue_session(self):
        """
        Check if the time since the last HTTP request is under the
        session timeout limit. If it's been too long since the last request
        attempt to authenticate again.
        """
        now = time.time()
        diff = abs(now - self.last_request_time)
        timeout_sec = self.session_timeout * 60  # convert minutes to seconds

        if diff >= timeout_sec:
            self.__log('Session timed out, attempting to authenticate')
            self.authenticate()

    def set_logger(self, logger):
        """
        Have the Session class send debug logging to your python logging logger.
        Set to None stop the logging.

        Parameters
        ----------
        logger : `Logger <http://docs.python.org/2/library/logging.html>`_
            The logger to send debug output to.
        """
        self.__logger = logger

    def build_url(self, path):
        """
        Build a LendingClub URL from a URL path (without the domain).

        Parameters
        ----------
        path : string
            The path part of the URL after the domain. i.e. https://www.lendingclub.com/<path>
        """
        url = '{0}{1}'.format(self.base_url, path)
        url = re.sub('([^:])//', '\\1/', url)  # Remove double slashes
        return url

    def authenticate(self, email=None, password=None):
        """
        Authenticate with LendingClub and preserve the user session for future requests.
        This will raise an exception if the login appears to have failed, otherwise it returns True.

        Since Lending Club doesn't seem to have a login API, the code has to try to decide if the login
        worked or not by looking at the URL redirect and parsing the returned HTML for errors.

        Parameters
        ----------
        email : string
            The email of a user on Lending Club
        password : string
            The user's password, for authentication.

        Returns
        -------
        boolean
            True on success or throws an exception on failure.

        Raises
        ------
        session.AuthenticationError
            If authentication failed
        session.NetworkError
            If a network error occurred
        """

        # Get email and password
        if email is None:
            email = self.email
        else:
            self.email = email

        if password is None:
            password = self.__pass
        else:
            self.__pass = password

        # Get them from the user
        if email is None:
            email = raw_input('Email:')
            self.email = email
        if password is None:
            password = getpass.getpass()
            self.__pass = password

        self.__log('Attempting to authenticate: {0}'.format(self.email))

        # Start session
        self.__session = requests.Session()
        self.__session.headers = {
            'Referer': 'https://www.lendingclub.com/',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/26.0.1410.65 Safari/537.31'
        }

        # Set last request time to now
        self.last_request_time = time.time()

        # Send login request to LC
        payload = {
            'login_email': email,
            'login_password': password
        }
        response = self.post('/account/login.action', data=payload, redirects=False)

        # Get URL redirect URL and save the last part of the path as the endpoint
        response_url = response.url
        if response.status_code == 302:
            response_url = response.headers['location']
        endpoint = response_url.split('/')[-1]

        # Debugging
        self.__log('Status code: {0}'.format(response.status_code))
        self.__log('Redirected to: {0}'.format(response_url))
        self.__log('Cookies: {0}'.format(str(response.cookies.keys())))

        # Show query and data that the server received
        if 'x-echo-query' in response.headers:
            self.__log('Query: {0}'.format(response.headers['x-echo-query']))
        if 'x-echo-data' in response.headers:
            self.__log('Data: {0}'.format(response.headers['x-echo-data']))

        # Parse any errors from the HTML
        soup = BeautifulSoup(response.text, "html5lib")
        errors = soup.find(id='master_error-list')
        if errors:
            errors = errors.text.strip()

            # Remove extra spaces and newlines from error message
            errors = re.sub('\t+', '', errors)
            errors = re.sub('\s*\n+\s*', ' * ', errors)

            if errors == '':
                errors = None

        # Raise error
        if errors is not None:
            raise AuthenticationError(errors)

        # Redirected back to the login page...must be an error
        if endpoint == 'login.action':
            raise AuthenticationError('Unknown! Redirected back to the login page without an error message')

        return True

    def is_site_available(self):
        """
        Returns true if we can access LendingClub.com
        This is also a simple test to see if there's a network connection

        Returns
        -------
        boolean
            True or False
        """
        try:
            response = requests.head(self.base_url)
            status = response.status_code
            return 200 <= status < 400  # Returns true if the status code is greater than 200 and less than 400
        except Exception:
            return False

    def request(self, method, path, query=None, data=None, redirects=False):
        """
        Sends HTTP request to LendingClub.

        Parameters
        ----------
        method : {GET, POST, HEAD, DELETE}
            The HTTP method to use: GET, POST, HEAD or DELETE
        path : string
            The path that will be appended to the domain defined in :attr:`base_url`.
        query : dict
            A dictionary of query string parameters
        data : dict
            A dictionary of POST data values
        redirects : boolean
            True to follow redirects, False to return the original response from the server.

        Returns
        -------
        requests.Response
            A `requests.Response <http://docs.python-requests.org/en/latest/api/#requests.Response>`_ object
        """

        # Check session time
        self.__continue_session()

        try:
            url = self.build_url(path)
            method = method.upper()

            self.__log('{0} request to: {1}'.format(method, url))

            if method == 'POST':
                request = self.__session.post(url, params=query, data=data, allow_redirects=redirects)
            elif method == 'GET':
                request = self.__session.get(url, params=query, data=data, allow_redirects=redirects)
            elif method == 'HEAD':
                request = self.__session.head(url, params=query, data=data, allow_redirects=redirects)
            elif method == 'DELETE':
                request = self.__session.delete(url, params=query, data=data, allow_redirects=redirects)
            else:
                raise SessionError('{0} is not a supported HTTP method'.format(method))

            self.last_response = request

            # Update session time
            self.last_request_time = time.time()

        except (RequestException, ConnectionError, TooManyRedirects, HTTPError) as e:
            raise NetworkError('{0} failed to: {1}'.format(method, url), e)
        except Timeout:
            raise NetworkError('{0} request timed out: {1}'.format(method, url), e)

        return request

    def post(self, path, query=None, data=None, redirects=False):
        """
        POST request wrapper for :func:`request()`
        """
        return self.request('POST', path, query, data, redirects)

    def get(self, path, query=None, redirects=False):
        """
        GET request wrapper for :func:`request()`
        """
        return self.request('GET', path, query, None, redirects)

    def head(self, path, query=None, data=None, redirects=False):
        """
        HEAD request wrapper for :func:`request()`
        """
        return self.request('HEAD', path, query, None, redirects)

    def clear_session_order(self):
        """
        Clears any existing order in the LendingClub.com user session.
        """
        self.get('/portfolio/confirmStartNewPortfolio.action')

    def json_success(self, json):
        """
        Check the JSON response object for the success flag

        Parameters
        ----------
        json : dict
            A dictionary representing a JSON object from lendingclub.com
        """
        if type(json) is dict and 'result' in json and json['result'] == 'success':
            return True
        return False


class SessionError(Exception):
    """
    Base exception class for :mod:`lendingclub.session`

    Parameters
    ----------
    value : string
        The error message
    origin : Exception
        The original exception, if this exception was caused by another.
    """
    value = 'Unknown error'
    origin = None

    def __init__(self, value, origin=None):
        self.value = value
        self.origin = origin

    def __str__(self):
        if self.origin is None:
            return repr(self.value)
        else:
            return '{0} (from {1})'.format(repr(self.value), repr(self.origin))


class AuthenticationError(SessionError):
    """
    Authentication failed
    """
    pass


class NetworkError(SessionError):
    """
    An error occurred while making an HTTP request
    """
    pass
