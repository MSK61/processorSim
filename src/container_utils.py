# -*- coding: utf-8 -*-

"""container utilities"""

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
# file:         container_utils.py
#
# function:     generic container utilities
#
# description:  contains helper container functions
#
# author:       Mohammed El-Afifi (ME)
#
# environment:  Komodo IDE, version 10.2.1 build 89853, python 2.7.13,
#               Ubuntu 17.04
#               Komodo IDE, version 11.1.1 build 91089, python 2.7.15,
#               Fedora release 29 (Twenty Nine)
#
# notes:        This is a private program.
#
############################################################

from itertools import imap
import operator
from operator import eq
import str_conv


class BagValDict:

    """Dictionary with(unsorted) lists as values"""

    def __init__(self, initial_dict=None):
        """Create an empty dictionary.

        `self` is this dictionary.
        `initial_dict` is the initial dictionary contents, defaulting to
                       an empty dictionary.

        """
        self._dict = initial_dict or {}

    def __getitem__(self, key):
        """Retrieve the list of the given key.

        `self` is this dictionary.
        `key` is the key to retrieve whose list.

        """
        # We deliberately don't throw exceptions here since a
        # non-existing key is considered to have an empty list.
        return tuple(self._dict.get(key, []))

    def __delitem__(self, key):
        """Delete the list of the given key.

        `self` is this dictionary.
        `key` is the key to remove whose list.

        """
        if key in self._dict:  # Ignore non-existing keys.
            del self._dict[key]

    def __eq__(self, other):
        """Test if the two dictionaries are identical.

        `self` is this dictionary.
        `other` is the other dictionary.

        """
        assert other.__class__.__name__ == self.__class__.__name__
        lst_pairs = imap(lambda pair: imap(sorted, [pair[1], other[pair[0]]]),
                         self._dict.iteritems())
        return eq(*(imap(len, [self, other]))) and all(
            imap(lambda elem_lists: eq(*elem_lists), lst_pairs))

    def __iter__(self):
        """Retrieve an iterator over this dictionary.

        `self` is this dictionary.

        """
        return iter(self._dict)

    def __len__(self):
        """Retrieve the number of keys in this dictionary.

        `self` is this dictionary.

        """
        return len(self._dict)

    def __ne__(self, other):
        """Test if the two dictionaries are different.

        `self` is this dictionary.
        `other` is the other dictionary.

        """
        return not self == other

    def __repr__(self):
        """Return the official string of this dictionary.

        `self` is this dictionary.

        """
        return str_conv.format_obj(
            self.__class__.__name__, [self._format_dict()])

    def add(self, key, elem):
        """Append the element to the key list.

        `self` is this dictionary.
        `key` is the key to append the element to whose list.
        `elem` is the element to append.

        """
        self._dict.setdefault(key, []).append(elem)

    def remove(self, key, elem_index):
        """Remove the element from the key list.

        `self` is this dictionary.
        `key` is the key to remove the element from whose list.
        `elem_index` is the element index in the key list.

        """
        self._dict[key].pop(elem_index)

        if not self._dict[key]:
            del self._dict[key]

    def _format_dict(self):
        """Format this dictionary.

        `self` is this dictionary.

        """
        return "{{{}}}".format(self._format_elems())

    def _format_elems(self):
        """Format the elements of this dictionary.

        `self` is this dictionary.

        """
        items = imap(
            lambda item: (item[0], sorted(item[1])), self._dict.iteritems())
        item_strings = imap(lambda item: "{}: {}".format(
            repr(item[0]), item[1]), sorted(items, key=operator.itemgetter(0)))
        sep = ", "
        return sep.join(item_strings)


def contains(container, elems):
    """Test the membership of all elements within a container.

    `container` is the container to check elements against.
    `elems` are the elements to check.

    """
    return all(imap(lambda cur_elem: cur_elem in container, elems))
