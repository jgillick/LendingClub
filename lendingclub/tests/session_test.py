#!/usr/bin/env python

import sys
import os
import unittest
import subprocess
from logger import TestLogger
from server import ServerThread

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from LendingClub import session


class TestSession(unittest.TestCase):
    session = None
    logger = None

    def setUp(self):
        self.logger = TestLogger()
        self.session = session.Session(logger=self.logger)
        self.session.base_url = 'http://127.0.0.1:8000/'

    def tearDown(self):
        pass

    def test_valid_login(self):
        """ test_valid_login
        Test login with valid credentials
        """
        self.assertTrue(self.session.authenticate('test@test.com', 'supersecret'))

    def test_invalid_password(self):
        """ test_invalid_password
        Test login with the wrong password
        """
        self.assertRaises(
            session.AuthenticationError,
            lambda: self.session.authenticate('test@test.com', 'wrongsecret')
        )

    def test_invalid_email(self):
        """ test_invalid_email
        Test login with wrong email
        """
        self.assertRaises(
            session.AuthenticationError,
            lambda: self.session.authenticate('wrong@test.com', 'supersecret')
        )


if __name__ == '__main__':
    # Start the web-server in a background thread
    http = ServerThread()
    http.start()

    # Run tests
    unittest.main()

    # Stop threads
    http.stop()
