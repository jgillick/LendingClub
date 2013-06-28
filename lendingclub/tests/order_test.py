#!/usr/bin/env python

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
                'loanFractionAmount': 50
            }, {
                'loan_id': 234,
                'loanFractionAmount': 75
            }
        ])

        self.assertEqual(len(self.order.loans), 2)
        self.assertEqual(self.order.loans[123], 50)
        self.assertEqual(self.order.loans[234], 75)

    def test_add_batch_object(self):
        """ test_add_batch_object
        If you send an object to add_batch, the loan notes must be on the loan_fractions key
        """
        self.order.add_batch({
            'loan_fractions': [
                {
                    'loan_id': 123,
                    'loanFractionAmount': 50
                }, {
                    'loan_id': 234,
                    'loanFractionAmount': 75
                }
            ]
        })

        self.assertEqual(len(self.order.loans), 2)
        self.assertEqual(self.order.loans[123], 50)
        self.assertEqual(self.order.loans[234], 75)


if __name__ == '__main__':
    # Start the web-server in a background thread
    http = ServerThread()
    http.start()

    # Run tests
    unittest.main()

    # Stop threads
    http.stop()