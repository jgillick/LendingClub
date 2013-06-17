#!/usr/bin/env python

#
# Utilities used by the LendingClubInvestor
#

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
import logging
import requests
from bs4 import BeautifulSoup
from requests.exceptions import *

baseUrl = 'https://www.lendingclub.com/'
logger = None

session = requests.Session()
cookies = {}
requestHeaders = {
    'Referer': 'https://www.lendingclub.com/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/26.0.1410.65 Safari/537.31'
}


def set_logger(verbose=False):
    """
    Initialize a logger for the autoinvestor
    """
    global logger

    if logger is None:
        logger = logging.getLogger('investor')
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        logHandler = logging.StreamHandler()
        if verbose:
            logHandler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s #%(lineno)d - %(message)s', '%Y-%m-%d %H:%M'))
        else:
            logHandler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s - %(message)s', '%Y-%m-%d %H:%M'))

        logger.addHandler(logHandler)

    return logger


def is_site_available():
    """
    Returns true if we can access LendingClub.com
    This is also a simple test to see if there's an internet connection
    """
    try:
        response = requests.head(baseUrl, headers=requestHeaders)
        status = response.status_code
        return 200 <= status < 400
    except Exception:
        return False


def start_session(email, password):
    """
    Login user to LendingClub and preserve the user session for future requests
    This will raise an exception if the login appears to have failed.

    The problem is that LendingClub doesn't seem to have a login API that we can access directly,
    so the code has to try to decide if the login worked or not.
    """
    global session

    try:
        session = requests.Session()
        session.headers = requestHeaders

        url = '{0}{1}'.format(baseUrl, '/account/login.action')
        url = re.sub('([^:])//', '\\1/', url)  # Remove double slashes
        payload = {
            'login_email': email,
            'login_password': password
        }
        response = session.post(url, data=payload, allow_redirects=False)

        # Get URL endpoint
        responseUrl = response.url
        if response.status_code == 302:
            responseUrl = response.headers['location']
        endpoint = responseUrl.split('/')[-1]

        # Debugging
        logger.debug('Status code: {0}'.format(response.status_code))
        logger.debug('Redirected to: {0}'.format(responseUrl))
        logger.debug('Cookies: {0}'.format(str(response.cookies.keys())))

        # Parse any errors
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
            raise Exception(errors)

        # Redirected back to the login page...must be an error
        if endpoint == 'login.action':
            raise Exception('An unknown error occurred')

    except (RequestException, ConnectionError, TooManyRedirects, HTTPError) as e:
        raise Exception('Could not get login from: {0}\n{1}'.format(url, str(e)))
    except Timeout:
        raise Exception('Timed out trying login using: {0}'.format(url))

    return True


def post_url(relUrl, params={}, data={}, useCookies=True):
    """
    Sends POST request to the relative URL of www.lendingclub.com
    """
    global cookies, session

    url = '{0}{1}'.format(baseUrl, relUrl)
    try:
        url = re.sub('([^:])//', '\\1/', url)  # Remove double slashes
        cookies = cookies if useCookies else {}

        logger.debug('POSTING {0}'.format(url))
        req = session.post(url, params=params, data=data, cookies=cookies)
        return req

    except (RequestException, ConnectionError, TooManyRedirects, HTTPError) as e:
        raise Exception('Could not post to: {0}\n{1}'.format(url, str(e)))
    except Timeout:
        raise Exception('Timed out trying to post to: {0}'.format(url))

    return False


def get_url(relUrl, params={}, useCookies=True):
    """
    Sends GET request to the relative URL of www.lendingclub.com
    """
    global cookies, session

    url = '{0}{1}'.format(baseUrl, relUrl)
    try:
        url = re.sub('([^:])//', '\\1/', url)  # Remove double slashes
        cookies = cookies if useCookies else {}

        logger.debug('GETTING {0}'.format(url))
        req = session.get(url, params=params, cookies=cookies)
        return req

    except (RequestException, ConnectionError, TooManyRedirects, HTTPError) as e:
        raise Exception('Could not get URL "{0}" with {1}\n{2}'.format(url, str(params), str(e)))
    except Timeout:
        raise Exception('Timed out trying to get URL "{0}" with {1}'.format(url, str(params)))

    return False


