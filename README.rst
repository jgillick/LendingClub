Lending Club API
================

An attempt to extract the API from the `LendingClub Auto Investor <https://github.com/jgillick/LendingClubAutoInvestor>`_ project into a standalone API module. The currently committed code does not work yet, but should soon. Until then, you should be able to use the modules from the auto investor project.

Example
=======

Here's a step-by-step example of searching for grade B loans and investing in the first one:

    >>> from lendingclub import LendingClub
    >>> from lendingclub.filters import Filters
    >>> lc = LendingClub()
    >>> lc.authenticate()
    Email:test@test.com
    Password:
    True
    >>> filters = Filters()
    >>> filters['grades']['B'] = True      # Search for only B grade loans
    >>> results = lc.search(filters)
    >>> len(results['loans'])              # See how many results returned
    >>> results['loans'][0]['loan_id']     # See the loan_id of the first loan
    >>> order = lc.start_order()           # Start a new investment order
    >>> order.add(results['loans'][0], 25) # Add the first loan to the order with a $25 investment
    >>> order.execute()                    # Execute the order
    8861879
    >>> order.order_id                     # See the order ID

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
