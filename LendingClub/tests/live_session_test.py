#!/usr/bin/env python

import sys
import unittest
import getpass
from logger import TestLogger

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from lendingclub import session


class LiveTestSession(unittest.TestCase):
    http = None
    session = None
    logger = None

    def setUp(self):
        self.logger = TestLogger()
        self.session = session.Session(logger=self.logger)

    def tearDown(self):
        pass

    def test_login(self):
        """ test_valid_login
        Test login with credentials from the user
        """

        print '\n\nEnter a valid LendingClub account information...'
        email = raw_input('Email:')
        password = getpass.getpass()

        self.assertTrue(self.session.authenticate(email, password))
        print 'Authentication successful'

    def test_invalid_login(self):
        """ test_invalid_password
        Test login with the wrong password
        """
        self.assertRaises(
            session.AuthenticationError,
            lambda: self.session.authenticate('test@test.com', 'wrongsecret')
        )


if __name__ == '__main__':
    unittest.main()
