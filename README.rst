Lending Club API
================

A stand-alone python API for Lending Club. In a nutshell, this module lets you check your cash balance, search for notes, build orders and invest.

It is still a work in progress but I expect the first stable release by the end of July. The current release works well but may have some bugs -- use at your own risk.

The code has been ported out of the `LendingClub Auto Investor <https://github.com/jgillick/LendingClubAutoInvestor>`_ project.

Disclaimer
----------

I have tested this tool to the best of my ability, but understand that it may have bugs. Use at your own risk!

Requirements
------------

The following Python libraries are required:

* requests
* beautifulsoup4
* html5lib
* pybars

These can automatically be installed with `pip <http://www.pip-installer.org/en/latest/>`_::

    sudo pip install requests beautifulsoup4 html5lib pybars

Install
-------

To install, run::

    sudo python ./setup.py install


Examples
--------

Here's a step-by-step example of searching for grade B loans and investing $25 in the first one::

    >>> from lendingclub import LendingClub
    >>> from lendingclub.filters import Filter
    >>> lc = LendingClub()
    >>> lc.authenticate()
    Email:test@test.com
    Password:
    True
    >>> filters = Filter()
    >>> filters['grades']['B'] = True      # Filter for only B grade loans
    >>> results = lc.search(filters)       # Search using this filter
    >>> len(results['loans'])              # See how many results returned
    100
    >>> results['loans'][0]['loan_id']     # See the loan_id of the first loan
    1763030
    >>> order = lc.start_order()           # Start a new investment order
    >>> order.add(1763030, 25)             # Add the first loan to the order with a $25 investment
    >>> order.execute()                    # Execute the order
    1861879
    >>> order.order_id                     # See the order ID
    1861879
    >>> order.assign_to_portfolio('Foo')   # Assign the loans in this order to a portfolio called 'Foo'
    True

Create a diversified portfolio of loan notes. Here we want to invest $400 in a portfolio with only B, C, D and E grade notes with an average overall return between 17% - 19%::

    >>> from lendingclub import LendingClub
    >>> from lendingclub.filters import Filter
    >>> lc = LendingClub()
    >>> lc.authenticate()
    Email:test@test.com
    Password:
    True
    >>> filters = Filter()                # Set the filters
    >>> filters['grades']['B'] = True     # See Pro Tips for a shorter way to do this
    >>> filters['grades']['C'] = True
    >>> filters['grades']['D'] = True
    >>> filters['grades']['E'] = True
    >>> lc.get_cash_balance()             # See the cash you have available for investing
    463.80000000000001
                                          # Find a portfolio to invest in ($400 & between 17-19%)
    >>> portfolio = lc.build_portfolio(400, 17.0, 19.0, filters)
    >>> len(portfolio['loan_fractions'])  # See how many loans are in this portfolio
    16
    >>> order = lc.start_order()          # Start a new order
    >>> order.add_batch(portfolio)        # Add the portfolio to the order
    >>> order.execute()                   # Execute the order
    1861880

Get a list of the loan notes that you've invested in (by default this will only return 100 at a time)::

    >>> from lendingclub import LendingClub
    >>> lc = LendingClub()
    >>> lc.authenticate()
    Email:test@test.com
    Password:
    True
    >>> notes = lc.get_notes()                  # Get the first 100 loan notes
    >>> len(notes['loans'])
    100
    >>> notes['total']                          # See the total number of loan notes you have
    630
    >>> notes = lc.get_notes(start_index=100)   # Get the next 100 loan notes
    >>> len(notes['loans'])
    100
    >>> notes = lc.get_notes(get_all=True)       # Get all notes in one request (may be slow)
    >>> len(notes['loans'])
    630

Pro Tips
--------

You can define some of your filters in the init line::

    filters = Filter({'grades': {'B': True, 'C': True, 'D': True, 'E': True}})

This will merge these values with the rest of the filters.

License
=======
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
