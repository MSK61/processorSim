#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""tests register access structures"""

############################################################
#
# Copyright 2017, 2019 Mohammed El-Afifi
# This file is part of processorSim.
#
# processorSim is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# processorSim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with processorSim.  If not, see
# <http://www.gnu.org/licenses/>.
#
# program:      processor simulator
#
# file:         test_reg_access.py
#
# function:     register access plan tests
#
# description:  tests register access plan creation
#
# author:       Mohammed El-Afifi (ME)
#
# environment:  Komodo IDE, version 11.1.1 build 91089, python 3.7.3,
#               Fedora release 30 (Thirty)
#
# notes:        This is a private program.
#
############################################################

import pytest
from pytest import mark
from test_env import TEST_DIR
from reg_access import Access, AccessType, RegAccessQueue, RegAccQBuilder
import unittest


class TestAccessPlan:

    """Test case for creating register access plans"""

    @mark.parametrize("req_type", [AccessType.READ, AccessType.WRITE])
    def test_adding_request_to_empty_queue_creates_new_request(self, req_type):
        """Test adding a request to an empty queue.

        `self` is this test case.
        `req_type` is the type of the request to add.

        """
        builder = RegAccQBuilder()
        builder.append(req_type, len(TEST_DIR))
        assert builder.create() == RegAccessQueue(
            [Access(req_type, len(TEST_DIR))])

    @mark.parametrize("prev_req", [AccessType.READ, AccessType.WRITE])
    def test_adding_write_after_any_request_creates_new_write(self, prev_req):
        """Test adding a write request after any request.

        `self` is this test case.
        `prev_req` is the request preceding the write request.

        """
        builder = RegAccQBuilder()
        builder.append(prev_req, 0)
        builder.append(AccessType.WRITE, 1)
        assert builder.create() == RegAccessQueue(
            [Access(prev_req, 0), Access(AccessType.WRITE, 1)])


class CoverageTest(unittest.TestCase):

    """Test case for fulfilling complete code coverage"""

    def test_Access_ne_operator(self):
        """Test Access != operator.

        `self` is this test case.

        """
        assert Access(AccessType.READ, 0) != Access(AccessType.READ, 1)

    def test_RegAccessQueue_ne_operator(self):
        """Test RegAccessQueue != operator.

        `self` is this test case.

        """
        assert RegAccessQueue([]) != RegAccessQueue(
            [Access(AccessType.READ, 0)])

    def test_RegAccessQueue_repr(self):
        """Test RegAccessQueue representation.

        `self` is this test case.

        """
        assert repr(RegAccessQueue([Access(
            AccessType.READ,
            0)])) == "RegAccessQueue([Access(AccessType.READ, 0)])"


def main():
    """entry point for running test in this module"""
    pytest.main([__file__])

if __name__ == '__main__':
    main()
