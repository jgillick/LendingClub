#!/usr/bin/env python

import sys
import unittest
import getpass
from random import choice
from logger import TestLogger

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from lendingclub import LendingClub, Order
from lendingclub.filters import Filter

logger = TestLogger()
lc = LendingClub(logger=logger)


class LiveTests(unittest.TestCase):

    def setUp(self):
        # Clear any existing orders
        lc.session.clear_session_order()

        # Override Order.__place_order so that no orders can be made
        Order._Order__place_order = self.place_order_override

        # Make sure that the override worked
        o = Order(lc)
        self.assertEqual(o._Order__place_order('token'), 12345)

    def place_order_override(self, token):
        """
        This overrides the Order.__place_order method so that no
        actual order is ever made
        """
        assert token, 'The token is empty or does not exist'
        return 12345

    def tearDown(self):
        pass

    def test_is_site_available(self):
        self.assertTrue(lc.is_site_available())

    def test_get_balance(self):
        cash = lc.get_cash_balance()

        self.assertTrue(cash is not False)
        self.assertTrue(cash >= 25)

    def test_get_investable_balance(self):
        cash = lc.get_investable_balance()

        self.assertTrue(cash is not False)
        self.assertTrue(cash >= 25)
        self.assertTrue(cash % 25 == 0)

    def test_get_portfolio_list(self):
        porfolio_list = lc.get_portfolio_list()

        assert len(porfolio_list), 'You do not have any named portfolios in your account'

        first = porfolio_list[0]
        self.assertEqual(type(first), dict)
        self.assertTrue('portfolioName' in first)

    def test_search(self):
        loans = lc.search()
        self.assertTrue(len(loans) > 0)

    def test_search_with_filters(self):
        f = Filter({'grades': {'B': True}})
        results = lc.search(f)

        self.assertTrue(len(results['loans']) > 0)

        # Ensure all the notes are B grade
        for loan in results['loans']:
            self.assertEqual(loan['loanGrade'][0], 'B')

    def test_build_portfolio(self):
        f = Filter({'grades': {'B': True}})
        portfolio = lc.build_portfolio(25, 25, 9.0, 14.0, filters=f)

        self.assertEqual(len(portfolio['loan_fractions']), 1)
        self.assertEqual(portfolio['b'], 100)
        self.assertEqual(portfolio['number_of_b_loans'], 1)
        self.assertTrue(14.0 > portfolio['percentage'] > 9.0)

    def test_build_portfolio_invest(self):
        f = Filter({'grades': {'B': True}})
        portfolio = lc.build_portfolio(25, 25, 9.0, 14.0, filters=f, automatically_invest=True)

        self.assertEqual(len(portfolio['loan_fractions']), 1)
        self.assertEqual(portfolio['b'], 100)
        self.assertTrue('order_id' in portfolio)
        self.assertEqual(portfolio['order_id'], 12345)

        # Try to reinvest this same portfolio
        o = lc.start_order()
        self.assertRaises(
            AssertionError,
            lambda: o.add_batch(portfolio)
        )

    def test_my_notes(self):
        notes = lc.my_notes()
        self.assertTrue(len(notes) > 0)

    def test_get_note(self):
        notes = lc.my_notes()
        self.assertTrue(len(notes['loans']) > 0)

        note = choice(notes['loans'])  # Get random note

        found = lc.get_note(note['noteId'])
        self.assertEqual(note['noteId'], found['noteId'])

    def search_my_notes(self):
        # Find a note to use as something to search from
        notes = lc.my_notes()
        note = choice(notes['loans'])  # Get random note

        # Find by loan_id
        found = lc.search_my_notes(loan_id=note['loanId'])
        self.assertTrue(len(found) > 0)
        self.assertEqual(found[0]['loanId'], note['loanId'])

        # Find by order_id
        found = lc.search_my_notes(loan_id=note['orderId'])
        self.assertTrue(len(found) > 0)
        self.assertEqual(found[0]['orderId'], note['orderId'])

        # Find by Grade
        grade = note['rate'][0]
        found = lc.search_my_notes(grade=grade)
        self.assertTrue(len(found) > 0)
        for note in found:
            self.assertEqual(grade, note['rate'][0])


print """
!!!WARNING !!!
This is a live test of the module communicating with LendingClub.com with your account!!!
Your account must have at least $25 to continue. Tests will attempt to get full API test
coverage coming just short of investing money from your account.

However, this is not guaranteed if something in the tests are broken. Please continue at your own risk.
"""
res = raw_input('Continue with the tests? [yes/no]')
if res.lower() != 'yes':
    exit()

print '\n\nEnter a valid LendingClub account information...'
email = raw_input('Email:')
password = getpass.getpass()


assert lc.is_site_available(), 'No network connection or cannot access lendingclub.com'
assert lc.authenticate(email, password), 'Could not authenticate'
assert lc.get_investable_balance(), 'You do not have at least $25 in your account.'

if __name__ == '__main__':
    unittest.main()
