# -*- coding: utf-8 -*-

"""simulation definitions"""

############################################################
#
# Copyright 2017, 2019, 2020, 2021 Mohammed El-Afifi
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
# file:         sim_defs.py
#
# function:     simulation helper classes
#
# description:  simulation definitions
#
# author:       Mohammed El-Afifi (ME)
#
# environment:  Visual Studdio Code 1.52.1, python 3.8.7, Fedora release
#               33 (Thirty Three)
#
# notes:        This is a private program.
#
############################################################

import enum
from enum import auto

import attr


class StallState(enum.Enum):

    """Instruction stalling state"""

    NO_STALL = auto()

    STRUCTURAL = auto()

    DATA = auto()


@attr.s
class InstrState:

    """Instruction state"""

    instr: int = attr.ib()

    stalled: StallState = attr.ib(StallState.NO_STALL)
