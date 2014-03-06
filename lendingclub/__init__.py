#!/usr/bin/env python

"""
The stand-alone python module for interacting with your Lending Club account.
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

import re
import os
from pprint import pprint
from bs4 import BeautifulSoup
from lendingclub.filters import Filter, FilterByLoanID, SavedFilter
from lendingclub.session import Session


class LendingClub:
    """
    The main entry point for interacting with Lending Club.

    Parameters
    ----------
    email : string
        The email of a user on Lending Club
    password : string
        The user's password, for authentication.
    logger : `Logger <http://docs.python.org/2/library/logging.html>`_
        A python logger used to get debugging output from this module.

    Examples
    --------

    Get the cash balance in your lending club account:

        >>> from lendingclub import LendingClub
        >>> lc = LendingClub()
        >>> lc.authenticate()         # Authenticate with your lending club credentials
        Email:test@test.com
        Password:
        True
        >>> lc.get_cash_balance()     # See the cash you have available for investing
        463.80000000000001

    You can also enter your email and password when you instantiate the LendingClub class, in one line:

        >>> from lendingclub import LendingClub
        >>> lc = LendingClub(email='test@test.com', password='secret123')
        >>> lc.authenticate()
        True
    """

    __logger = None
    session = None
    order = None

    def __init__(self, email=None, password=None, logger=None):
        self.session = Session(email, password)
        self.order = Order(self.session)

        if logger is not None:
            self.set_logger(logger)

    def __log(self, message):
        """
        Log a debugging message
        """
        if self.__logger:
            self.__logger.debug(message)

    def set_logger(self, logger):
        """
        Set a logger to send debug messages to

        Parameters
        ----------
        logger : `Logger <http://docs.python.org/2/library/logging.html>`_
            A python logger used to get debugging output from this module.
        """
        self.__logger = logger
        self.session.set_logger(self.__logger)

    def version(self):
        """
        Return the version number of the Lending Club Investor tool

        Returns
        -------
        string
            The version number string
        """
        this_path = os.path.dirname(os.path.realpath(__file__))
        version_file = os.path.join(this_path, 'VERSION')
        return open(version_file).read()

    def authenticate(self, email=None, password=None):
        """
        Attempt to authenticate the user.

        Parameters
        ----------
        email : string
            The email of a user on Lending Club
        password : string
            The user's password, for authentication.

        Returns
        -------
        boolean
            True if the user authenticated or raises an exception if not

        Raises
        ------
        session.AuthenticationError
            If authentication failed
        session.NetworkError
            If a network error occurred
        """
        if self.session.authenticate(email, password):
            return True

    def is_site_available(self):
        """
        Returns true if we can access LendingClub.com
        This is also a simple test to see if there's an internet connection

        Returns
        -------
        boolean
        """
        return self.session.is_site_available()

    def get_cash_balance(self):
        """
        Returns the account cash balance available for investing

        Returns
        -------
        float
            The cash balance in your account.
        """
        cash = False
        try:
            response = self.session.get('/browse/cashBalanceAj.action')
            json_response = response.json()

            if self.session.json_success(json_response):
                self.__log('Cash available: {0}'.format(json_response['cashBalance']))
                cash_value = json_response['cashBalance']

                # Convert currency to float value
                # Match values like $1,000.12 or 1,0000$
                cash_match = re.search('^[^0-9]?([0-9\.,]+)[^0-9]?', cash_value)
                if cash_match:
                    cash_str = cash_match.group(1)
                    cash_str = cash_str.replace(',', '')
                    cash = float(cash_str)
            else:
                self.__log('Could not get cash balance: {0}'.format(response.text))

        except Exception as e:
            self.__log('Could not get the cash balance on the account: Error: {0}\nJSON: {1}'.format(str(e), response.text))
            raise e

        return cash

    def get_investable_balance(self):
        """
        Returns the amount of money from your account that you can invest.
        Loans are multiples of $25, so this is your total cash balance, adjusted to be a multiple of 25.

        Returns
        -------
        int
            The amount of cash you can invest
        """
        cash = int(self.get_cash_balance())
        while cash % 25 != 0:
            cash -= 1
        return cash

    def get_portfolio_list(self, names_only=False):
        """
        Get your list of named portfolios from the lendingclub.com

        Parameters
        ----------
        names_only : boolean, optional
            If set to True, the function will return a list of portfolio names, instead of portfolio objects

        Returns
        -------
        list
            A list of portfolios (or names, if `names_only` is True)
        """
        folios = []
        response = self.session.get('/data/portfolioManagement?method=getLCPortfolios')
        json_response = response.json()

        # Get portfolios and create a list of names
        if self.session.json_success(json_response):
            folios = json_response['results']

            if names_only is True:
                for i, folio in enumerate(folios):
                    folios[i] = folio['portfolioName']

        return folios

    def get_saved_filters(self):
        """
        Get a list of all the saved search filters you've created on lendingclub.com

        Returns
        -------
        list
            List of :class:`lendingclub.filters.SavedFilter` objects
        """
        return SavedFilter.all_filters(self)

    def get_saved_filter(self, filter_id):
        """
        Load a single saved search filter from the site by ID

        Parameters
        ----------
        filter_id : int
            The ID of the saved filter

        Returns
        -------
        SavedFilter
            A :class:`lendingclub.filters.SavedFilter` object or False
        """
        return SavedFilter(self, filter_id)

    def assign_to_portfolio(self, portfolio_name, loan_id, order_id):
        """
        Assign a note to a named portfolio. `loan_id` and `order_id` can be either
        integer values or lists. If choosing lists, they both **MUST** be the same length
        and line up. For example, `order_id[5]` must be the order ID for `loan_id[5]`

        Parameters
        ----------
        portfolio_name : string
            The name of the portfolio to assign a the loan note to -- new or existing
        loan_id : int or list
            The loan ID, or list of loan IDs, to assign to the portfolio
        order_id : int or list
            The order ID, or list of order IDs, that this loan note was invested with.
            You can find this in the dict returned from `get_note()`

        Returns
        -------
        boolean
            True on success
        """
        response = None

        assert type(loan_id) == type(order_id), "Both loan_id and order_id need to be the same type"
        assert type(loan_id) in (int, list), "loan_id and order_id can only be int or list types"
        assert type(loan_id) is int or (type(loan_id) is list and len(loan_id) == len(order_id)), "If order_id and loan_id are lists, they both need to be the same length"

        # Data
        post = {
            'loan_id': loan_id,
            'record_id': loan_id,
            'order_id': order_id
        }
        query = {
            'method': 'createLCPortfolio',
            'lcportfolio_name': portfolio_name
        }

        # Is it an existing portfolio
        existing = self.get_portfolio_list()
        for folio in existing:
            if folio['portfolioName'] == portfolio_name:
                query['method'] = 'addToLCPortfolio'

        # Send
        response = self.session.post('/data/portfolioManagement', query=query, data=post)
        json_response = response.json()

        # Failed
        if not self.session.json_success(json_response):
            raise LendingClubError('Could not assign order to portfolio \'{0}\''.format(portfolio_name), response)

        # Success
        else:

            # Assigned to another portfolio, for some reason, raise warning
            if 'portfolioName' in json_response and json_response['portfolioName'] != portfolio_name:
                raise LendingClubError('Added order to portfolio "{0}" - NOT - "{1}", and I don\'t know why'.format(json_response['portfolioName'], portfolio_name))

            # Assigned to the correct portfolio
            else:
                self.__log('Added order to portfolio "{0}"'.format(portfolio_name))

            return True

        return False

    def search(self, filters=None, start_index=0, limit=100):
        """
        Search for a list of notes that can be invested in.
        (similar to searching for notes in the Browse section on the site)

        Parameters
        ----------
        filters : lendingclub.filters.*, optional
            The filter to use to search for notes. If no filter is passed, a wildcard search
            will be performed.
        start_index : int, optional
            The result index to start on. By default only 100 records will be returned at a time, so use this
            to start at a later index in the results. For example, to get results 200 - 300, set `start_index` to 200.
            (default is 0)
        limit : int, optional
            The number of results to return per request. (default is 100)

        Returns
        -------
        dict
            A dictionary object with the list of matching loans under the `loans` key.
        """
        assert filters is None or isinstance(filters, Filter), 'filter is not a lendingclub.filters.Filter'

        # Set filters
        if filters:
            filter_string = filters.search_string()
        else:
            filter_string = 'default'
        payload = {
            'method': 'search',
            'filter': filter_string,
            'startindex': start_index,
            'pagesize': limit
        }

        # Make request
        response = self.session.post('/browse/browseNotesAj.action', data=payload)
        json_response = response.json()

        if self.session.json_success(json_response):
            results = json_response['searchresult']

            # Normalize results by converting loanGUID -> loan_id
            for loan in results['loans']:
                loan['loan_id'] = int(loan['loanGUID'])

            # Validate that fractions do indeed match the filters
            if filters is not None:
                filters.validate(results['loans'])

            return results

        return False

    def build_portfolio(self, cash, max_per_note=25, min_percent=0, max_percent=20, filters=None, automatically_invest=False, do_not_clear_staging=False):
        """
        Returns a list of loan notes that are diversified by your min/max percent request and filters.
        One way to invest in these loan notes, is to start an order and use add_batch to add all the
        loan fragments to them. (see examples)

        Parameters
        ----------
        cash : int
            The total amount you want to invest across a portfolio of loans (at least $25).
        max_per_note : int, optional
            The maximum dollar amount you want to invest per note. Must be a multiple of 25
        min_percent : int, optional
            THIS IS NOT PER NOTE, but the minimum average percent of return for the entire portfolio.
        max_percent : int, optional
            THIS IS NOT PER NOTE, but the maxmimum average percent of return for the entire portfolio.
        filters : lendingclub.filters.*, optional
            The filters to use to search for portfolios
        automatically_invest : boolean, optional
            If you want the tool to create an order and automatically invest in the portfolio that matches your filter.
            (default False)
        do_not_clear_staging : boolean, optional
            Similar to automatically_invest, don't do this unless you know what you're doing.
            Setting this to True stops the method from clearing the loan staging area before returning

        Returns
        -------
        dict
            A dict representing a new portfolio or False if nothing was found.
            If `automatically_invest` was set to `True`, the dict will contain an `order_id` key with
            the ID of the completed investment order.

        Notes
        -----
        **The min/max_percent parameters**

        When searching for portfolios, these parameters will match a portfolio of loan notes which have
        an **AVERAGE** percent return between these values. If there are multiple portfolio matches, the
        one closes to the max percent will be chosen.

        Examples
        --------
        Here we want to invest $400 in a portfolio with only B, C, D and E grade notes with an average overall return between 17% - 19%. This similar to finding a portfolio in the 'Invest' section on lendingclub.com::

            >>> from lendingclub import LendingClub
            >>> from lendingclub.filters import Filter
            >>> lc = LendingClub()
            >>> lc.authenticate()
            Email:test@test.com
            Password:
            True
            >>> filters = Filter()                  # Set the search filters (only B, C, D and E grade notes)
            >>> filters['grades']['C'] = True
            >>> filters['grades']['D'] = True
            >>> filters['grades']['E'] = True
            >>> lc.get_cash_balance()               # See the cash you have available for investing
            463.80000000000001

            >>> portfolio = lc.build_portfolio(400, # Invest $400 in a portfolio...
                    min_percent=17.0,               # Return percent average between 17 - 19%
                    max_percent=19.0,
                    max_per_note=50,                # As much as $50 per note
                    filters=filters)                # Search using your filters

            >>> len(portfolio['loan_fractions'])    # See how many loans are in this portfolio
            16
            >>> loans_notes = portfolio['loan_fractions']
            >>> order = lc.start_order()            # Start a new order
            >>> order.add_batch(loans_notes)        # Add the loan notes to the order
            >>> order.execute()                     # Execute the order
            1861880

        Here we do a similar search, but automatically invest the found portfolio. **NOTE** This does not allow
        you to review the portfolio before you invest in it.

            >>> from lendingclub import LendingClub
            >>> from lendingclub.filters import Filter
            >>> lc = LendingClub()
            >>> lc.authenticate()
            Email:test@test.com
            Password:
            True
                                                    # Filter shorthand
            >>> filters = Filter({'grades': {'B': True, 'C': True, 'D': True, 'E': True}})
            >>> lc.get_cash_balance()               # See the cash you have available for investing
            463.80000000000001

            >>> portfolio = lc.build_portfolio(400,
                    min_percent=17.0,
                    max_percent=19.0,
                    max_per_note=50,
                    filters=filters,
                    automatically_invest=True)      # Same settings, except invest immediately

            >>> portfolio['order_id']               # See order ID
            1861880
        """
        assert filters is None or isinstance(filters, Filter), 'filter is not a lendingclub.filters.Filter'
        assert max_per_note >= 25, 'max_per_note must be greater than or equal to 25'

        # Set filters
        if filters:
            filter_str = filters.search_string()
        else:
            filter_str = 'default'

        # Start a new order
        self.session.clear_session_order()

        # Make request
        payload = {
            'amount': cash,
            'max_per_note': max_per_note,
            'filter': filter_str
        }
        self.__log('POST VALUES -- amount: {0}, max_per_note: {1}, filter: ...'.format(cash, max_per_note))
        response = self.session.post('/portfolio/lendingMatchOptionsV2.action', data=payload)
        json_response = response.json()

        # Options were found
        if self.session.json_success(json_response) and 'lmOptions' in json_response:
            options = json_response['lmOptions']

            # Nothing found
            if type(options) is not list or json_response['numberTicks'] == 0:
                self.__log('No lending portfolios were returned with your search')
                return False

            # Choose an investment option based on the user's min/max values
            i = 0
            match_index = -1
            match_option = None
            for option in options:

                # A perfect match
                if option['percentage'] == max_percent:
                    match_option = option
                    match_index = i
                    break

                # Over the max
                elif option['percentage'] > max_percent:
                    break

                # Higher than the minimum percent and the current matched option
                elif option['percentage'] >= min_percent and (match_option is None or match_option['percentage'] < option['percentage']):
                    match_option = option
                    match_index = i

                i += 1

            # Nothing matched
            if match_option is None:
                self.__log('No portfolios matched your percentage requirements')
                return False

            # Mark this portfolio for investing (in order to get a list of all notes)
            payload = {
                'order_amount': cash,
                'lending_match_point': match_index,
                'lending_match_version': 'v2'
            }
            self.session.get('/portfolio/recommendPortfolio.action', query=payload)

            # Get all loan fractions
            payload = {
                'method': 'getPortfolio'
            }
            response = self.session.get('/data/portfolio', query=payload)
            json_response = response.json()

            # Extract fractions from response
            fractions = []
            if 'loanFractions' in json_response:
                fractions = json_response['loanFractions']

                # Normalize by converting loanFractionAmount to invest_amount
                for frac in fractions:
                    frac['invest_amount'] = frac['loanFractionAmount']

                    # Raise error if amount is greater than max_per_note
                    if frac['invest_amount'] > max_per_note:
                        raise LendingClubError('ERROR: LendingClub tried to invest ${0} in a loan note. Your max per note is set to ${1}. Portfolio investment canceled.'.format(frac['invest_amount'], max_per_note))

            if len(fractions) == 0:
                self.__log('The selected portfolio didn\'t have any loans')
                return False
            match_option['loan_fractions'] = fractions

            # Validate that fractions do indeed match the filters
            if filters is not None:
                filters.validate(fractions)

            # Not investing -- reset portfolio search session and return
            if automatically_invest is not True:
                if do_not_clear_staging is not True:
                    self.session.clear_session_order()

            # Invest in this porfolio
            elif automatically_invest is True:  # just to be sure
                order = self.start_order()

                # This should probably only be ever done here...ever.
                order._Order__already_staged = True
                order._Order__i_know_what_im_doing = True

                order.add_batch(match_option['loan_fractions'])
                order_id = order.execute()
                match_option['order_id'] = order_id

            return match_option
        else:
            raise LendingClubError('Could not find any portfolio options that match your filters', response)

        return False

    def my_notes(self, start_index=0, limit=100, get_all=False, sort_by='loanId', sort_dir='asc'):
        """
        Return all the loan notes you've already invested in. By default it'll return 100 results at a time.

        Parameters
        ----------
        start_index : int, optional
            The result index to start on. By default only 100 records will be returned at a time, so use this
            to start at a later index in the results. For example, to get results 200 - 300, set `start_index` to 200.
            (default is 0)
        limit : int, optional
            The number of results to return per request. (default is 100)
        get_all : boolean, optional
            Return all results in one request, instead of 100 per request.
        sort_by : string, optional
            What key to sort on
        sort_dir : {'asc', 'desc'}, optional
            Which direction to sort

        Returns
        -------
        dict
            A dictionary with a list of matching notes on the `loans` key
        """

        index = start_index
        notes = {
            'loans': [],
            'total': 0,
            'result': 'success'
        }
        while True:
            payload = {
                'sortBy': sort_by,
                'dir': sort_dir,
                'startindex': index,
                'pagesize': limit,
                'namespace': '/account'
            }
            response = self.session.post('/account/loansAj.action', data=payload)
            json_response = response.json()

            # Notes returned
            if self.session.json_success(json_response):
                notes['loans'] += json_response['searchresult']['loans']
                notes['total'] = json_response['searchresult']['totalRecords']

            # Error
            else:
                notes['result'] = json_response['result']
                break

            # Load more
            if get_all is True and len(notes['loans']) < notes['total']:
                index += limit

            # End
            else:
                break

        return notes

    def get_note(self, note_id):
        """
        Get a loan note that you've invested in by ID

        Parameters
        ----------
        note_id : int
            The note ID

        Returns
        -------
        dict
            A dictionary representing the matching note or False

        Examples
        --------
            >>> from lendingclub import LendingClub
            >>> lc = LendingClub(email='test@test.com', password='secret123')
            >>> lc.authenticate()
            True
            >>> notes = lc.my_notes()                  # Get the first 100 loan notes
            >>> len(notes['loans'])
            100
            >>> notes['total']                          # See the total number of loan notes you have
            630
            >>> notes = lc.my_notes(start_index=100)   # Get the next 100 loan notes
            >>> len(notes['loans'])
            100
            >>> notes = lc.my_notes(get_all=True)       # Get all notes in one request (may be slow)
            >>> len(notes['loans'])
            630
        """

        index = 0
        while True:
            notes = self.my_notes(start_index=index, sort_by='noteId')

            if notes['result'] != 'success':
                break

            # If the first note has a higher ID, we've passed it
            if notes['loans'][0]['noteId'] > note_id:
                break

            # If the last note has a higher ID, it could be in this record set
            if notes['loans'][-1]['noteId'] >= note_id:
                for note in notes['loans']:
                    if note['noteId'] == note_id:
                        return note

            index += 100

        return False

    def search_my_notes(self, loan_id=None, order_id=None, grade=None, portfolio_name=None, status=None, term=None):
        """
        Search for notes you are invested in. Use the parameters to define how to search.
        Passing no parameters is the same as calling `my_notes(get_all=True)`

        Parameters
        ----------
        loan_id : int, optional
            Search for notes for a specific loan. Since a loan is broken up into a pool of notes, it's possible
            to invest multiple notes in a single loan
        order_id : int, optional
            Search for notes from a particular investment order.
        grade : {A, B, C, D, E, F, G}, optional
            Match by a particular loan grade
        portfolio_name : string, optional
            Search for notes in a portfolio with this name (case sensitive)
        status : string, {issued, in-review, in-funding, current, charged-off, late, in-grace-period, fully-paid}, optional
            The funding status string.
        term : {60, 36}, optional
            Term length, either 60 or 36 (for 5 year and 3 year, respectively)

        Returns
        -------
        dict
            A dictionary with a list of matching notes on the `loans` key
        """
        assert grade is None or type(grade) is str, 'grade must be a string'
        assert portfolio_name is None or type(portfolio_name) is str, 'portfolio_name must be a string'

        index = 0
        found = []
        sort_by = 'orderId' if order_id is not None else 'loanId'
        group_id = order_id if order_id is not None else loan_id   # first match by order, then by loan

        # Normalize grade
        if grade is not None:
            grade = grade[0].upper()

        # Normalize status
        if status is not None:
            status = re.sub('[^a-zA-Z\-]', ' ', status.lower())  # remove all non alpha characters
            status = re.sub('days', ' ', status)  # remove days
            status = re.sub('\s+', '-', status.strip())  # replace spaces with dash
            status = re.sub('(^-+)|(-+$)', '', status)

        while True:
            notes = self.my_notes(start_index=index, sort_by=sort_by)

            if notes['result'] != 'success':
                break

            # If the first note has a higher ID, we've passed it
            if group_id is not None and notes['loans'][0][sort_by] > group_id:
                break

            # If the last note has a higher ID, it could be in this record set
            if group_id is None or notes['loans'][-1][sort_by] >= group_id:
                for note in notes['loans']:

                    # Order ID, no match
                    if order_id is not None and note['orderId'] != order_id:
                        continue

                    # Loan ID, no match
                    if loan_id is not None and note['loanId'] != loan_id:
                        continue

                    # Grade, no match
                    if grade is not None and note['rate'][0] != grade:
                        continue

                    # Portfolio, no match
                    if portfolio_name is not None and note['portfolioName'][0] != portfolio_name:
                        continue

                    # Term, no match
                    if term is not None and note['loanLength'] != term:
                        continue

                    # Status
                    if status is not None:
                        # Normalize status message
                        nstatus = re.sub('[^a-zA-Z\-]', ' ', note['status'].lower())  # remove all non alpha characters
                        nstatus = re.sub('days', ' ', nstatus)  # remove days
                        nstatus = re.sub('\s+', '-', nstatus.strip())  # replace spaces with dash
                        nstatus = re.sub('(^-+)|(-+$)', '', nstatus)

                        # No match
                        if nstatus != status:
                            continue

                    # Must be a match
                    found.append(note)

            index += 100

        return found

    def start_order(self):
        """
        Start a new investment order for loans

        Returns
        -------
        lendingclub.Order
            The :class:`lendingclub.Order` object you can use for investing in loan notes.
        """
        order = Order(lc=self)
        return order


class Order:
    """
    Used to create an order for one or more loan notes. It's best to create the Order
    instance through the :func:`lendingclub.LendingClub.start_order()` method (see examples below).

    Parameters
    ----------
    lc : :class:`lendingclub.LendingClub`
        The LendingClub API object that is used to communicate with lendingclub.com

    Examples
    --------

    Invest in a single loan::

        >>> from lendingclub import LendingClub
        >>> lc = LendingClub()
        >>> lc.authenticate()
        Email:test@test.com
        Password:
        True
        >>> order = lc.start_order()           # Start a new investment order
        >>> order.add(654321, 25)              # Add loan 654321 to the order with a $25 investment
        >>> order.execute()                    # Execute the order
        1861879
        >>> order.order_id                     # See the order ID
        1861879
        >>> order.assign_to_portfolio('Foo')   # Assign the loan in this order to a portfolio called 'Foo'
        True

    Invest $25 in multiple loans::

        >>> from lendingclub import LendingClub
        >>> lc = LendingClub(email='test@test.com', password='mysecret')
        >>> lc.authenticate()
        True
        >>> loans = [1234, 2345, 3456]       # Create a list of loan IDs
        >>> order = lc.start_order()          # Start a new order
        >>> order.add_batch(loans, 25)        # Invest $25 in each loan
        >>> order.execute()                   # Execute the order
        1861880

    Invest different amounts in multiple loans::

        >>> from lendingclub import LendingClub
        >>> lc = LendingClub(email='test@test.com', password='mysecret')
        >>> lc.authenticate()
        True
        >>> loans = [
            {'loan_id': 1234, invest_amount: 50},  # $50 in 1234
            {'loan_id': 2345, invest_amount: 25},  # $25 in 2345
            {'loan_id': 3456, invest_amount: 150}  # $150 in 3456
        ]
        >>> order = lc.start_order()
        >>> order.add_batch(loans)                 # Do not pass `batch_amount` parameter this time
        >>> order.execute()                        # Execute the order
        1861880
    """

    loans = None
    order_id = 0
    lc = None

    # These two attributes should [almost] never be used. It assumes that all the loans are already staged
    # and skips clearing and staging and goes straight to investing everything which is staged, either
    # here or on LC.com
    __already_staged = False
    __i_know_what_im_doing = False

    def __init__(self, lc):
        """
        Start a new order
        """
        self.lc = lc
        self.loans = {}
        self.order_id = 0

        self.__already_staged = False
        self.__i_know_what_im_doing = False

    def __log(self, msg):
        self.lc._LendingClub__log(msg)

    def add(self, loan_id, amount):
        """
        Add a loan and amount you want to invest, to your order.
        If this loan is already in your order, it's amount will be replaced
        with the this new amount

        Parameters
        ----------
        loan_id : int or dict
            The ID of the loan you want to add or a dictionary containing a `loan_id` value
        amount : int % 25
            The dollar amount you want to invest in this loan, as a multiple of 25.
        """
        assert amount > 0 and amount % 25 == 0, 'Amount must be a multiple of 25'
        assert type(amount) in (float, int), 'Amount must be a number'

        if type(loan_id) is dict:
            loan = loan_id
            assert 'loan_id' in loan and type(loan['loan_id']) is int, 'loan_id must be a number or dictionary containing a loan_id value'
            loan_id = loan['loan_id']

        assert type(loan_id) in [str, unicode, int], 'Loan ID must be an integer number or a string'
        self.loans[loan_id] = amount

    def update(self, loan_id, amount):
        """
        Update a loan in your order with this new amount

        Parameters
        ----------
        loan_id : int or dict
            The ID of the loan you want to update or a dictionary containing a `loan_id` value
        amount : int % 25
            The dollar amount you want to invest in this loan, as a multiple of 25.
        """
        self.add(loan_id, amount)

    def add_batch(self, loans, batch_amount=None):
        """
        Add a batch of loans to your order.

        Parameters
        ----------
        loans : list
            A list of dictionary objects representing each loan and the amount you want to invest in it (see examples below).
        batch_amount : int, optional
            The dollar amount you want to set on ALL loans in this batch.
            **NOTE:** This will override the invest_amount value for each loan.

        Examples
        --------
        Each item in the loans list can either be a loan ID OR a dictionary object containing `loan_id` and
        `invest_amount` values. The invest_amount value is the dollar amount you wish to invest in this loan.

        **List of IDs**::

            # Invest $50 in 3 loans
            order.add_batch([1234, 2345, 3456], 50)

        **List of Dictionaries**::

            # Invest different amounts in each loans
            order.add_batch([
                {'loan_id': 1234, invest_amount: 50},
                {'loan_id': 2345, invest_amount: 25},
                {'loan_id': 3456, invest_amount: 150}
            ])
        """
        assert batch_amount is None or batch_amount % 25 == 0, 'batch_amount must be a multiple of 25'

        # Add each loan
        assert type(loans) is list, 'The loans property must be a list. (not {0})'.format(type(loans))
        for loan in loans:
            loan_id = loan
            amount = batch_amount

            # Extract ID and amount from loan dict
            if type(loan) is dict:
                assert 'loan_id' in loan, 'Each loan dict must have a loan_id value'
                assert batch_amount or 'invest_amount' in loan, 'Could not determine how much to invest in loan {0}'.format(loan['loan_id'])

                loan_id = loan['loan_id']
                if amount is None and 'invest_amount' in loan:
                    amount = loan['invest_amount']

            assert amount is not None, 'Could not determine how much to invest in loan {0}'.format(loan_id)
            assert amount % 25 == 0, 'Amount to invest must be a multiple of 25 (loan_id: {0})'.format(loan_id)

            self.add(loan_id, amount)

    def remove(self, loan_id):
        """
        Remove a loan from your order

        Parameters
        ----------
        loan_id : int
            The ID of the loan you want to remove
        """
        if loan_id in self.loans:
            del self.loans[loan_id]

    def remove_all(self):
        """
        Remove all loans from your order
        """
        self.loans = {}

    def execute(self, portfolio_name=None):
        """
        Place the order with LendingClub

        Parameters
        ----------
        portfolio_name : string
            The name of the portfolio to add the invested loan notes to.
            This can be a new or existing portfolio name.

        Raises
        ------
        LendingClubError

        Returns
        -------
        int
            The completed order ID
        """
        assert self.order_id == 0, 'This order has already been place. Start a new order.'
        assert len(self.loans) > 0, 'There aren\'t any loans in your order'

        # Place the order
        self.__stage_order()
        token = self.__get_strut_token()
        self.order_id = self.__place_order(token)

        self.__log('Order #{0} was successfully submitted'.format(self.order_id))

        # Assign to portfolio
        if portfolio_name:
            return self.assign_to_portfolio(portfolio_name)

        return self.order_id

    def assign_to_portfolio(self, portfolio_name=None):
        """
        Assign all the notes in this order to a portfolio

        Parameters
        ----------
            portfolio_name -- The name of the portfolio to assign it to (new or existing)

        Raises
        ------
        LendingClubError

        Returns
        -------
        boolean
            True on success
        """
        assert self.order_id > 0, 'You need to execute this order before you can assign to a portfolio.'

        # Get loan IDs as a list
        loan_ids = self.loans.keys()

        # Make a list of 1 order ID per loan
        order_ids = [self.order_id]*len(loan_ids)

        return self.lc.assign_to_portfolio(portfolio_name, loan_ids, order_ids)

    def __stage_order(self):
        """
        Add all the loans to the LC order session
        """

        # Skip staging...probably not a good idea...you've been warned
        if self.__already_staged is True and self.__i_know_what_im_doing is True:
            self.__log('Not staging the order...I hope you know what you\'re doing...'.format(len(self.loans)))
            return

        self.__log('Staging order for {0} loan notes...'.format(len(self.loans)))

        # Create a fresh order session
        self.lc.session.clear_session_order()

        #
        # Stage all the loans to the order
        #
        loan_ids = self.loans.keys()
        self.__log('Staging loans {0}'.format(loan_ids))

        # LendingClub requires you to search for the loans before you can stage them
        f = FilterByLoanID(loan_ids)
        results = self.lc.search(f, limit=len(self.loans))
        if len(results['loans']) == 0 or results['totalRecords'] != len(self.loans):
            raise LendingClubError('Could not stage the loans. The number of loans in your batch does not match totalRecords. {0} != {1}'.format(len(self.loans), results['totalRecords']), results)

        # Stage each loan
        for loan_id, amount in self.loans.iteritems():
            payload = {
                'method': 'addToPortfolio',
                'loan_id': loan_id,
                'loan_amount': amount,
                'remove': 'false'
            }
            response = self.lc.session.get('/data/portfolio', query=payload)
            json_response = response.json()

            # Ensure it was successful before moving on
            if not self.lc.session.json_success(json_response):
                raise LendingClubError('Could not stage loan {0} on the order: {1}'.format(loan_id, response.text), response)

        #
        # Add all staged loans to the order
        #
        payload = {
            'method': 'addToPortfolioNew'
        }
        response = self.lc.session.get('/data/portfolio', query=payload)
        json_response = response.json()

        if self.lc.session.json_success(json_response):
            self.__log(json_response['message'])
            return True
        else:
            raise self.__log('Could not add loans to the order: {0}'.format(response.text))
            raise LendingClubError('Could not add loans to the order', response.text)

    def __get_strut_token(self):
        """
        Move the staged loan notes to the order stage and get the struts token
        from the place order HTML.
        The order will not be placed until calling _confirm_order()

        Returns
        -------
        dict
            A dict with the token name and value
        """

        try:
            # Move to the place order page and get the struts token

            response = self.lc.session.get('/portfolio/placeOrder.action')
            soup = BeautifulSoup(response.text, "html5lib")


            # Example HTML with the stuts token:
            """
            <input type="hidden" name="struts.token.name" value="token" />
            <input type="hidden" name="token" value="C4MJZP39Q86KDX8KN8SBTVCP0WSFBXEL" />
            """
            # 'struts.token.name' defines the field name with the token value

            strut_tag = None
            strut_token_name = soup.find('input', {'name': 'struts.token.name'})
            if strut_token_name and strut_token_name['value'].strip():

                # Get form around the strut.token.name element
                form = soup.form # assumed
                for parent in strut_token_name.parents:
                    if parent and parent.name == 'form':
                        form = parent
                        break

                # Get strut token value
                strut_token_name = strut_token_name['value']
                strut_tag = soup.find('input', {'name': strut_token_name})
                if strut_tag and strut_tag['value'].strip():
                    return {'name': strut_token_name, 'value': strut_tag['value'].strip()}

            # No strut token found
            self.__log('No struts token! HTML: {0}'.format(response.text))
            raise LendingClubError('No struts token. Please report this error.', response)

        except Exception as e:
            self.__log('Could not get struts token. Error message: {0}'.format(str(e)))
            raise LendingClubError('Could not get struts token. Error message: {0}'.format(str(e)))

    def __place_order(self, token):
        """
        Use the struts token to place the order.

        Parameters
        ----------
        token : string
            The struts token received from the place order page

        Returns
        -------
        int
            The completed order ID.
        """
        order_id = 0
        response = None

        if not token or token['value'] == '':
            raise LendingClubError('The token parameter is False, None or unknown.')

        # Process order confirmation page
        try:
            # Place the order
            payload = {}
            if token:
                payload['struts.token.name'] = token['name']
                payload[token['name']] = token['value']
            response = self.lc.session.post('/portfolio/orderConfirmed.action', data=payload)

            # Process HTML for the order ID
            html = response.text
            soup = BeautifulSoup(html)

            # Order num
            order_field = soup.find(id='order_id')
            if order_field:
                order_id = int(order_field['value'])

            # Did not find an ID
            if order_id == 0:
                self.__log('An investment order was submitted, but a confirmation ID could not be determined')
                raise LendingClubError('No order ID was found when placing the order.', response)
            else:
                return order_id

        except Exception as e:
            raise LendingClubError('Could not place the order: {0}'.format(str(e)), response)


class LendingClubError(Exception):
    """
    An error occurred.
    If the error was the result of an API call, the response attribute will contain the HTTP
    requests response object that was used to make the call to LendingClub.

    Parameters
    ----------
    value : string
        The error message
    response : `requests.Response <http://docs.python-requests.org/en/latest/api/#requests.Response>`_
    """
    response = None

    def __init__(self, value, response=None):
        self.value = value
        self.response = response

    def __str__(self):
        return repr(self.value)
