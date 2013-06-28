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

        # Make sure session is enabled and clear
        self.lc.session.post('/session/enabled')
        self.lc.session.request('delete', '/session')

    def tearDown(self):
        pass

    def test_cash_balance(self):
        cash = self.lc.get_cash_balance()
        self.assertEqual(cash, 216.02)

    def test_portfolios(self):
        portfolios = self.lc.get_portfolio_list()
        self.assertEquals(len(portfolios), 2)
        self.assertEquals(portfolios[0]['portfolioName'], 'Existing Portfolio')

    def test_build_portfolio(self):
        portfolio = self.lc.build_portfolio(200, 15, 16)

        self.assertNotEqual(portfolio, False)
        self.assertEqual(portfolio['percentage'], 15.28)

        self.assertTrue('loan_fractions' in portfolio)
        self.assertEqual(len(portfolio['loan_fractions']), 15)

    def test_build_portfolio_session_fail(self):
        """ test_build_portfolio_session_fail"
        If the session isn't saved, fractions shouldn't be found,
        which should make the entire method return False
        """

        # Disable session
        self.lc.session.post('/session/disabled')

        portfolio = self.lc.build_portfolio(200, 15, 16)
        self.assertFalse(portfolio)

    def test_build_portfolio_no_match(self):
        """ test_build_portfolio_no_match"
        Enter a min/max percent that cannot match dummy returned JSON
        """
        portfolio = self.lc.build_portfolio(200, 17.6, 18.5)
        self.assertFalse(portfolio)

    def test_search(self):
        results = self.lc.search()
        self.assertTrue(results is not False)
        self.assertTrue('loans' in results)
        self.assertTrue(len(results['loans']) > 0)


if __name__ == '__main__':
    # Start the web-server in a background thread
    http = ServerThread()
    http.start()

    # Run tests
    unittest.main()

    # Stop threads
    http.stop()