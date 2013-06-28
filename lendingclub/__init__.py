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
from lendingclub.filters import Filter
from lendingclub.session import Session


class LendingClub:
    logger = None
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

    def get_portfolio_list(self):
        """
        Return the list of portfolio names from the server
        """
        folios = []
        response = self.session.get('/data/portfolioManagement?method=getLCPortfolios')
        json_response = response.json()

        # Get portfolios and create a list of names
        if self.session.json_success(json_response):
            folios = json_response['results']

        return folios

    def search(self, filters=None, start_index=0):
        """
        Sends the filters to the Browse Notes API and returns a list of the notes found or False on error.

        Parameters:
            filters -- The filters to use to search for notes
            start_index -- Only 100 records will be returned at a time, so use this to start at a later index.
                            For example, to get the next 100, set start_index to 100
        """
        assert filter is None or type(filters) is Filter, 'filter is not a lendingclub.search.Filter'

        # Set filters
        if filters is None:
            filters = 'default'
        else:
            filters = filter.search_string()
        payload = {
            'method': 'search',
            'filter': filters,
            'startindex': start_index,
            'pagesize': 100
        }

        # Make request
        response = self.session.post('/browse/browseNotesAj.action', data=payload)
        json_response = response.json()

        if self.session.json_success(json_response):
            results = json_response['searchresult']

            # Normalize results by converting loanGUID -> loan_id
            for loan in results['loans'].iteritems():
                loan['loan_id'] = loan['loanGUID']

            # Validate that fractions do indeed match the filters
            filters.validate(results['loans'])

            return results

        return False

    def build_portfolio(self, cash, min_percent=0, max_percent=25, filters=None):
        """
        Returns a list of loan notes that are diversified by your min/max percent request and filters.
        If you want to invest in these loan notes, you will have to start and order and use add_batch to
        add all the loan fragments to them.

        Parameters:
            cash -- The amount you want to invest in a portfolio
            min/max_percent -- Matches a portfolio with a average expected APR between these two numbers.
                               If there are multiple options, the one closes to the max will be chosen.
            filters -- (optional) The filters to use to search for notes

        Returns a dict representing a new portfolio or False if nothing was found.
        """
        assert filters is None or type(filters) is Filter, 'filter is not a lendingclub.search.Filter'

        # Set filters
        if filters is None:
            filter_str = 'default'
            max_per = 25
        else:
            filter_str = filter.search_string()
            max_per = filters['max_per_note']

        # Start a new order
        self.session.clear_session_order()

        # Make request
        payload = {
            'amount': cash,
            'max_per_note': max_per,
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
            filters.validate(fractions)

            # Reset portfolio search session
            self.session.clear_session_order()

            return match_option
        else:
            raise LendingClubError('Could not find any diversified investment options', response)

        return False

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
            loan_id -- The ID of the loan you want to add
            amount -- The dollar amount you want to invest in this loan.
        """
        assert amount > 0 and amount % 25 == 0, 'Amount must be a multiple of 25'
        assert type(amount) in (float, int), 'Amount must be a number'
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

    def execute(self, portfolio=None):
        """
        Place the order with LendingClub

        Parameters:
            portfolio -- The name of the portfolio to add the invested loan notes to.
                         This can be a new or existing portfolio name.

        Returns the order ID
        """
        assert self.order_id == 0, 'This order has already been place. Start a new order.'

        # Place the order
        self.__stage_order()
        token = self.__get_strut_token()
        self.order_id = self.__place_order(token)

        self.__log('Order #{0} was successfully submitted'.format(self.order_id))

        # Assign to portfolio
        if portfolio is not None:
            self.__assign_to_portfolio(portfolio)

        return self.order_id

    def __stage_order(self):
        """
        Add all the loans to the LC order session
        """

        # Create a fresh order session
        self.lc.session.clear_session_order()

        #
        # Stage all the loans to the order
        #
        for loan_id, amount in self.loans.iteritems():
            payload = {
                'loan_id': loan_id,
                'investment_amount': amount,
                'remove': 'false'
            }
            response = self.lc.session.post('/browse/updateLSRAj.action', data=payload)
            json_response = response.json()

            # Ensure it was successful before moving on
            if not self.lc.session.json_success(json_response):
                raise LendingClubError('Could not stage loan {0} on the order: {1}'.format(loan_id), response)

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
            if strut_tag:
                return strut_tag['value']
            else:
                self.__log('No struts token! {0}', response.text)
                raise LendingClubError('Could not find the struts token to place order with', response)

        except Exception as e:
            self.__log('Could not get struts token. Error message: {0}'.filter(str(e)))
            raise LendingClubError('Could not get struts token. Error message: {0}'.filter(str(e)))

    def __place_order(self, token):
        """
        Use the struts token to place the order.

        Parameters:
            token -- The struts token received from the place order page

        Returns the order ID.
        """
        order_id = 0
        response = None

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

    def __assign_to_portfolio(self, portfolio):
        """
        Assign the order to a named portfolio, either new or existing.

        Parameters:
            portfolio -- The name of the portfolio to assign the order to

        Returns True
        """
        assert self.order_id > 0, 'The order has not been processed yet'

        response = None

        # Get loan IDs as a list
        loan_ids = []
        for loan_id, amount in self.loans.iteritems():
            loan_ids.append(loan_id)

        # Data
        order_ids = [self.order_id]*len(loan_ids)  # Make a list of 1 order ID per loan
        post = {
            'loan_id': loan_ids,
            'record_id': loan_ids,
            'order_id': order_ids
        }
        query = {
            'method': 'createLCPortfolio',
            'lcportfolio_name': portfolio
        }

        # Is it an existing portfolio
        existing = self.lc.get_portfolio_list()
        for folio in existing:
            if folio['portfolioName'] == portfolio:
                query['method'] = 'addToLCPortfolio'

        # Send
        response = self.lc.session.post('/data/portfolioManagement', query=query, data=post)
        json_response = response.json()

        # Failed
        if not self.lc.session.json_success(json_response):
            raise LendingClubError('Could not assign order #{0} to portfolio \'{1}\''.format(str(self.order_id), portfolio), response)

        # Success
        else:

            # Assigned to another portfolio, for some reason, raise warning
            if 'portfolioName' in json_response and json_response['portfolioName'] != portfolio:
                raise LendingClubError('Added order #{0} to portfolio "{1}" - NOT - "{2}", and I don\'t know why'.format(str(self.order_id), json_response['portfolioName'], portfolio))

            # Assigned to the correct portfolio
            else:
                self.__log('Added order #{0} to portfolio "{1}"'.format(str(self.order_id), portfolio))

            return True

        return False


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
