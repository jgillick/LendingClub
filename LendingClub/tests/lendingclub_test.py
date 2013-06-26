#!/usr/bin/env python

import sys
import unittest
from logger import TestLogger
from server import ServerThread

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from lendingclub import LendingClub


class TestLendingClub(unittest.TestCase):
    lc = None
    logger = None

    def setUp(self):
        self.logger = TestLogger()
        self.lc = LendingClub(logger=self.logger)

        self.lc.session.base_url = 'http://127.0.0.1:8000/'
        self.lc.session.set_logger(None)

        self.lc.authenticate('test@test.com', 'supersecret')

    def tearDown(self):
        pass

    def test_cash_balance(self):
        cash = self.lc.get_cash_balance()
        self.assertEqual(cash, 216.02)

    def test_portfolios(self):
        portfolios = self.lc.get_portfolio_list()
        self.assertEquals(len(portfolios), 2)
        self.assertEquals(portfolios[0]['portfolioName'], 'Existing Portfolio')


if __name__ == '__main__':
    # Start the web-server in a background thread
    http = ServerThread()
    http.start()

    # Run tests
    unittest.main()

    # Stop threads
    http.stop()