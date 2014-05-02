#!/usr/bin/env python

"""
Filters are used to search lending club for loans to invest in. There are many filters you can use, here are some
examples with the main `Filter` class.

For example, to search for B grade loans,
you could create a filter like this:

    >>> filters = Filter()
    >>> filters['grades']['B'] = True

Or, another more complex example:

    >>> filters = Filter()
    >>> filters['grades']['B'] = True
    >>> filters['funding_progress'] = 90
    >>> filters['term']['Year5'] = False

This would search for B grade loans that are at least 90% funded and not 5 year loans.

Filters currently do not support all search criteria. To see what is supported, create one and print it:

    >>> filter = Filter()
    >>> print filter
    {'exclude_existing': True,
     'funding_progress': 0,
     'grades': {'A': False,
                'All': True,
                'B': False,
                'C': False,
                'D': False,
                'E': False,
                'F': False,
                'G': False},
     'term': {'Year3': True,
              'Year5': True}}

You can also set the values on instantiation:

    >>> filters = Filter({'grades': {'B': True, 'C': True, 'D': True, 'E': True}})
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
import json
from pybars import Compiler


class Filter(dict):
    """
    The default search filter that let's you refine your search based on a
    dictionary of search facets. Not all search options are supported yet.

    Parameters
    ----------
    filters : dict, optional
        This will override any of the search filters you want on instantiation.

    Examples
    --------
    See the default filters::

        >>> from lendingclub.filters import Filter
        >>> from pprint import pprint
        >>> filter = Filter()
        >>> pprint(filter)
        {'exclude_existing': True,
         'funding_progress': 0,
         'grades': {'A': False,
                    'All': True,
                    'B': False,
                    'C': False,
                    'D': False,
                    'E': False,
                    'F': False,
                    'G': False},
         'term': {'Year3': True,
                  'Year5': True}}

    Set filters on instantiation::

        >>> from lendingclub.filters import Filter
        >>> from pprint import pprint
        >>> filters = Filter({'grades': {'B': True, 'C': True, 'D': True, 'E': True}})
        >>> pprint(filters['grades'])
        {'All': False,
         'A': False,
         'B': True,
         'C': True,
         'D': True,
         'E': True,
         'F': False,
         'G': False}
    """

    tmpl_file = False
    __initialized = False
    __normalizing = False

    def __init__(self, filters=None):
        """
        Set the default search filter values
        """

        # Set filter values
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

        # Merge in filter values
        if filters is not None:
            self.__merge_values(filters, self)

        # Set the template file path
        this_path = os.path.dirname(os.path.realpath(__file__))
        self.tmpl_file = os.path.join(this_path, 'filter.handlebars')

        self.__initialized = True
        self.__normalize()

    def __merge_values(self, from_dict, to_dict):
        """
        Merge dictionary objects recursively, by only updating keys existing in to_dict
        """
        for key, value in from_dict.iteritems():

            # Only if the key already exists
            if key in to_dict:

                # Make sure the values are the same datatype
                assert type(to_dict[key]) is type(from_dict[key]), 'Data type for {0} is incorrect: {1}, should be {2}'.format(key, type(from_dict[key]), type(to_dict[key]))

                # Recursively dive into the next dictionary
                if type(to_dict[key]) is dict:
                    to_dict[key] = self.__merge_values(from_dict[key], to_dict[key])

                # Replace value
                else:
                    to_dict[key] = from_dict[key]

        return to_dict

    def __getitem__(self, key):
        self.__normalize()
        return dict.__getitem__(self, key)

    def __setitem__(self, key, value):

        # If setting grades, merge dictionary instead of replace
        if key == 'grades' and self.__initialized is True:
            assert type(value) is dict, 'The grades filter must be a dictionary object'
            self.__merge_values(value, dict.__getitem__(self, 'grades'))
            value = self['grades']

        # Set value and normalize
        dict.__setitem__(self, key, value)
        self.__normalize()

    def __normalize_grades(self):
        """
        Adjust the grades list.
        If a grade has been set, set All to false
        """

        if 'grades' in self and self['grades']['All'] is True:
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

    def __normalize(self):
        """
        Adjusts the values of the filters to be correct.
        For example, if you set grade 'B' to True, then 'All'
        should be set to False
        """

        # Don't normalize if we're already normalizing or intializing
        if self.__normalizing is True or self.__initialized is False:
            return

        self.__normalizing = True
        self.__normalize_grades()
        self.__normalize_progress()
        self.__normalizing = False

    def validate(self, results):
        """
        Validate that the results indeed match the filters.
        It's a VERY good idea to run your search results through this, even though
        the filters were passed to LendingClub in your search. Since we're not using formal
        APIs for LendingClub, they could change the way their search works at anytime, which
        might break the filters.

        Parameters
        ----------
        results : list
            A list of loan note records returned from LendingClub

        Returns
        -------
        boolean
            True or raises FilterValidationError

        Raises
        ------
        FilterValidationError
            If a loan does not match the filter criteria
        """
        for loan in results:
            self.validate_one(loan)

        return True

    def validate_one(self, loan):
        """
        Validate a single result record to the filters

        Parameters
        ----------
        loan : dict
            A single loan note record

        Returns
        -------
        boolean
            True or raises FilterValidationError

        Raises
        ------
        FilterValidationError
            If the loan does not match the filter criteria
        """
        assert type(loan) is dict, 'loan parameter must be a dictionary object'

        # Map the loan value keys to the filter keys
        req = {
            'loanGUID': 'loan_id',
            'loanGrade': 'grade',
            'loanLength': 'term',
            'loanUnfundedAmount': 'progress',
            'loanAmountRequested': 'progress',
            'alreadyInvestedIn': 'exclude_existing',
            'purpose': 'loan_purpose',
        }

        # Throw an error if the loan does not contain one of the criteria keys that this filter has
        for key, criteria in req.iteritems():
            if criteria in self and key not in loan:
                raise FilterValidationError('Loan does not have a "{0}" value.'.format(key), loan, criteria)

        # Loan ID
        if 'loan_id' in self:
            loan_ids = str(self['loan_id']).split(',')
            if str(loan['loanGUID']) not in loan_ids:
                raise FilterValidationError('Did not meet filter criteria for loan ID. {0} does not match {1}'.format(loan['loanGUID'], self['loan_id']), loan=loan, criteria='loan ID')

        # Grade
        grade = loan['loanGrade'][0]  # Extract the letter portion of the loan
        if 'grades' in self and self['grades']['All'] is not True:
            if grade not in self['grades']:
                raise FilterValidationError('Loan grade "{0}" is unknown'.format(grade), loan, 'grade')
            elif self['grades'][grade] is False:
                raise FilterValidationError(loan=loan, criteria='grade')

        # Term
        if 'term' in self:
            if loan['loanLength'] == 36 and self['term']['Year3'] is False:
                raise FilterValidationError(loan=loan, criteria='loan term')
            elif loan['loanLength'] == 60 and self['term']['Year5'] is False:
                raise FilterValidationError(loan=loan, criteria='loan term')

        # Progress
        if 'funding_progress' in self:
            loan_progress = (1 - (loan['loanUnfundedAmount'] / loan['loanAmountRequested'])) * 100
            if self['funding_progress'] > loan_progress:
                raise FilterValidationError(loan=loan, criteria='funding progress')

        # Exclude existing
        if 'exclude_existing' in self:
            if self['exclude_existing'] is True and loan['alreadyInvestedIn'] is True:
                raise FilterValidationError(loan=loan, criteria='exclude loans you are invested in')

        # Loan purpose (either an array or single value)
        if 'loan_purpose' in self and loan['purpose'] is not False:
            purpose = self['loan_purpose']
            if type(purpose) is not dict:
                purpose = {purpose: True}

            if 'All' not in purpose or purpose['All'] is False:
                if loan['purpose'] not in purpose:
                    raise FilterValidationError(loan=loan, criteria='loan purpose')

        return True

    def search_string(self):
        """"
        Returns the JSON string that LendingClub expects for it's search
        """
        self.__normalize()

        # Get the template
        tmpl_source = unicode(open(self.tmpl_file).read())

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


class SavedFilter(Filter):
    """
    Load a saved search filter from the site. Since this is
    loading a filter from the server, the individual values cannot be modified.
    Most often it is easiest to load the saved filters from LendingClub, via `get_saved_filters` and `get_saved_filter`.
    See examples.

    Parameters
    ----------
    lc : :py:class:`lendingclub.LendingClub`
        An instance of the LendingClub class that will be used to communicate with the site
    filter_id : int
        The ID of the filter to load

    Examples
    --------

    The SavedFilter needs to use an instance of LendingClub to access the site, so the class has a couple wrappers
    you can use to load SavedFilters. Here are a couple examples of loading saved filters from the LendingClub instance.

    Load all saved filters:
        >>> from lendingclub import LendingClub
        >>> from lendingclub.filters import SavedFilter
        >>> lc = LendingClub(email='test@test.com', password='secret123')
        >>> lc.authenticate()
        True
        >>> filters = SavedFilter.all_filters(lc)    # Get a list of all saved filters on LendinClub.com
        >>> print filters
        [<SavedFilter: 12345, '90 Percent'>, <SavedFilter: 23456, 'Only A loans'>]

    Load a single saved filter:
        >>> from lendingclub import LendingClub
        >>> from lendingclub.filters import SavedFilter
        >>> lc = LendingClub(email='test@test.com', password='secret123')
        >>> lc.authenticate()
        True
        >>> filter = lc.get_saved_filter(23456)    # Get a single saved search filter from the site by ID
        >>> filter.name
        u'Only A'
    """
    id = None
    lc = None
    name = None
    json = None
    json_text = None
    response = None

    @staticmethod
    def all_filters(lc):
        """
        Get a list of all your saved filters

        Parameters
        ----------
        lc : :py:class:`lendingclub.LendingClub`
            An instance of the authenticated LendingClub class

        Returns
        -------
        list
            A list of lendingclub.filters.SavedFilter objects
        """

        filters = []
        response = lc.session.get('/browse/getSavedFiltersAj.action')
        json_response = response.json()

        # Load all filters
        if lc.session.json_success(json_response):
            for saved in json_response['filters']:
                filters.append(SavedFilter(lc, saved['id']))

        return filters

    def __init__(self, lc, filter_id):
        self.id = filter_id
        self.lc = lc
        self.load()

    def reload(self):
        """
        Reload the saved filter
        """
        self.load()

    def load(self):
        """
        Load the filter from the server
        """

        # Attempt to load the saved filter
        payload = {
            'id': self.id
        }
        response = self.lc.session.get('/browse/getSavedFilterAj.action', query=payload)
        self.response = response
        json_response = response.json()

        if self.lc.session.json_success(json_response) and json_response['filterName'] != 'No filters':
            self.name = json_response['filterName']

            #
            # Parse out the filter JSON string manually from the response JSON.
            # If the filter JSON is modified at all, or any value is out of order,
            # LendingClub will reject the filter and perform a wildcard search instead,
            # without any error. So we need to retain the filter JSON value exactly how it is given to us.
            #
            text = response.text

            # Cut off everything  before "filter": [...]
            text = re.sub('\n', '', text)
            text = re.sub('^.*?,\s*["\']filter["\']:\s*\[(.*)', '[\\1', text)

            # Now loop through the string until we find the end of the filter block
            # This is a simple parser that keeps track of block elements, quotes and
            # escape characters
            blockTracker = []
            blockChars = {
                '[': ']',
                '{': '}'
            }
            inQuote = False
            lastChar = None
            json_text = ""
            for char in text:
                json_text += char

                # Escape char
                if char == '\\':
                    if lastChar == '\\':
                        lastChar = ''
                    else:
                        lastChar = char
                    continue

                # Quotes
                if char == "'" or char == '"':
                    if inQuote is False:  # Starting a quote block
                        inQuote = char
                    elif inQuote == char:  # Ending a quote block
                        inQuote = False
                    lastChar = char
                    continue

                # Start of a block
                if char in blockChars.keys():
                    blockTracker.insert(0, blockChars[char])

                # End of a block, remove from block path
                elif len(blockTracker) > 0 and char == blockTracker[0]:
                    blockTracker.pop(0)

                # No more blocks in the tracker which means we're at the end of the filter block
                if len(blockTracker) == 0 and lastChar is not None:
                    break

                lastChar = char

            # Verify valid JSON
            try:
                if json_text.strip() == '':
                    raise SavedFilterError('A saved filter could not be found for ID {0}'.format(self.id), response)

                json_test = json.loads(json_text)

                # Make sure it looks right
                assert type(json_test) is list, 'Expecting a list, instead received a {0}'.format(type(json_test))
                assert 'm_id' in json_test[0], 'Expecting a \'m_id\' property in each filter'
                assert 'm_value' in json_test[0], 'Expecting a \'m_value\' property in each filter'

                self.json = json_test
            except Exception as e:
                raise SavedFilterError('Could not parse filter from the JSON response: {0}'.format(str(e)))

            self.json_text = json_text
            self.__analyze()

        else:
            raise SavedFilterError('A saved filter could not be found for ID {0}'.format(self.id), response)

    def __str__(self):
        return '<SavedFilter: {0}, \'{1}\'>'.format(self.id, self.name)

    def __repr__(self):
        return self.__str__()

    def __setitem__(self, key, value):
        raise SavedFilterError('A saved filter cannot be modified')

    def __analyze(self):
        """
        Analyze the filter JSON and attempt to parse out the individual filters.
        """
        filter_values = {}

        # ID to filter name mapping
        name_map = {
            10: 'grades',
            11: 'loan_purpose',
            13: 'approved',
            15: 'funding_progress',
            38: 'exclude_existing',
            39: 'term',
            43: 'keyword'
        }

        if self.json is not None:
            filters = self.json

            for f in filters:
                if 'm_id' in f:
                    name = f['m_id']

                    # Get the name to represent this filter
                    if f['m_id'] in name_map:
                        name = name_map[f['m_id']]

                    # Get values
                    if 'm_value' in f:
                        raw_values = f['m_value']
                        value = {}

                        # Loop through multiple values
                        if type(raw_values) is list:

                            # A single non string value, is THE value
                            if len(raw_values) == 1 and type(raw_values[0]['value']) not in [str, unicode]:
                                value = raw_values[0]['value']

                            # Create a dict of values: name = True
                            for val in raw_values:
                                if type(val['value']) in [str, unicode]:
                                    value[val['value']] = True

                        # A single value
                        else:
                            value = raw_values

                        # Normalize grades array
                        if name == 'grades':
                            if 'All' not in value:
                                value['All'] = False

                    # Add filter value
                    filter_values[name] = value
                    dict.__setitem__(self, name, value)

        return filter_values

    def __normalize():
        pass

    def search_string(self):
        """
        Get the search JSON string to send to the server
        """
        return self.json_text


class FilterByLoanID(Filter):
    """
    Creates a filter to search by loan ID. You can either search by
    1 loan ID or for multiple loans by ID.

    Parameters
    ----------
    loan_id : int or list
        The loan ID or a list of loan IDs

    Examples
    --------

    Search for 1 loan by ID:

        >>> from lendingclub import LendingClub
        >>> from lendingclub.filters import FilterByLoanID
        >>> lc = LendingClub(email='test@test.com', password='secret123')
        >>> lc.authenticate()
        True
        >>> filter = FilterByLoanID(1234)  # Search for the loan 1234
        >>> results = lc.search(filter)
        >>> len(results['loans'])
        1

    Search for multiple loans by ID:

        >>> from lendingclub import LendingClub
        >>> from lendingclub.filters import FilterByLoanID
        >>> lc = LendingClub(email='test@test.com', password='secret123')
        >>> lc.authenticate()
        True
        >>> filter = FilterByLoanID(54321, 76432)  # Search for two loans: 54321 and 76432
        >>> results = lc.search(filter)
        >>> len(results['loans'])
        2
    """

    def __init__(self, loan_id):

        # Convert a list to comma delimited string
        if type(loan_id) is list:
            loan_id = map(str, loan_id)
            loan_id = ','.join(loan_id)

        self['loan_id'] = loan_id
        this_path = os.path.dirname(os.path.realpath(__file__))
        self.tmpl_file = os.path.join(this_path, 'filter.handlebars')

    def __normalize():
        pass


class FilterValidationError(Exception):
    """
    A loan note does not match the filters set.

    After a search is performed, each loan returned from the server will be
    validate against the filter's criteria, for good measure. If it doesn't match, this exception is thrown.

    Parameters
    ----------
    value : string
        The error message
    loan : dict
        The loan that did not match
    criteria : string
        The filter item that the loan failed on.
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


class SavedFilterError(Exception):
    """
    An error occurred while loading or processing a :class:SavedFilter

    Parameters
    ----------
    value : string
        The error message
    response : `requests.Response <http://docs.python-requests.org/en/latest/api/#requests.Response>`_
        The Response object from the HTTP request to find the saved filter.
    """
    value = None
    request = None

    def __init__(self, value, request=None):
        self.value = value
        self.request = request

    def __str__(self):
        return repr(self.value)
