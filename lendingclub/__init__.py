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
from lendingclub.search import Filter
from lendingclub.session import Session


class LendingClub:
    logger = None
    session = Session()

    def __init__(self, email=None, password=None, logger=None):
        self.session = Session(email, password)

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
        Set a logger to debug to
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

            if json_response['result'] == 'success':
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
        if json_response['result'] == 'success':
            folios = json_response['results']

        return folios

    def search(self, filters=None):
        """
        Sends the filters to the Browse Notes API and returns a list of the notes found or False on error.

        Attributes:
            filters -- The filters to use to search for notes
        """
        assert filter is None or type(filters) is Filter, 'filter is not a lendingclub.search.Filter'

        # Set filters
        if filters is None:
            filters = 'default'
        else:
            filters = filter.search_string()
        payload = {
            'method': 'search',
            'filter': filters
        }

        # Make request
        response = self.session.post('/browse/browseNotesAj.action', data=payload)
        json_response = response.json()

        if 'result' in json_response and json_response['result'] == 'success':
            return json_response['searchresult']

        return False

    def build_portfolio(self, cash, min_percent=0, max_percent=25, filters=None):
        """
        Returns a list of loan notes that are diversified by your min/max percent request and filters.

        This is the same as selecting a portfolio from the Invest page (https://www.lendingclub.com/portfolio/autoInvest.action.)
        except that it will choose an allotment for you. The reason is because LendingClub saves the search and
        options to the user session. This session could be changed or overridden if the user is browsing
        the website as they use the API.

        Attributes:
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

        # Start a new portfolio
        self.session.get('/portfolio/confirmStartNewPortfolio.action')

        # Make request
        payload = {
            'amount': cash,
            'max_per_note': max_per,
            'filter': filter_str
        }
        response = self.session.post('/portfolio/lendingMatchOptionsV2.action', data=payload)
        json_response = response.json()

        # Options were found
        if 'result' in json_response and json_response['result'] == 'success' and 'lmOptions' in json_response:
            options = json_response['lmOptions']

            # Nothing found
            if type(options) is not list or json_response['numberTicks'] == 0:
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
                return False

            # Mark this portfolio for investing (in order to get a list of all notes)
            payload = {
                'order_amount': cash,
                'lending_match_point': match_index,
                'lending_match_version': 'v2'
            }
            self.session.get('/portfolio/recommendPortfolio.action', query=payload)

            # Get all loan fractions
            frac_response = self.session.get('/data/portfolio', query={'method': 'getPortfolio'})
            frac_json = frac_response.json()
            if 'loanFractions' in frac_json and len(frac_json['loanFractions']) > 0:
                match_option['loan_fractions'] = frac_json['loanFractions']
            else:
                return False

            # Reset portfolio search session
            self.session.get('/portfolio/confirmStartNewPortfolio.action')

            return match_option
        else:
            raise LendingClubError('Could not find any diversified investment options', response.text)

        return False

    def __get_strut_token(self):
        """
        Get the struts token from the place order HTML
        """
        strutToken = ''
        try:
            response = self.session.get('/portfolio/placeOrder.action')
            soup = BeautifulSoup(response.text, "html5lib")
            strutTokenTag = soup.find('input', {'name': 'struts.token'})
            if strutTokenTag:
                strutToken = strutTokenTag['value']
        except Exception as e:
            self.logger.warning('Could not get struts token. Error message: {0}'.filter(str(e)))

        return strutToken

    def prepare_investment_order(self, cash, investmentOption):
        """
        Submit an investment request for with an investment portfolio option selected from get_investment_option()
        """

        # Place the order
        try:
            if 'optIndex' not in investmentOption:
                self.logger.error('The \'optIndex\' key is not present in investmentOption passed to sendInvestment()! This value is set when selecting the option from get_investment_option()')
                return False

            # Prepare the order (don't process response)
            payload = {
                'order_amount': cash,
                'lending_match_point': investmentOption['optIndex'],
                'lending_match_version': 'v2'
            }
            self.session.get('/portfolio/recommendPortfolio.action', query=payload)

            # Get struts token
            return self.get_strut_token()

        except Exception as e:
            self.logger.error('Could not complete your order (although, it might have gone through): {0}'.format(str(e)))

        return False

    def place_order(self, strutToken, cash, investmentOption):
        """
        Place the order and get the order number, loan ID from the resulting HTML -- then assign to a portfolio
        The cash parameter is the amount of money invest in this order
        The investmentOption parameter is the investment portfolio returned by get_investment_option()
        """

        orderID = 0
        loanIDs = []

        # Process order confirmation page
        try:
            payload = {}
            if strutToken:
                payload['struts.token.name'] = 'struts.token'
                payload['struts.token'] = strutToken
            response = self.session.post('/portfolio/orderConfirmed.action', data=payload)

            # Process HTML
            html = response.text
            soup = BeautifulSoup(html)

            # Order num
            orderField = soup.find(id='order_id')
            if orderField:
                orderID = int(orderField['value'])

            # Load ID
            loanTags = soup.find_all('td', {'class': 'loan_id'})
            for tag in loanTags:
                loanIDs.append(int(tag.text))

            # Print status message
            if orderID == 0:
                self.logger.error('An investment order was submitted, but a confirmation could not be determined')
            else:
                self.logger.info('Order #{0} was successfully submitted for ${1} at {2}%'.format(orderID, cash, investmentOption['percentage']))

            # Print order summary
            orderSummary = self.get_option_summary(investmentOption)
            self.logger.info(orderSummary)

        except Exception as e:
            self.logger.error('Could not get your order number or loan ID from the order confirmation. Err Message: {0}'.format(str(e)))

        return (orderID, loanIDs)

    def assign_to_portfolio(self, orderID=0, loanIDs=[], returnJson=False):
        """
        Assign an order to a the portfolio named in the investing dictionary.
        If returnJson is True, this method will return the JSON returned from the server (this is primarily for unit testing)
        Otherwise it returns the name of the portfolio the order was assigned to or False
        """

        # Assign to portfolio
        resText = ''
        try:
            if not self.settings['portfolio']:
                return True

            if len(loanIDs) != 0 and orderID != 0:

                # Data
                orderIDs = [orderID]*len(loanIDs)  # 1 order ID per record
                postData = {
                    'loan_id': loanIDs,
                    'record_id': loanIDs,
                    'order_id': orderIDs
                }
                paramData = {
                    'method': 'addToLCPortfolio',
                    'lcportfolio_name': self.settings['portfolio']
                }

                # New portfolio
                folioList = self.get_portfolio_list()
                if self.settings['portfolio'] not in folioList:
                    paramData['method'] = 'createLCPortfolio'

                # Send
                response = self.session.post('/data/portfolioManagement', query=paramData, data=postData)
                resText = response.text
                resJson = response.json()

                if returnJson is True:
                    return resJson

                # Failed if the response is not 200 or JSON result is not success
                if response.status_code != 200 or resJson['result'] != 'success':
                    self.logger.error('Could not assign order #{0} to portfolio \'{1}: Server responded with {2}\''.format(str(orderID), self.settings['portfolio'], response.text))

                # Success
                else:

                    # Assigned to another portfolio, for some reason, raise warning
                    if 'portfolioName' in resJson and resJson['portfolioName'] != self.settings['portfolio']:
                        self.logger.warning('Added order #{0} to portfolio "{1}" - NOT - "{2}", and I don\'t know why'.format(str(orderID), resJson['portfolioName'], self.settings['portfolio']))
                    # Assigned to the correct portfolio
                    else:
                        self.logger.info('Added order #{0} to portfolio "{1}"'.format(str(orderID), self.settings['portfolio']))

                    return resJson['portfolioName']

        except Exception as e:
            self.logger.error('Could not assign order #{0} to portfolio \'{1}\': {2} -- {3}'.format(orderID, self.settings['portfolio'], str(e), resText))

        return False


class LendingClubError(Exception):
    """
    An error with the LendingClub API.
    If the error was the result of an API call, the response attribute
    will contain the server response text.
    """
    response = None

    def __init__(self, value, response=None):
        self.value = value
        self.response = response

    def __str__(self):
        return repr(self.value)
