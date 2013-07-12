#!/usr/bin/env python

"""
An API for LendingClub.com that let's you access your account, search for notes
and invest.
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
from bs4 import BeautifulSoup
from lendingclub.filters import Filter, FilterByLoanID, SavedFilter
from lendingclub.session import Session


class LendingClub:
    __logger = None
    session = Session()
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
        """
        self.__logger = logger
        self.session.set_logger(self.__logger)

    def version(self):
        """
        Return the version number of the Lending Club Investor tool
        """
        this_path = os.path.dirname(os.path.realpath(__file__))
        version_file = os.path.join(this_path, 'VERSION')
        return open(version_file).read()

    def authenticate(self, email=None, password=None):
        """
        Attempt to authenticate the user.
        Returns True or raises an exception
        """
        if self.session.authenticate(email, password):
            return True

    def is_site_available(self):
        """
        Returns true if we can access LendingClub.com
        This is also a simple test to see if there's an internet connection
        """
        return self.session.is_site_available()

    def get_cash_balance(self):
        """
        Returns the account cash balance available for investing or False
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

        return cash

    def get_investable_balance(self):
        """
        Returns the amount of money you have to invest.
        Loans are multiples of $25, so this is your total cash balance, adjusted to be a multiple of 25.
        """
        cash = int(self.get_cash_balance())
        while cash % 25 != 0:
            cash -= 1
        return cash

    def get_portfolio_list(self, names_only=False):
        """
        Return the list of portfolio names from the server

        Parameters:
            names_only -- Return a list of portfolio names, instead of portfolio objects

        Returns A list of portfolios
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
        Return a list of all your saved filters and their IDs
        """
        return SavedFilter.all_filters(self)

    def get_saved_filter(self, filter_id):
        """
        Load a saved filter by ID
        """
        return SavedFilter(self, filter_id)

    def assign_to_portfolio(self, portfolio_name, loan_id, order_id):
        """
        Assign a note to a named portfolio. loan_id and order_id can be either
        integer values or lists. If choosing lists, they both should be the same length
        and match up. For example, order_id[5] must be the order_id for loan_id[5]

        Parameters:
            portfolio_name -- The name of the portfolio to assign it to (new or existing)
            loan_id -- The ID (or list of IDs) of the note to assign to a portfolio
            order_id -- The ID (or list of IDs) of the order this loan note was invested with.
                        You can find this in the dict returned from get_note()

        Returns True on success
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

    def search(self, filters=None, start_index=0):
        """
        Sends the filters to the Browse Notes API and returns a list of the notes found or False on error.

        Parameters:
            filters -- The filters to use to search for notes
            start_index -- Only 100 records will be returned at a time, so use this to start at a later index.
                            For example, to get the next 100, set start_index to 100

        Returns a dictionary object with the list of matching loans under the 'loans' key.
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
            'pagesize': 100
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
        If you want to invest in these loan notes, you will have to start and order and use add_batch to
        add all the loan fragments to them.

        Parameters:
            cash -- The amount you want to invest in a portfolio
            max_per_note -- The maximum dollar amount you want to invest per note. Must be 25 or above
            min/max_percent -- Matches a portfolio with a average expected APR between these two numbers.
                               If there are multiple options, the one closes to the max will be chosen.
            filters -- (optional) The filters to use to search for notes
            automatically_invest -- (default False) If you want the tool to create an order and automatically
                                    invest the portfolio that matches your filter.
            do_not_clear_staging -- Similar to automatically_invest, don't do this unless you know what you're doing.
                                    Setting this to True stops the method from clearing the loan staging area before returning

        Returns a dict representing a new portfolio or False if nothing was found.
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

            if len(fractions) > 0:
                match_option['loan_fractions'] = fractions
            else:
                self.__log('Couldn\'t load the loan fractions for the selected portfolio')
                return False

            # Validate that fractions do indeed match the filters
            if filters is not None:
                filters.validate(fractions)

            # Not investing -- reset portfolio search session and return
            if automatically_invest is not True:
                if do_not_clear_staging is not True:
                    self.session.clear_session_order()

            # Invest in this porfolio
            elif automatically_invest is True: # just to be sure
                order = self.start_order()

                # This should probably only be ever done here...ever.
                order._Order__already_staged = True
                order._Order__i_know_what_im_doing = True

                order.add_batch(match_option)
                order_id = order.execute()
                match_option['order_id'] = order_id

            return match_option
        else:
            raise LendingClubError('Could not find any portfolio options that match your filters', response)

        return False

    def my_notes(self, start_index=0, per_page=100, get_all=False, sort_by='loanId', sort_dir='asc'):
        """
        Return all the loan notes you've invested in. By default it'll return 100 results at a time.

        Parameters
            start_index -- The result index to start on. For example, if per_page is set to 100,
                            to get results 200 - 300, start_index should be set to 200.
            per_page -- The number of notes you want returned per request
            get_all -- Return all results, instead of paged.

        Returns a dictionary with a list of matching notes on the 'loans' key
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
                'pagesize': per_page,
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
                index += per_page

            # End
            else:
                break

        return notes

    def get_note(self, note_id):
        """
        Get a note that you've invested in by ID

        Parameters:
            note_id -- The note ID

        Returns a matching note or False
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
        Passing no parameters is like calling `my_notes(get_all=True)`

        Parameters:
            loan_id -- Search for notes that are for a specific loan
            order_id -- Search for notes from a particular order
            grade -- Match loan grades (A - G)
            portfolio_name -- Search for notes in a portfolio with this name (case sensitive)
            status -- The funding status string: issued, in-review, in-funding, current, charged-off, late, in-grace-period, fully-paid)
            term -- Term length, either 60 or 36 (for 5 year and 3 year, respectively)

        Returns a dictionary with a list of matching notes on the 'loans' key
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
        Start a new investment order or loans
        """
        order = Order(lc=self)
        return order


class Order:
    """
    Manages an investment order
    """

    loans = {}
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

        Parameters:
            lc -- The LendingClub API object
        """
        self.lc = lc

    def __log(self, msg):
        self.lc._LendingClub__log(msg)

    def add(self, loan_id, amount):
        """
        Add a loan and amount you want to invest, to your order.
        If this loan is already in your order, it's amount will be replaced
        with the this new amount

        Parameters:
            loan_id -- The ID of the loan you want to add (or a dictionary containing a loan_id value)
            amount -- The dollar amount you want to invest in this loan.
        """
        assert amount > 0 and amount % 25 == 0, 'Amount must be a multiple of 25'
        assert type(amount) in (float, int), 'Amount must be a number'

        if type(loan_id) is dict:
            loan = loan_id
            assert 'loan_id' in loan and type(loan['loan_id']) is int, 'loan_id must be a number or dictionary containing a loan_id value'
            loan_id = loan['loan_id']

        assert type(loan_id) is int, 'loan_id must be a number'

        self.loans[loan_id] = amount

    def update(self, loan_id, amount):
        """
        Update a loan in your order with this new amount

        Parameters:
            loan_id -- The ID of the loan you want to add
            amount -- The dollar amount you want to invest in this loan.
        """
        self.add(loan_id, amount)

    def add_batch(self, loans, batch_amount=None):
        """
        Add a batch of loans to your order. Each loan in the list must be a dictionary
        object with at least a 'loan_id' and a 'invest_amount' value. The invest_amount
        value is the dollar amount you wish to invest in this loan.

        Parameters:
            loans -- A list of dictionary objects representing each loan and the amount you want to invest in it.
            batch_amount -- The dollar amount you want to set on ALL loans in this batch.
                            NOTE: This will override the invest_amount value for each loan.
        """
        assert batch_amount is None or batch_amount % 25 == 0, 'batch_amount must be a multiple of 25'

        # Loans is an object, perhaps it's from build_portfolio and has a loan_fractions list
        if type(loans) is dict and 'loan_fractions' in loans:
            assert 'order_id' not in loans, 'This batch of loans has already been ordered'
            loans = loans['loan_fractions']

        # Add each loan
        assert type(loans) is list, 'The loans property must be a list'
        for loan in loans:
            amount = batch_amount if batch_amount else loan['invest_amount']

            assert amount % 25 == 0, 'Loan invest_amount must be a multiple of 25'
            self.add(loan['loan_id'], amount)

    def remove(self, loan_id):
        """
        Remove a loan from your order

        Parameters:
            loan_id -- The ID of the loan to remove from your order
        """
        if loan_id in self.loans:
            del self.loans[loan_id]

    def execute(self, portfolio_name=None):
        """
        Place the order with LendingClub

        Parameters:
            portfolio_name -- The name of the portfolio to add the invested loan notes to.
                              This can be a new or existing portfolio name.

        Returns the order ID or raises an exception
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

        Parameters:
            portfolio_name -- The name of the portfolio to assign it to (new or existing)

        Returns True on success
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
        for loan_id, amount in self.loans.iteritems():
            self.__log(' - staging loan {0}'.format(loan_id))

            # You have to search before you can stage
            f = FilterByLoanID(loan_id)
            results = self.lc.search(f)
            if len(results['loans']) == 0:
                raise LendingClubError('Could not find a loan for ID {0}: {1}'.format(loan_id, results.text), results)

            # Stage
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
        Move the staged loan notes to the order stage and get the struts token.
        The order will not be placed until calling _confirm_order()
        """

        try:
            # Move to the place order page and get the struts token
            response = self.lc.session.get('/portfolio/placeOrder.action')
            soup = BeautifulSoup(response.text, "html5lib")

            strut_tag = soup.find('input', {'name': 'struts.token'})
            if strut_tag and strut_tag['value'].strip():
                return strut_tag['value'].strip()
            else:
                self.__log('No struts token! {0}', response.text)
                raise LendingClubError('Could not find the struts token to place order with', response)

        except Exception as e:
            self.__log('Could not get struts token. Error message: {0}'.format(str(e)))
            raise LendingClubError('Could not get struts token. Error message: {0}'.format(str(e)))

    def __place_order(self, token):
        """
        Use the struts token to place the order.

        Parameters:
            token -- The struts token received from the place order page

        Returns the order ID.
        """
        order_id = 0
        response = None

        if not token or token == '':
            raise LendingClubError('The token parameter is False, None or unknown.')

        # Process order confirmation page
        try:
            # Place the order
            payload = {}
            if token:
                payload['struts.token.name'] = 'struts.token'
                payload['struts.token'] = token
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
    An error with the LendingClub API.
    If the error was the result of an API call, the response attribute
    will contain the HTTP requests response object that was used to make the call to LendingClub.
    """
    response = None

    def __init__(self, value, response=None):
        self.value = value
        self.response = response

    def __str__(self):
        return repr(self.value)
