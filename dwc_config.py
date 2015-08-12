"""DWC Network Server Emulator

    Copyright (C) 2014 SMTDDR
    Copyright (C) 2014 kyle95wm
    Copyright (C) 2014 AdmiralCurtiss
    Copyright (C) 2015 Sepalani

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

Configuration module.
"""

try:
    # Python 2
    import ConfigParser
except ImportError:
    # Python 3
    import configparser as ConfigParser


def get_ip_port(section, filename='altwfc.cfg'):
    """Return a tuple (IP, Port) of the corresponding section."""
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.read(filename)
    return (config.get(section, 'IP'), config.getint(section, 'Port'))


def get_ip(section, filename='altwfc.cfg'):
    """Return the IP of the corresponding section."""
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.read(filename)
    return config.get(section, 'IP')


def get_port(section, filename='altwfc.cfg'):
    """Return the port of the corresponding section."""
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.read(filename)
    return config.getint(section, 'Port')
