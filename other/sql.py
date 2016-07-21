"""DWC Network Server Emulator

    Copyright (C) 2016 Sepalani

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


class Infix(object):
    """Infix operator class.

    A |Infix| B
    """
    def __init__(self, function):
        self.function = function

    def __ror__(self, other):
        return Infix(lambda x, self=self: self.function(other, x))

    def __or__(self, other):
        return self.function(other)


def sql_like(a, b):
    """SQL LIKE command.

    TODO:
     - Handle % character
     - Handle _ character
     - Handle escape character
     - Handle []
     - Handle [^]
    """
    a = str(a).lower()
    b = str(b).lower()
    return a == b


LIKE = Infix(sql_like)

sql_commands = {
    "LIKE": LIKE
}
