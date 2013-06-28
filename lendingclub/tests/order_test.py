#!/usr/bin/env python

import json
import sys
import unittest
from logger import TestLogger
from server import ServerThread

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from lendingclub import LendingClub, Order


class TestLendingClub(unittest.TestCase):
    lc = None
    order = None
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

        # Start order
        self.order = self.lc.start_order()

    def tearDown(self):
        pass

    def test_add(self):
        self.order.add(123, 50)
        self.assertEqual(len(self.order.loans), 1)
        self.assertEqual(self.order.loans[123], 50)

    def test_update(self):
        self.order.add(123, 50)
        self.assertEqual(self.order.loans[123], 50)

        self.order.add(123, 100)
        self.assertEqual(len(self.order.loans), 1)
        self.assertEqual(self.order.loans[123], 100)

    def test_remove(self):
        self.order.add(123, 50)
        self.order.add(234, 75)

        self.assertEqual(len(self.order.loans), 2)

        self.order.remove(234)

        self.assertEqual(len(self.order.loans), 1)
        self.assertEqual(self.order.loans[123], 50)
        self.assertFalse(234 in self.order.loans)

    def test_multiple_of_25(self):
        self.assertRaises(
            AssertionError,
            lambda: self.order.add(123, 0)
        )
        self.assertRaises(
            AssertionError,
            lambda: self.order.add(123, 26)
        )

    def test_add_batch(self):
        self.order.add_batch([
            {
                'loan_id': 123,
                'invest_amount': 50
            }, {
                'loan_id': 234,
                'invest_amount': 75
            }
        ])

        self.assertEqual(len(self.order.loans), 2)
        self.assertEqual(self.order.loans[123], 50)
        self.assertEqual(self.order.loans[234], 75)

    def test_add_batch_amount(self):
        """ test_add_batch_amount
        Add a batch with a batch_amount parameter value to override the individual values
        """
        self.order.add_batch([
            {
                'loan_id': 123,
                'invest_amount': 50
            }, {
                'loan_id': 234,
                'invest_amount': 75
            }
        ], 100)

        self.assertEqual(len(self.order.loans), 2)
        self.assertEqual(self.order.loans[123], 100)
        self.assertEqual(self.order.loans[234], 100)

    def test_add_batch_object(self):
        """ test_add_batch_object
        If you send an object to add_batch, the loan notes must be on the loan_fractions key
        """
        self.order.add_batch({
            'loan_fractions': [
                {
                    'loan_id': 123,
                    'invest_amount': 50
                }, {
                    'loan_id': 234,
                    'invest_amount': 75
                }
            ]
        })

        self.assertEqual(len(self.order.loans), 2)
        self.assertEqual(self.order.loans[123], 50)
        self.assertEqual(self.order.loans[234], 75)

    def test_execute(self):
        self.order.add_batch([
            {
                'loan_id': 123,
                'invest_amount': 50
            }, {
                'loan_id': 234,
                'invest_amount': 75
            }
        ])

        order_id = self.order.execute()
        self.assertNotEqual(order_id, 0)

    def test_execute_existing_portfolio(self):
        self.order.add_batch([
            {
                'loan_id': 123,
                'invest_amount': 50
            }, {
                'loan_id': 234,
                'invest_amount': 75
            }
        ])

        portfolio = 'New Portfolio'
        order_id = self.order.execute(portfolio)
        self.assertNotEqual(order_id, 0)

        # Check portfolio name
        request = self.lc.session.get('/session')
        http_session = request.json()
        self.assertEqual(http_session['new_portfolio'], portfolio)

    def test_execute_new_portfolio(self):
        self.order.add_batch([
            {
                'loan_id': 123,
                'invest_amount': 50
            }, {
                'loan_id': 234,
                'invest_amount': 75
            }
        ])

        portfolio = 'Existing Portfolio'
        order_id = self.order.execute(portfolio)
        self.assertNotEqual(order_id, 0)

        # Check portfolio name
        request = self.lc.session.get('/session')
        http_session = request.json()
        self.assertEqual(http_session['existing_portfolio'], portfolio)

    def test_double_execute(self):
        """ test_double_execute
        An order can only be executed once
        """
        self.order.add_batch([
            {
                'loan_id': 123,
                'invest_amount': 50
            }, {
                'loan_id': 234,
                'invest_amount': 75
            }
        ])

        order_id = self.order.execute()
        self.assertNotEqual(order_id, 0)

        self.assertRaises(
            AssertionError,
            lambda: self.order.execute()
        )


if __name__ == '__main__':
    # Start the web-server in a background thread
    http = ServerThread()
    http.start()

    # Run tests
    unittest.main()

    # Stop threads
    http.stop()