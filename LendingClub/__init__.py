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

import logging
from LendingClub import util


class LendingClub:
    logger = None

    def __init__(self, email=None, password=None, logger=None):
        if email is not None:
            self.authenticate(email, password)

        # Create a null logger
        if logger is None:
            logger = logging.getLogger('lendingclubapi')
            logger.setLevel(logging.DEBUG)
            logHandler = logging.NullHandler()
            logger.addHandler(logHandler)

        self.set_logger(logger)

    def set_logger(self, logger):
        self.logger = logger
        util.set_logger(self.logger)

    def authenticate(self, email, password):
        """
        Attempt to authenticate the user.
        Returns True/False
        """
        try:
            if util.start_session(email, password):
                self.authed = True
                return True
        except Exception as e:
            raise e
        raise Exception('An unknown error occurred')

    def version(self):
        """
        Return the version number of the Lending Club Investor tool
        """
        this_path = os.path.dirname(os.path.realpath(__file__))
        version_file = os.path.join(this_path, 'VERSION')
        return open(version_file).read()

    def browse_notes(self, filter):
        """
        Sends the filters to the Browse Notes API and returns a JSON of the notes found
        """
        # Get all investment options
        filters = filter.json_string()
        if filters is False:
            filters = 'default'
        payload = {
            'method': 'search',
            'filter': filters
        }
        response = util.post_url('/browse/browseNotesAj.action', data=payload)
        jsonRes = response.json()
        return jsonRes

    def search_for_investment_portfolios(self, filters, cash):
        """
        Do a search for portfolios of loan notes based on the filters and cash you want to invest.
        """
        try:

            # Get all investment options
            filters = filter.json_string()
            if filters is False:
                filters = 'default'
            payload = {
                'amount': cash,
                'max_per_note': filters['max_per_note'],
                'filter': filters
            }
            response = util.post_url('/portfolio/lendingMatchOptionsV2.action', data=payload)
            resJson = response.json()

            if resJson['result'] == 'success' and 'lmOptions' in resJson:
                return resJson['lmOptions']
            else:
                print payload['filter']
                print response.json()
                self.logger.error('Could not get investment portfolio options! Server responded with: {0}'.format(response.text))
                return False

        except Exception as e:
            self.logger.error(str(e))

        return False

    def get_strut_token(self):
        """
        Get the struts token from the place order page
        """
        strutToken = ''
        try:
            response = util.get_url('/portfolio/placeOrder.action')
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
            util.get_url('/portfolio/recommendPortfolio.action', params=payload)

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
            response = util.post_url('/portfolio/orderConfirmed.action', data=payload)

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
                response = util.post_url('/data/portfolioManagement', params=paramData, data=postData)
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

    def get_cash_balance(self):
        """
        Returns the cash balance available to invest
        """
        cash = -1
        try:
            response = util.get_url('/browse/cashBalanceAj.action')
            jsonRes = response.json()

            if jsonRes['result'] == 'success':
                self.logger.debug('Cash available: {0}'.format(jsonRes['cashBalance']))
                cash = util.currency_to_float(jsonRes['cashBalance'])
            else:
                self.logger.error('Could not get cash balance: {0}'.format(response.text))

        except Exception as e:
            self.logger.error('Could not get the cash balance on the account: Error: {0}\nJSON: {1}'.format(str(e), response.text))

        return cash

    def get_portfolio_list(self):
        """
        Return the list of portfolio names from the server
        """
        foliosNames = []
        try:
            response = util.get_url('/data/portfolioManagement?method=getLCPortfolios')
            jsonRes = response.json()

            # Get portfolios and create a list of names
            if jsonRes['result'] == 'success':
                folios = jsonRes['results']
                for folio in folios:
                    foliosNames.append(folio['portfolioName'])

        except Exception as e:
            self.logger.warning('Could not get list of portfolios for this account. Error message: {0}'.format(str(e)))

        return foliosNames



class LendingClubError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
