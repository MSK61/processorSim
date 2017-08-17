#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""tests hardware loading service"""

############################################################
#
# Copyright 2017 Mohammed El-Afifi
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
# file:         test_hw.py
#
# function:     hardware loading service tests
#
# description:  tests hardware loading
#
# author:       Mohammed El-Afifi (ME)
#
# environment:  Komodo IDE, version 10.2.1 build 89853, python 2.7.13,
#               Ubuntu 17.04
#
# notes:        This is a private program.
#
############################################################

from mock import patch
import os.path
import test_utils
import processor
from processor import HwDesc
from processor_utils import ProcessorDesc
import processor_utils.units
from processor_utils.units import UnitModel
import unittest
from unittest import TestCase


class CoverageTest(TestCase):

    """Test case for fulfilling complete code coverage"""

    def test_HwDesc_ne_operator(self):
        """Test HwDesc != operator.

        `self` is this test case.

        """
        assert HwDesc(ProcessorDesc([], [], [], []), {}) != HwDesc(
            ProcessorDesc([UnitModel("", 1, [""])], [], [], []), {})

    def test_HwDesc_repr(self):
        """Test HwDesc representation.

        `self` is this test case.

        """
        in_port = UnitModel("", 1, [""])
        out_port = processor_utils.units.FuncUnit(UnitModel("output", 1, [""]),
                                                  [in_port])
        repr(HwDesc(ProcessorDesc([in_port], [out_port], [], []), {}))


class _MockCheck(object):

    """Test case for checking mock calls"""

    def __init__(self, mock_obj, params):
        """Set the mock check information.

        `self` is this mock check.
        `mock_obj` is the mock object.
        `params` are the call parameters.

        """
        self._mock = mock_obj
        self._params = params

    @property
    def mock(self):
        """Mock object

        `self` is this mock check.

        """
        return self._mock

    @property
    def params(self):
        """Expected call parameters

        `self` is this mock check.

        """
        return self._params


class HwDescLoadTest(TestCase):

    """Test case for loading complete hardware description files"""

    def test_hw_load_calls_into_processor_and_isa_load_functions(self):
        """Test loading a full hardware description file.

        `self` is this test case.
        The method tests appropriate calls are made to load the
        processor and ISA descriptions.

        """
        with patch(
            "processor_utils.load_proc_desc",
            return_value=ProcessorDesc([], [], [
                UnitModel("fullSys", 1, ["ALU"])], [])) as proc_mock, patch(
            "processor_utils.get_abilities",
            return_value=frozenset(["ALU"])) as ability_mock, patch(
                "processor_utils.load_isa", return_value={}) as isa_mock:
            assert processor.read_processor(os.path.join(
                test_utils.TEST_DATA_DIR, "fullHwDesc",
                "singleUnitProcessorWithEmptyISA.yaml")) == HwDesc(
                ProcessorDesc([], [], [UnitModel("fullSys", 1, ["ALU"])], []),
                {})

        for mock_chk in [
            _MockCheck(
                proc_mock,
                [{"units": [{"name": "fullSys", "width": 1, "capabilities": [
                    "ALU"]}], "dataPath": []}]), _MockCheck(ability_mock, [
                ProcessorDesc([], [], [UnitModel("fullSys", 1, ["ALU"])], [
                    ])]), _MockCheck(isa_mock, [{}, frozenset(["ALU"])])]:
            mock_chk.mock.assert_called_with(*(mock_chk.params))


def main():
    """entry point for running test in this module"""
    unittest.main()

if __name__ == '__main__':
    main()
