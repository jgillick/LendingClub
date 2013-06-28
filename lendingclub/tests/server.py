#!/usr/bin/env python

"""
A dummy web server used to test the LendingClub API requests
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

import os
import json
import urlparse
import cgi
import SocketServer
from threading import Thread
from BaseHTTPServer import BaseHTTPRequestHandler

logging = None
http_session = {}
session_disabled = False


class TestServerHandler(BaseHTTPRequestHandler):
    httpd = None
    query = None
    data = None

    headers_sent = False

    auth = {
        'email': 'test@test.com',
        'password': 'supersecret'
    }
    """
    Dummy authenticated email and password for this LendingClub server.
    Any other combination will fail on auth.
    """

    def log(self, msg):
        global logging

        msg = 'SERVER: {0}'.format(msg)
        if logging is not None:
            logging.debug(msg)
        else:
            print '{0}\n'.format(msg)

    def start(self):
        """
        Start the http server
        """
        self.log('Server started...')
        self.httpd.serve_forever()

    def stop(self):
        """
        Shutdown http server
        """
        self.httpd.shutdown()

    def send_headers(self, status_code=200, headers=None, content_type="text/plain"):
        """
        Send all the HTTP headers and prepare the response for content
        """
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)

        if type(headers) is dict:
            for key, value in headers.iteritems():
                self.send_header(key, value)

        # Debug by echoing the query and data base
        if self.query:
            self.send_header('x-echo-query', repr(self.query))
        if self.data:
            self.send_header('x-echo-data', repr(self.data))

        self.end_headers()
        self.headers_sent = True

    def read_asset_file(self, file_name):
        """
        Read a file from the assets directory
        """
        this_dir = os.path.dirname(os.path.realpath(__file__))
        asset_file = os.path.join(this_dir, 'assets', file_name)

        if not os.path.exists(asset_file):
            raise Exception('The asset file \'{0}\' does not exist in {1}'.format(file_name, this_dir))

        return open(asset_file).read()

    def write(self, output):
        """
        Write to the response stream and send default headers if they haven't been sent yet
        """
        if self.headers_sent is False:
            self.send_headers()
        self.wfile.write(output)

    def add_session(self, key, value):
        """
        Add a value to the HTTP session
        """
        global http_session
        if not session_disabled:
            http_session[key] = value

        print 'Add to session: {0}={1}'.format(key, value)

    def output_file(self, file_name):
        """
        Read a file from the assets directory and write it to response stream
        """
        self.write(self.read_asset_file(file_name))

    def output_error_json(self, message):
        """
        Output a JSON error message to the response stream
        """
        error = {
            'result': 'error',
            'error': [message]
        }
        self.write(json.dumps(error))

    def process_post_data(self):
        content_len = int(self.headers.getheader('content-length'))
        postvars = cgi.parse_qs(self.rfile.read(content_len))

        # Flatten values
        for key, values in postvars.iteritems():
            if len(values) == 1:
                postvars[key] = values[0]

        self.data = postvars

    def process_url(self):
        """
        Separate the path from the query
        """
        url = urlparse.urlparse(self.path)
        self.path = url.path
        self.query = urlparse.parse_qs(url.query)

        # Flatten query string values
        for key, values in self.query.iteritems():
            if len(values) == 1:
                self.query[key] = values[0]

    def do_GET(self):
        """
        Process at GET request
        """
        global http_session
        self.process_url()

        path = self.path
        query = self.query

        #self.log('GET {0} {1}'.format(path, query))

        # Summary page
        if '/account/summary.action' == path:
            return self.write('Summary Page')

        # Cash balance JSON
        elif '/browse/cashBalanceAj.action' == path:
            return self.output_file('cashBalanceAj.json')

        # Portfolio list
        elif '/data/portfolioManagement' == path:
            if 'method' in query:
                if query['method'] == 'getLCPortfolios':
                    return self.output_file('portfolioManagement_getLCPortfolios.json')
                else:
                    return self.write('Unknown method {0}'.format(query['method']))
            else:
                return self.write('No method provided')

        # Place order and strut token
        elif '/portfolio/placeOrder.action' == path:
            return self.output_file('placeOrder.html')

        # Select portfolio option and save to session
        elif '/portfolio/recommendPortfolio.action' == path:
            self.add_session('lending_match_point', query['lending_match_point'])
            self.send_headers(302, {'location': '/portfolio/autoInvest.action'})

        # Clear portfolio building session
        elif '/portfolio/confirmStartNewPortfolio.action' == path:
            if 'lending_match_point' in http_session:
                del http_session['lending_match_point']
            self.send_headers(302, {'location': '/portfolio/viewOrder.action'})

        # Get list of loan fractions (must have lending_match_point set in the session)
        elif '/data/portfolio' == path and 'getPortfolio' == query['method']:
            if 'lending_match_point' in http_session:
                self.output_file('portfolio_getPortfolio.json')
            else:
                print 'lending_match_point was not set'
                self.write('{"error": "The lending match point was not set"}')

        # Stage an order
        elif '/data/portfolio' == path and 'addToPortfolioNew' == query['method']:
            return self.output_file('portfolio_addToPortfolioNew.json')

        # Get a dump of the session
        elif '/session' == path:
            self.write(json.dumps(http_session))

        # Nothing here yet
        elif '/portfolio/autoInvest.action' == path:
            self.write('/portfolio/autoInvest.action')
        elif '/portfolio/viewOrder.action' == path:
            self.write('/portfolio/viewOrder.action')

        else:
            self.write('{"error": "Unknown path"}')

    def do_POST(self):
        """
        Process at POST request
        """
        global http_session, session_disabled
        #self.log('POST {0}'.format(self.path))
        self.process_url()
        self.process_post_data()

        path = self.path
        data = self.data
        query = self.query

        #self.log('Post Data {0}'.format(self.data))

        # Login - if the email and password match, set the cookie
        if '/account/login.action' == path:
            if data['login_email'] == self.auth['email'] and data['login_password'] == self.auth['password']:
                self.send_headers(302, {
                    'Set-Cookie': 'LC_FIRSTNAME=John',
                    'Content-Type': 'text/plain',
                    'location': '/account/summary.action'
                })
                return
            else:
                return self.output_file('login_fail.html')

        # Investment option search
        elif '/portfolio/lendingMatchOptionsV2.action' == path:

            # Default filters
            if data['filter'] == 'default':
                return self.output_file('lendingMatchOptionsV2.json')

            # Custom filters
            else:
                return self.output_file('lendingMatchOptionsV2_filter.json')

        # Order confirmation
        elif '/portfolio/orderConfirmed.action' == path:
            if 'struts.token' in data and data['struts.token'].strip() != '':
                return self.output_file('orderConfirmed.html')
            else:
                print "No struts token passed"
                self.write('{"error": "No struts token passed"}')

        # Assign to portfolio
        elif '/data/portfolioManagement' == path:

            if 'method' in query:
                # Existing portfolio
                if 'addToLCPortfolio' == query['method']:
                    http_session['existing_portfolio'] = query['lcportfolio_name']
                    self.output_file('portfolioManagement_addToLCPortfolio.json')

                # New portfolio
                elif 'createLCPortfolio' == query['method']:
                    http_session['new_portfolio'] = query['lcportfolio_name']
                    self.output_file('portfolioManagement_createLCPortfolio.json')

                else:
                    return self.write('Unknown method: {0}'.format(query.method))
            else:
                self.write('{"error": "No method passed"}')

        # Select a loan note
        elif '/browse/updateLSRAj.action' == path:
            return self.output_file('updateLSRAj.json')

        # Disable the session
        elif '/session/disabled' == path:
            session_disabled = True
            http_session = {}
            self.write('Session disabled')

        # Enable the session
        elif '/session/enabled' == path:
            session_disabled = False
            self.write('Session enabled')

        # Add the post data to the session
        elif '/session' == path:
            if session_disabled is True:
                self.write('{"error": "Session disabled"}')
            else:
                for key, values in data.iteritems():
                    self.add_session(key, value)
                self.send_headers(302, {'location': '/session'})

        else:
            self.write('{"error": "Unknown path"}')

    def do_HEAD(self):
        """
        Process at HEAD request
        """
        return self.do_GET()

    def do_DELETE(self):
        """
        Process at DELETE request
        """
        global http_session

        # Delete the session
        if '/session' == self.path:
            http_session = {}
            return self.write(json.dumps(http_session))

        else:
            self.send_headers(500)
            self.write('Unknown delete action: {0}'.format(self.path))


class ReusableServer(SocketServer.TCPServer):
    allow_reuse_address = True


class TestWebServer:
    """
    Simple class to start/stop the server
    """
    http = None

    def __init__(self):
        #self.http = HTTPServer(('127.0.0.1', 7357), TestServerHandler)
        pass

    def start(self):
        print 'Starting server at 127.0.0.1:8000'
        self.http = ReusableServer(('127.0.0.1', 8000), TestServerHandler)
        self.http.serve_forever()

    def stop(self):
        print 'Stopping server...'
        self.http.shutdown()
        self.http = None


class ServerThread:
    """
    Start the server in it's own thread
    """

    httpd = None
    thread = None

    def __init__(self):
        self.httpd = TestWebServer()
        self.thread = Thread(target=self.httpd.start)
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        print 'Server thread started'

    def stop(self):
        self.httpd.stop()


#
# When called from the command line
#
if __name__ == '__main__':
    server = TestWebServer()

    try:
        server.start()
    except KeyboardInterrupt:
        print '\nShutting down the test server'
        server.stop()
