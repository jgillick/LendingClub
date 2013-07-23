#!/usr/bin/env python

import re
import sys
import json as pyjson
import unittest
from logger import TestLogger
from server import ServerThread

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from lendingclub import LendingClub
from lendingclub.filters import *


def matches(regex, subject):
    """
    Returns True if the regex string matches the subject
    """
    return re.match(regex, subject) is not None


class TestFilters(unittest.TestCase):
    filters = None

    def setUp(self):
        self.filters = Filter()

    def tearDown(self):
        pass

    def get_values(self, m_id):
        """
        Get the m_values array from the filter JSON for this m_id
        """
        search_json = self.filters.search_string()
        json = pyjson.loads(search_json)
        for filterObj in json:
            if filterObj['m_id'] == m_id:
                return filterObj['m_value']

    def test_term_all(self):
        """ test_term_all
        Test the default state, having 36 and 60 month terms
        """
        values = self.get_values(39)

        self.assertEqual(len(values), 2)
        self.assertEqual(values[0]['value'], 'Year3')
        self.assertEqual(values[1]['value'], 'Year5')

    def test_term_36(self):
        """ test_term_36
        36 month term only
        """
        self.filters['term']['Year3'] = True
        self.filters['term']['Year5'] = False
        values = self.get_values(39)

        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['value'], 'Year3')

    def test_term_60(self):
        """ test_term_60
        60 month term only
        """
        self.filters['term']['Year3'] = False
        self.filters['term']['Year5'] = True
        values = self.get_values(39)

        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['value'], 'Year5')

    def test_exclude_existing(self):
        self.filters['exclude_existing'] = True
        values = self.get_values(38)

        self.assertEqual(len(values), 1)

    def test_include_existing(self):
        self.filters['exclude_existing'] = False
        values = self.get_values(38)

        self.assertEqual(values, None)

    def test_default_funding_progress(self):
        values = self.get_values(15)
        self.assertEqual(values, None)

    def test_funding_progress_rounding(self):
        """ test_funding_progress_rounding
        Funding progress should be rounded to the nearest 10
        """
        self.filters['funding_progress'] = 56
        values = self.get_values(15)
        self.assertEqual(values[0]['value'], 60)

    def test_funding_progress_set(self):
        """ test_funding_progress_round_up
        Funding progress set to 90
        """
        self.filters['funding_progress'] = 90
        values = self.get_values(15)
        self.assertEqual(values[0]['value'], 90)

    def test_funding_progress_round_up(self):
        """ test_funding_progress_round_up
        Test the progress rounding. It should round to the nearest 10
        """
        self.filters['funding_progress'] = 67
        values = self.get_values(15)
        self.assertEqual(values[0]['value'], 70)

    def test_funding_progress_round_down(self):
        """ test_funding_progress_round_down
        Test the progress rounding. It should round to the nearest 10
        """
        self.filters['funding_progress'] = 63
        values = self.get_values(15)
        self.assertEqual(values[0]['value'], 60)

    def test_grades(self):
        """ test_grade
        Test setting grades to 'B'
        """
        self.filters['grades']['All'] = False
        self.filters['grades']['B'] = True
        values = self.get_values(10)

        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['value'], 'B')

    def test_grades_all(self):
        """ test_grades_all
        All should be set to False if another grade is set to True
        """
        self.filters['grades']['C'] = True

        values = self.get_values(10)

        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['value'], 'C')


class TestFilterValidation(unittest.TestCase):
    filters = None
    logger = None
    lc = None
    loan_list = None

    def setUp(self):
        self.filters = Filter()
        self.filters['exclude_existing'] = False
        self.logger = TestLogger()

        self.lc = LendingClub(logger=self.logger)
        self.lc.session.base_url = 'http://127.0.0.1:8000/'
        self.lc.session.set_logger(None)
        self.lc.authenticate('test@test.com', 'supersecret')

        response = self.lc.session.get('/filter_validation', query={'id': 1})
        json_response = response.json()
        self.loan_list = json_response['loanFractions']

    def tearDown(self):
        pass

    def test_validation_defaults(self):
        """ test_validation_defaults
        Default filters should match
        """
        self.assertTrue(self.filters.validate(self.loan_list))

    def test_validation_grade_valid(self):
        self.filters['C'] = True
        self.assertTrue(self.filters.validate(self.loan_list))

    def test_validation_grade_fail(self):
        self.filters['grades']['B'] = True
        self.assertRaises(
            FilterValidationError,
            lambda: self.filters.validate(self.loan_list)
        )

    def test_validation_term_36(self):
        """ test_validation_term_36
        Should fail on the 60 month loan, loan_id: 12345
        """
        self.filters['term']['Year3'] = True
        self.filters['term']['Year5'] = False
        try:
            self.filters.validate(self.loan_list)

        # Check the loan it failed on
        except FilterValidationError as e:
            self.assertEqual(e.loan['loan_id'], 12345)

        # Invalid Exception
        except Exception:
            self.assertTrue(False)

    def test_validation_term_60(self):
        """ test_validation_term_60
        Should fail on the 36 month loan, loan_id: 23456
        """
        self.filters['term']['Year3'] = False
        self.filters['term']['Year5'] = True
        try:
            self.filters.validate(self.loan_list)

        # Check the loan it failed on
        except FilterValidationError as e:
            self.assertEqual(e.loan['loan_id'], 23456)

        # Invalid Exception
        except Exception:
            self.assertTrue(False)

    def test_validation_progress_70(self):
        """ test_validation_progress_70
        Loan 12345 is 91 percent funded
        Loan 23456 is 77 percent funded
        """
        self.filters['funding_progress'] = 70
        self.assertTrue(self.filters.validate(self.loan_list))

    def test_validation_progress_90(self):
        """ test_validation_term_90
        Should fail
        Loan 12345 is 91 percent funded
        Loan 23456 is 77 percent funded
        """
        self.filters['funding_progress'] = 90
        try:
            self.filters.validate(self.loan_list)

        # Check the loan it failed on
        except FilterValidationError as e:
            self.assertEqual(e.loan['loan_id'], 23456)

        # Invalid Exception
        except Exception:
            self.assertTrue(False)

    def test_validation_progress_95(self):
        """ test_validation_progress_95
        Should fail
        Loan 12345 is 91 percent funded
        Loan 23456 is 77 percent funded
        """
        self.filters['funding_progress'] = 95
        try:
            self.filters.validate(self.loan_list)

        # Check the loan it failed on
        except FilterValidationError as e:
            self.assertEqual(e.loan['loan_id'], 12345)

        # Invalid Exception
        except Exception:
            self.assertTrue(False)

    def test_validation_exclude_existing(self):
        """ test_validation_exclude_existing
        Should fail on loan 23456, which the user is already invested in.
        """
        self.filters['exclude_existing'] = True
        try:
            self.filters.validate(self.loan_list)

        # Check the loan it failed on
        except FilterValidationError as e:
            self.assertEqual(e.loan['loan_id'], 23456)

        # Invalid Exception
        except Exception:
            self.assertTrue(False)


class TestSavedFilters(unittest.TestCase):
    filters = None
    logger = None
    lc = None
    loan_list = None

    def setUp(self):
        self.logger = TestLogger()

        self.lc = LendingClub(logger=self.logger)
        self.lc.session.base_url = 'http://127.0.0.1:8000/'
        self.lc.session.set_logger(None)
        self.lc.authenticate('test@test.com', 'supersecret')

    def tearDown(self):
        pass

    def test_get_all_filters(self):
        filters = SavedFilter.all_filters(self.lc)

        self.assertEqual(len(filters), 2)
        self.assertEqual(filters[0].name, 'Filter 1')

    def test_get_saved_filters(self):
        saved = SavedFilter(self.lc, 1)

        self.assertEqual(saved.name, 'Filter 1')
        self.assertEqual(saved.id, 1)
        self.assertNotEqual(saved.search_string(), None)

    def test_validation_1(self):
        """ test_validation_1
        Filter 1 against filter_validation 1
        """
        saved = SavedFilter(self.lc, 1)

        # Get loan list
        response = self.lc.session.get('/filter_validation', query={'id': 1})
        json_response = response.json()
        self.loan_list = json_response['loanFractions']

        # Validate, should fail on 'exclude_invested'
        try:
            saved.validate(self.loan_list)
            assert False, 'Test should fail on exclude_existing'
        except FilterValidationError as e:
            print e.criteria
            self.assertTrue(matches('exclude loans', e.criteria))

    def test_validation_2(self):
        """ test_validation_2
        Filter 2 against filter_validation 2
        """
        saved = SavedFilter(self.lc, 2)

        # Get loan list
        response = self.lc.session.get('/filter_validation', query={'id': 2})
        json_response = response.json()
        self.loan_list = json_response['loanFractions']

        # Validate, should fail on 'exclude_invested'
        try:
            saved.validate(self.loan_list)
            assert False, 'Test should fail on loan_purpose'
        except FilterValidationError as e:
            print e.criteria
            self.assertTrue(matches('loan purpose', e.criteria))

    def test_validation_2_1(self):
        """ test_validation_2_1
        Filter 2 against filter_validation 1
        """
        saved = SavedFilter(self.lc, 2)

        # Get loan list
        response = self.lc.session.get('/filter_validation', query={'id': 1})
        json_response = response.json()
        self.loan_list = json_response['loanFractions']

        # Validate, should not fail
        saved.validate(self.loan_list)

    def test_validation_2_3(self):
        """ test_validation_3
        Filter 2 against filter_validation 3
        """
        saved = SavedFilter(self.lc, 2)

        # Get loan list
        response = self.lc.session.get('/filter_validation', query={'id': 3})
        json_response = response.json()
        self.loan_list = json_response['loanFractions']

        # Validate, should fail on 'exclude_invested'
        try:
            saved.validate(self.loan_list)
            assert False, 'Test should fail on grade'
        except FilterValidationError as e:
            print e.criteria
            self.assertTrue(matches('grade', e.criteria))


if __name__ == '__main__':
    # Start the web-server in a background thread
    http = ServerThread()
    http.start()

    # Run tests
    unittest.main()

    # Stop threads
    http.stop()
