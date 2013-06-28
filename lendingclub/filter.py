#!/usr/bin/env python

"""
Create a search filter
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
import re
from pybars import Compiler


class Filter(dict):

    def __init__(self):
        """
        Set the default search filter values
        """
        self['max_per_note'] = 0    # The most you most you want to invest per note, or 0 for no limit
        self['term'] = {
            'Year3': True,
            'Year5': True
        }
        self['exclude_existing'] = True
        self['funding_progress'] = 0
        self['grades'] = {
            'All': True,
            'A': False,
            'B': False,
            'C': False,
            'D': False,
            'E': False,
            'F': False,
            'G': False
        }

    def __normalize_grades(self):
        """
        Adjust the grades list.
        If a grade has been set, set All to false
        """

        if self['grades']['All'] is True:
            for grade in self['grades']:
                if grade != 'All' and self['grades'][grade] is True:
                    self['grades']['All'] = False
                    break

    def __normalize_progress(self):
        """
        Adjust the funding progress filter to be a factor of 10
        """

        progress = self['funding_progress']
        if progress % 10 != 0:
            progress = round(float(progress) / 10)
            progress = int(progress) * 10

            self['funding_progress'] = progress

    def validate(self, results):
        """
        Validate that the results indeed match the filters.
        It's a VERY good idea to run your search results through this, even though
        the filters were passed to LendingClub in your search. Since we're not using formal
        APIs for LendingClub, they could change the way their search works at anytime, which
        might break the filters.

        Parameters:
            results -- A list of loan note records returned from LendingClub
        """
        for loan in results:
            self.validate_one(loan)

    def validate_one(self, loan):
        """
        Validate a single result record to the filters

        Parameters:
            loan -- A single loan note record returned from LendingClub
        """
        assert type(loan) is dict, 'loan parameter must be a dictionary object'

        # Check required keys for a loan
        req = {
            'loanGrade': 'grade',
            'loanLength': 'term',
            'loanUnfundedAmount': 'progress',
            'loanAmountRequested': 'progress',
            'alreadyInvestedIn': 'exclude_existing'
        }
        for key, criteria in req.iteritems():
            if key not in loan:
                raise FilterValidationError('Loan does not have a "{0}" value.'.format(key), loan, criteria)

        # Grade
        grade = loan['loanGrade'][0]  # Extract the letter portion of the loan
        if grade not in self.grades:
            raise FilterValidationError('Loan grade "{0}" is unknown'.filter(grade), loan, 'grade')
        elif self.grades[grade] is False:
            raise FilterValidationError(loan=loan, criteria='grade')

        # Term
        if loan['loanLength'] == 36 and self['term']['Year3'] is False:
            raise FilterValidationError(loan=loan, criteria='term')
        elif loan['loanLength'] == 60 and self['term']['Year5'] is False:
            raise FilterValidationError(loan=loan, criteria='term')

        # Progress
        loan_progress = (1 - (loan['loanUnfundedAmount'] / loan['loanAmountRequested'])) * 100
        if self['funding_progress'] > loan_progress:
            raise FilterValidationError(loan=loan, criteria='funding_progress')

        # Exclude existing
        if self['exclude_existing'] is True and loan['alreadyInvestedIn'] is True:
            raise FilterValidationError(loan=loan, criteria='alreadyInvestedIn')

    def search_string(self):
        """"
        Returns the JSON string that LendingClub expects for it's search
        """

        self.__normalize_grades()
        self.__normalize_progress()

        # Get the template
        this_path = os.path.dirname(os.path.realpath(__file__))
        tmpl_file = os.path.join(this_path, 'filter.handlebars')
        tmpl_source = unicode(open(tmpl_file).read())

        # Process template
        compiler = Compiler()
        template = compiler.compile(tmpl_source)
        out = template(self)
        if not out:
            return False
        out = ''.join(out)

        #
        # Cleanup output and remove all extra space
        #

        # remove extra spaces
        out = re.sub('\n', '', out)
        out = re.sub('\s{3,}', ' ', out)

        # Remove hanging commas i.e: [1, 2,]
        out = re.sub(',\s*([}\\]])', '\\1', out)

        # Space between brackets i.e: ],  [
        out = re.sub('([{\\[}\\]])(,?)\s*([{\\[}\\]])', '\\1\\2\\3', out)

        # Cleanup spaces around [, {, }, ], : and , characters
        out = re.sub('\s*([{\\[\\]}:,])\s*', '\\1', out)

        return out


class FilterValidationError(Exception):
    """
    A loan note does not match the filters set.

    Attributes:
        value -- The error message
        loan -- The loan note that did not match
        criteria -- The filter that did not match.
    """
    value = None
    loan = None
    criteria = None

    def __init__(self, value=None, loan=None, criteria=None):
        self.loan = loan
        self.criteria = criteria

        if value is None:
            if criteria is None:
                self.value = 'Did not meet filter criteria'
            else:
                self.value = 'Did not meet filter criteria for {0}'.format(criteria)
        else:
            self.value = value

    def __str__(self):
        return repr(self.value)