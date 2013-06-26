#!/usr/bin/env python

import sys
import json as pyjson
import unittest

sys.path.insert(0, '.')
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from search import Filters


class TestFilters(unittest.TestCase):
    filters = None

    def setUp(self):
        self.filters = Filters()

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

        self.assertEqual(len(values), 0)

    def test_default_funding_progress(self):
        values = self.get_values(15)
        self.assertEqual(values[0]['value'], 0)

    def test_funding_progress(self):
        values = self.get_values(15)
        self.assertEqual(values[0]['value'], 0)

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


if __name__ == '__main__':
    unittest.main()
