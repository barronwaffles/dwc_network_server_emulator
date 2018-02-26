"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 AdmiralCurtiss
    Copyright (C) 2014 msoucy
    Copyright (C) 2018 Sepalani

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

import os
import random
import logging
import BaseHTTPServer
import cgi
import urlparse
import sqlite3
import xml.dom.minidom as minidom

import other.utils as utils
import gamespy.gs_database as gs_database
import dwc_config

from io import BytesIO

# Paths to ProxyPass: /SakeStorageServer, /SakeFileServer
logger = dwc_config.get_logger('StorageServer')
address = dwc_config.get_ip_port('StorageServer')


def escape_xml(s):
    s = s.replace( "&", "&amp;" )
    s = s.replace( '"', "&quot;" )
    s = s.replace( "'", "&apos;" )
    s = s.replace( "<", "&lt;" )
    s = s.replace( ">", "&gt;" )
    return s


class StorageServer(object):
    def start(self):
        httpd = StorageHTTPServer((address[0], address[1]), StorageHTTPServerHandler)
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()


class StorageHTTPServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)

        self.gamespydb = gs_database.GamespyDatabase()

        self.db = sqlite3.connect('storage.db')
        self.tables = {}
        self.valid_sql_terms = ['LIKE', '=', 'AND', 'OR']

        logger.log(logging.INFO, "Checking for and creating database tables...")

        cursor = self.db.cursor()
        if not self.table_exists('typedata'):
            cursor.execute('CREATE TABLE typedata (tbl TEXT, col TEXT, type TEXT)')
        if not self.table_exists('filepaths'):
            cursor.execute('CREATE TABLE filepaths (fileid INTEGER PRIMARY KEY AUTOINCREMENT, gameid INT, playerid INT, path TEXT)')

        PK = 'INTEGER PRIMARY KEY AUTOINCREMENT'

        self.create_or_alter_table_if_not_exists(
            'g1443_bbdx_player',
            ['recordid', 'stat'],
            [PK,         'INT' ],
            ['int',      'int' ])
        self.create_or_alter_table_if_not_exists(
            'g1443_bbdx_info',
            ['serialid', 'stat', 'message'      ],
            ['INT',      'INT',  'TEXT'         ],
            ['int',      'int',  'unicodeString'])
        self.create_or_alter_table_if_not_exists(
            'g1443_bbdx_search',
            ['recordid', 'song_name',   'creator_name', 'average_rating', 'serialid', 'filestore', 'is_lyric', 'num_ratings', 'jasrac_code', 'artist_name'],
            [PK,         'TEXT',        'TEXT',         'REAL',           'INT',      'INT',       'INT',      'INT',         'TEXT',        'TEXT'       ],
            ['int',      'asciiString', 'asciiString',  'float',          'int',      'int',       'boolean',  'int',         'asciiString', 'asciiString'])

        # Mario Kart Wii
        self.create_or_alter_table_if_not_exists(
            'g1687_FriendInfo',
            ['recordid', 'ownerid', 'info'      ],
            [PK,         'INT',     'TEXT'      ],
            ['int',      'int',     'binaryData'])

        self.create_or_alter_table_if_not_exists(
            'g1687_StoredGhostData',
            ['recordid', 'fileid', 'profile', 'region', 'gameid', 'course' ],
            [PK,         'INT',    'INT',     'INT',    'INT',    'INT'    ],
            ['int',      'int',    'int',     'int',    'int',    'int'    ])

        # WarioWare DIY
        self.create_or_alter_table_if_not_exists(
            'g2050_contest',
            ['recordid', 'ownerid', 'm_no', 'm_file_id'],
            [PK,         'INT',     'INT',  'INT'      ],
            ['int',      'int',     'int',  'int'      ])
        self.create_or_alter_table_if_not_exists(
            'g2050_contest_eu',
            ['recordid', 'ownerid', 'm_no', 'm_file_id'],
            [PK,         'INT',     'INT',  'INT'      ],
            ['int',      'int',     'int',  'int'      ])
        self.create_or_alter_table_if_not_exists(
            'g2050_contest_us',
            ['recordid', 'ownerid', 'm_no', 'm_file_id'],
            [PK,         'INT',     'INT',  'INT'      ],
            ['int',      'int',     'int',  'int'      ])
        self.create_or_alter_table_if_not_exists(
            'g2050_box',
            ['recordid', 'ownerid', 'm_enable', 'm_type', 'm_index', 'm_file_id', 'm_header',   'm_file_id___size', 'm_file_id___create_time', 'm_file_id___downloads'],
            [PK,         'INT',     'INT',      'INT',    'INT',     'INT',       'TEXT',       'INT',              'DATETIME',                'INT'                  ],
            ['int',      'int',     'boolean',  'int',    'int',     'int',       'binaryData', 'int',              'dateAndTime',             'int'                  ])
        cursor.execute('CREATE TRIGGER IF NOT EXISTS g2050ti_box AFTER INSERT ON g2050_box BEGIN UPDATE g2050_box SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\'), m_file_id___size = 0, m_file_id___downloads = 0 WHERE recordid = NEW.recordid; END')
        cursor.execute('CREATE TRIGGER IF NOT EXISTS g2050tu_box AFTER UPDATE ON g2050_box BEGIN UPDATE g2050_box SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\') WHERE recordid = NEW.recordid; END')
        self.create_or_alter_table_if_not_exists(
            'g2050_box_us_eu',
            ['recordid', 'ownerid', 'm_enable', 'm_type', 'm_index', 'm_file_id', 'm_header',   'm_file_id___size', 'm_file_id___create_time', 'm_file_id___downloads'],
            [PK,         'INT',     'INT',      'INT',    'INT',     'INT',       'TEXT',       'INT',              'DATETIME',                'INT'                  ],
            ['int',      'int',     'boolean',  'int',    'int',     'int',       'binaryData', 'int',              'dateAndTime',             'int'                  ])
        cursor.execute('CREATE TRIGGER IF NOT EXISTS g2050ti_box_us_eu AFTER INSERT ON g2050_box_us_eu BEGIN UPDATE g2050_box_us_eu SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\'), m_file_id___size = 0, m_file_id___downloads = 0 WHERE recordid = NEW.recordid; END')
        cursor.execute('CREATE TRIGGER IF NOT EXISTS g2050tu_box_us_eu AFTER UPDATE ON g2050_box_us_eu BEGIN UPDATE g2050_box_us_eu SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\') WHERE recordid = NEW.recordid; END')

        self.create_or_alter_table_if_not_exists(
            'g2649_bbdx_player',
            ['recordid', 'stat'],
            [PK,         'INT' ],
            ['int',      'int' ])
        self.create_or_alter_table_if_not_exists(
            'g2649_bbdx_info',
            ['serialid', 'stat', 'message'      ],
            ['INT',      'INT',  'TEXT'         ],
            ['int',      'int',  'unicodeString'])
        self.create_or_alter_table_if_not_exists(
            'g2649_bbdx_search',
            ['recordid', 'song_name',   'creator_name', 'average_rating', 'serialid', 'filestore', 'is_lyric', 'num_ratings', 'song_code',   'artist_name'],
            [PK,         'TEXT',        'TEXT',         'REAL',           'INT',      'INT',       'INT',      'INT',         'TEXT',        'TEXT'       ],
            ['int',      'asciiString', 'asciiString',  'float',          'int',      'int',       'boolean',  'int',         'asciiString', 'asciiString'])

        # Playground
        self.create_or_alter_table_if_not_exists(
            'g2999_tblRegionInfo',
            ['recordid', 'region', 'allowed_regions', 'min_ratings' ],
            [PK,         'INT',    'INT',             'INT'         ],
            ['int',      'byte',   'int',             'int'         ])

        # Super Smash Bros. Brawl
        self.create_or_alter_table_if_not_exists(
            'g1658_submit',
            ['recordid', 'ownerid', 'data'],
            [PK,         'INT',     'INT'],
            ['int',      'int',     'int']
        )
        self.create_or_alter_table_if_not_exists(
            'g1658_watching',
            ['recordid', 'ownerid', 'data'],
            [PK,         'INT',     'INT'],
            ['int',      'int',     'int']
        )

        # Trackmania Wii
        self.create_or_alter_table_if_not_exists(
            'g2793_player',
            ['recordid', 'ownerid', 'ladder', 'avatar', 'mii', 'name',        'wins', 'loses', 'count', 'row'],
            [PK,         'INT',     'INT',    'INT',    'INT', 'TEXT',        'INT',  'INT',   'INT',   'INT'],
            ['int',      'int',     'int',    'int',    'int', 'asciiString', 'int',  'int',   'int',   'int']
        )

        self.create_or_alter_table_if_not_exists(
            'g2793_solo',
            ['recordid', 'ownerid', 'trackID', 'time',  'ghostID', 'ghostTime', 'date', 'ghostSize', 'row'],
            [PK,         'INT',     'INT',     'REAL',  'INT',     'REAL',      'INT',  'INT',       'INT'],
            ['int',      'int',     'int',     'float', 'int',     'float',     'int',  'int',       'int']
        )

        self.create_or_alter_table_if_not_exists(
            'g2793_custom',
            ['recordid', 'ownerid', 'name',        'author',      'date', 'env', 'trackFile', 'trackSize', 'goldFile', 'goldSize', 'silverFile', 'silverSize', 'bronzeFile', 'bronzeSize', 'isValidated'],
            [PK,         'INT',     'TEXT',        'TEXT',        'INT',  'INT', 'INT',       'INT',       'INT',      'INT',      'INT',        'INT',        'INT',        'INT',        'INT'],
            ['int',      'int',     'asciiString', 'asciiString', 'int',  'int', 'int',       'int',       'int',      'int',      'int',        'int',        'int',        'int',        'int']
        )

        self.create_or_alter_table_if_not_exists(
            'g2793_customDLC',
            ['recordid', 'ownerid', 'name',        'author',      'date', 'env', 'trackFile', 'trackSize', 'goldFile', 'goldSize', 'silverFile', 'silverSize', 'bronzeFile', 'bronzeSize', 'isValidated', 'isDLC'],
            [PK,         'INT',     'TEXT',        'TEXT',        'INT',  'INT', 'INT',       'INT',       'INT',      'INT',      'INT',        'INT',        'INT',        'INT',        'INT',         'INT'],
            ['int',      'int',     'asciiString', 'asciiString', 'int',  'int', 'int',       'int',       'int',      'int',      'int',        'int',        'int',        'int',        'int',         'int']
        )

        # load column info into memory, unfortunately there's no simple way
        # to check for column-existence so get that data in advance
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabledata = cursor.fetchall()
        for t in tabledata:
            cursor.execute("PRAGMA table_info(%s)" % t[0]) # yeah I know but parameters don't work in pragmas, and inserting table names like that should be safe
            columns = cursor.fetchall()
            self.tables[t[0]] = [c[1] for c in columns]

        self.db.commit()

    def table_exists(self, name):
        cursor = self.db.cursor()
        cursor.execute("SELECT Count(1) FROM sqlite_master WHERE type='table' AND name=?", (name,))
        exists = cursor.fetchone()[0]
        return True if exists else False

    def column_exists(self, table, column):
        cursor = self.db.cursor()
        cursor.execute("PRAGMA table_info(%s)" % table)
        data = cursor.fetchall()
        for row in data:
            if column == row[1]:
                return True
        return False

    def create_or_alter_table_if_not_exists(self, table, columns, sqlTypes, sakeTypes):
        # this is certainly not the most efficient way to create a table, but it should work and makes that mess in the init function more readable
        if not self.table_exists(table):
            cursor = self.db.cursor()
            cursor.execute('CREATE TABLE ' + table + ' (' + columns[0] + ' ' + sqlTypes[0] + ')')
            cursor.execute('INSERT INTO typedata (tbl, col, type) VALUES (?, ?, ?)', (table, columns[0], sakeTypes[0] + 'Value'))

        for i, col in enumerate(columns):
            self.create_column_if_not_exists(table, columns[i], sqlTypes[i], sakeTypes[i] + 'Value')
        return

    def create_column_if_not_exists(self, table, column, sqlType, sakeType):
        if not self.column_exists(table, column):
            cursor = self.db.cursor()
            cursor.execute('ALTER TABLE ' + table + ' ADD COLUMN ' + column + ' ' + sqlType)
            cursor.execute('INSERT INTO typedata (tbl, col, type) VALUES (?, ?, ?)', (table, column, sakeType))
        return

    def get_typedata(self, table, column):
        try:
            cursor = self.db.cursor()
            cursor.execute("SELECT type FROM typedata WHERE tbl=? AND col=?", (table,column))
            return cursor.fetchone()[0]
        except TypeError:
            return 'UNKNOWN'


class IllegalColumnAccessException(Exception):
    pass


class FilterSyntaxException(Exception):
    pass


class StorageHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def confirm_columns(self, columndata, table):
        '''Check if the columns the user wants to access actually exist, which should prevent SQL Injection'''
        columns = []

        for c in columndata:
            colname = c.firstChild.data.replace('.', '___') # fake the attributes that the actual sake databases have
            if colname not in self.server.tables[table]:
                raise IllegalColumnAccessException("Unknown column access '%s' in table '%s'" % (colname, table))
            columns.append(colname)

        return columns

    def tokenize_filter(self, filter):
        # TODO: Actual proper tokenization
        return filter.split()

    def parse_filter(self, table, filter):
        # I think I need to read up on how to properly parse SQL-like data, but this should do for the stuff I've seen from games so far.
        out = ''

        if ';' in filter:
            raise FilterSyntaxException("Semicolon in filter '%s'" & filter)
        if '\\' in filter:
            raise FilterSyntaxException("Backslash in filter '%s'" & filter)
        brace_count = filter.count('(')
        if brace_count != filter.count(')'):
            raise FilterSyntaxException("Mismatching brace count in filter '%s'" & filter)

        filter = self.tokenize_filter(filter)

        for f in filter:
            if f in self.server.tables[table]:
                # is a table name
                out += f + ' '
            elif f.upper() in self.server.valid_sql_terms:
                # is some SQL term such as LIKE, AND, OR, etc.
                out += f + ' '
            elif ( f.startswith("'") and f.endswith("'") ) or ( f.startswith('"') and f.endswith('"') ):
                # is a string
                out += f + ' '
            else:
                # is nothing valid, abort and return the statement so far
                out = out.strip()

                # try to make the output still valid by removing trailing connecting tokens
                last_space = out.rfind(' ')
                if last_space >= 0:
                    last_token = out[last_space + 1 :  ]
                    if last_token in self.server.valid_sql_terms:
                        out = out[  : last_space ]

                return out

        return out

    def append_filter(self, filter, table, statement, where_appended):
        try:
            filters = self.parse_filter(table, filter)
            if filters:
                if not where_appended:
                    statement += ' WHERE '
                    where_appended = True
                else:
                    statement += ' AND '
                statement += ' ( '
                statement += filters
                statement += ' ) '
        except FilterSyntaxException as e:
            logger.log(logging.WARNING, "FilterSyntaxException: %s by %s", e.message, self.client_address)
            pass
        return statement, where_appended

    def do_POST(self):
        # Alright, in case anyone is wondering: Yes, I am faking a SOAP service
        # instead of using an actual one. That's because I've tried to do this
        # with several actual python SOAP services and none of them give me the
        # ability to return the exact format that I want.
        # (Or make any kind of sense in case of ZSI...)

        if self.path == "/SakeStorageServer/StorageServer.asmx":
            length = int(self.headers.get('content-length', -1))
            action = self.headers['SOAPAction']
            post = self.rfile.read(length)
            logger.log(logging.DEBUG, "SakeStorageServer SOAPAction %s", action)
            logger.log(logging.DEBUG, post)

            shortaction = action[action.rfind('/')+1:-1]

            ret = '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><soap:Body>'

            if "<!DOCTYPE" in post.upper():
                logger.log(logging.ERROR, "User tried to redefine a DOCTYPE")
                return

            dom = minidom.parseString(post)
            data = dom.getElementsByTagName('SOAP-ENV:Body')[0].getElementsByTagName('ns1:' + shortaction)[0]
            gameid = str(int(data.getElementsByTagName('ns1:gameid')[0].firstChild.data))
            tableid = data.getElementsByTagName('ns1:tableid')[0].firstChild.data
            loginticket = data.getElementsByTagName('ns1:loginTicket')[0].firstChild.data

            table = 'g' + gameid + '_' + tableid

            if not self.server.table_exists(table):
                logger.log(logging.WARNING, "Unknown table access '%s' in %s by %s", table, shortaction, self.client_address)
                return

            ret += '<' + shortaction + 'Response xmlns="http://gamespy.net/sake">'
            ret += '<' + shortaction + 'Result>Success</' + shortaction + 'Result>'

            if shortaction == 'SearchForRecords' or shortaction == 'GetMyRecords' or shortaction == 'GetSpecificRecords':
                columndata = data.getElementsByTagName('ns1:fields')[0].getElementsByTagName('ns1:string')
                try:
                    columns = self.confirm_columns(columndata, table)
                except IllegalColumnAccessException as e:
                    logger.log(logging.WARNING, "IllegalColumnAccess: %s in %s by %s", e.message, shortaction, self.client_address)
                    return

                # build SELECT statement, yes I know one shouldn't do this but I cross-checked the table name and all the columns above so it should be fine
                statement = 'SELECT '
                statement += ",".join(columns)
                statement += ' FROM ' + table
                where_appended = False

                if shortaction == 'SearchForRecords':
                    # this is ugly as hell but SearchForRecords can request specific ownerids like this
                    owneriddata = data.getElementsByTagName('ns1:ownerids')
                    if owneriddata and owneriddata[0] and owneriddata[0].firstChild:
                        oids = owneriddata[0].getElementsByTagName('ns1:int')
                        if not where_appended:
                            statement += ' WHERE '
                            where_appended = True
                        else:
                            statement += ' AND '
                        statement += ' ( '
                        statement += ' OR '.join('ownerid = '+str(int(oid.firstChild.data)) for oid in oids)
                        statement += ' ) '

                elif shortaction == 'GetMyRecords':
                    profileid = self.server.gamespydb.get_profileid_from_loginticket(loginticket)
                    if not where_appended:
                        statement += ' WHERE '
                        where_appended = True
                    else:
                        statement += ' AND '
                    statement += ' ( ownerid = ' + str(profileid) + ' ) '

                elif shortaction == 'GetSpecificRecords':
                    recordids = data.getElementsByTagName('ns1:recordids')[0].getElementsByTagName('ns1:int')

                    # limit to requested records
                    if not where_appended:
                        statement += ' WHERE '
                        where_appended = True
                    else:
                        statement += ' AND '
                    statement += ' ( '
                    statement += ' OR '.join('recordid = '+str(int(r.firstChild.data)) for r in recordids)
                    statement += ' ) '

                # if there's a filter, evaluate it
                filterdata = data.getElementsByTagName('ns1:filter')
                if filterdata and filterdata[0] and filterdata[0].firstChild:
                    statement, where_appended = self.append_filter(filterdata[0].firstChild.data, table, statement, where_appended)

                # if only a subset of the data is wanted
                limit_offset_data = data.getElementsByTagName('ns1:offset')
                limit_max_data = data.getElementsByTagName('ns1:max')
                limits = []
                if limit_offset_data and limit_offset_data[0] and limit_offset_data[0].firstChild:
                    limits.append(str(int(limit_offset_data[0].firstChild.data)))
                if limit_max_data and limit_max_data[0] and limit_max_data[0].firstChild:
                    limits.append(str(int(limit_max_data[0].firstChild.data)))
                if limits:
                    statement += ' LIMIT ' + ','.join(limits)

                logger.log(logging.DEBUG, statement)
                cursor = self.server.db.cursor()
                cursor.execute(statement)
                rows = cursor.fetchall()

                if rows:
                    ret += '<values>'
                    for r in rows:
                        ret += '<ArrayOfRecordValue>'
                        for i, c in enumerate(r):
                            type = self.server.get_typedata(table, columns[i])

                            ret += '<RecordValue>'
                            ret += '<' + type + '>'
                            if c is not None:
                                if type == 'booleanValue':
                                    ret += '<value>' + ('true' if c else 'false') + '</value>'
                                else:
                                    ret += '<value>' + escape_xml(str(c)) + '</value>'
                            else:
                                ret += '<value/>'
                            ret += '</' + type + '>'
                            ret += '</RecordValue>'
                        ret += '</ArrayOfRecordValue>'
                    ret += '</values>'
                else:
                    ret += '<values/>'


            elif shortaction == 'GetRecordCount':
                statement = 'SELECT COUNT(1) FROM ' + table

                filterdata = data.getElementsByTagName('ns1:filter')
                if filterdata and filterdata[0] and filterdata[0].firstChild:
                    statement, where_appended = self.append_filter(filterdata[0].firstChild.data, table, statement, False)

                logger.log(logging.DEBUG, statement)

                cursor = self.server.db.cursor()
                cursor.execute(statement)
                count = cursor.fetchone()[0]

                ret += '<count>' + str(count) + '</count>'

            elif shortaction == 'UpdateRecord' or shortaction == 'CreateRecord':
                if shortaction == 'UpdateRecord':
                    recordid = int(data.getElementsByTagName('ns1:recordid')[0].firstChild.data)

                profileid = self.server.gamespydb.get_profileid_from_loginticket(loginticket)

                values = data.getElementsByTagName('ns1:values')[0]
                recordfields = values.getElementsByTagName('ns1:RecordField')
                columndata = [rf.getElementsByTagName('ns1:name')[0]
                              for rf in recordfields]

                try:
                    columns = self.confirm_columns(columndata, table)
                except IllegalColumnAccessException as e:
                    logger.log(logging.WARNING, "IllegalColumnAccess: %s in %s by %s", e.message, shortaction, self.client_address)
                    return

                rowdata = []
                for i, rf in enumerate(recordfields):
                    type = self.server.get_typedata(table, columns[i])
                    value = rf.getElementsByTagName('ns1:value')[0].getElementsByTagName('ns1:' + type)[0].getElementsByTagName('ns1:value')[0].firstChild.data
                    if type == 'intValue' or type == 'booleanValue':
                        rowdata.append( int(value) )
                    elif type == 'floatValue':
                        rowdata.append( float(value) )
                    else:
                        rowdata.append( value )

                if shortaction == 'UpdateRecord':
                    statement = 'UPDATE ' + table + ' SET '

                    statement += ', '.join(c+' = ?' for c in columns)
                    statement += ' WHERE recordid = ? AND ownerid = ?'
                    rowdata.append( recordid )
                    rowdata.append( profileid )
                elif shortaction == 'CreateRecord':
                    statement = 'INSERT INTO ' + table + ' ('

                    statement += ', '.join(columns)
                    statement += ', ownerid) VALUES ('
                    statement += '?, '*len(columns)
                    statement += '?)'
                    rowdata.append( profileid )
                else:
                    logger.log(logging.ERROR, 'Illegal Action %s in database insert/update path!', shortaction)
                    return

                cursor = self.server.db.cursor()
                cursor.execute(statement, tuple(rowdata))
                recordid = cursor.lastrowid

                if shortaction == 'CreateRecord':
                    ret += '<recordid>' + str(recordid) + '</recordid>'

                # Alright, so this kinda sucks, but we have no good way of automatically inserting
                # or updating the file's .size attribute, so we have to manually check if any column
                # has that, and update it accordingly.
                # I have no idea if this will work with all games but it seems to work in WarioWare.
                for i, col in enumerate(columns):
                    attrcol = col + '___size'
                    if attrcol in self.server.tables[table]:
                        if rowdata[i] == 0: # is a delete command, just set filesize to 0
                            filesize = 0
                        else:
                            cursor.execute('SELECT path FROM filepaths WHERE fileid = ?', (int(rowdata[i]),))

                            try:
                                filename = cursor.fetchone()[0]
                                filesize = os.path.getsize(filename)
                            except:
                                filesize = 0
                        cursor.execute('UPDATE ' + table + ' SET ' + attrcol + ' = ? WHERE recordid = ?', (filesize, recordid))

                self.server.db.commit()

            ret += '</' + shortaction + 'Response>'
            ret += '</soap:Body></soap:Envelope>'

            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.end_headers()

            logger.log(logging.DEBUG, "%s response to %s", action, self.client_address)
            #logger.log(logging.DEBUG, ret)
            self.wfile.write(ret)

        elif self.path.startswith("/SakeFileServer/upload.aspx?"):
            retcode = 0
            params = urlparse.parse_qs(self.path[self.path.find('?')+1:])

            gameid = int(params['gameid'][0])
            playerid = int(params['pid'][0])

            logger.log(logging.DEBUG, "SakeFileServer Upload Request in game %s, user %s", gameid, playerid)

            ctype, pdict = cgi.parse_header(self.headers['Content-Type'])
            multipart_data = self.rfile.read(int(self.headers.get('Content-Length', -1)))
            filedata = cgi.parse_multipart(BytesIO(multipart_data), pdict)
            data = filedata.get('data')
            if data is not None:
                data = data[0]
            else:
                for key in filedata:
                    if not filedata[key]:
                        continue
                    data = filedata[key][0]
                    break
            filesize = -1 if data is None else len(data)

            # make sure users don't upload huge files, dunno what an actual sensible maximum is
            # but 64 KB seems reasonable for what I've seen in WarioWare
            if data is not None and filesize <= 65536:
                # Apparently the real Sake doesn't care about the gameid/playerid, just the fileid
                # but for better categorization I think I'm still gonna leave folder-per-game/player thing

                userdir = 'usercontent/' + str(gameid) + '/' + str(playerid)
                if not os.path.exists(userdir):
                    os.makedirs(userdir)

                # get next fileid from database
                cursor = self.server.db.cursor()
                cursor.execute('INSERT INTO filepaths (gameid, playerid) VALUES (?, ?)', (gameid, playerid))
                fileid = cursor.lastrowid

                path = userdir + '/' + str(fileid)
                cursor.execute('UPDATE filepaths SET path = ? WHERE fileid = ?', (path, fileid))

                with open(path, 'wb') as fi:
                    fi.write(data)
            elif data is not None:
                logger.log(logging.WARNING, "Tried to upload big file, rejected. (%s bytes)", filesize)
                fileid = 0
                retcode = 1
            else:
                logger.log(logging.ERROR, "Failed to read data")
                fileid = 0
                retcode = 1

            self.send_response(200)

            if retcode == 0:
                self.send_header('Sake-File-Id', str(fileid))

            self.send_header('Sake-File-Result', str(retcode))
            self.end_headers()

            logger.log(logging.DEBUG, "SakeFileServer Upload Reply Sake-File-Id %s (%d bytes)", fileid, filesize)
            self.wfile.write('')

        else:
            logger.log(logging.INFO, "[NOT IMPLEMENTED] Got POST request %s from %s", self.path, self.client_address)

    def do_GET(self):
        if self.path.startswith("/SakeFileServer/download.aspx?"):
            params = urlparse.parse_qs(self.path[self.path.find('?')+1:])
            retcode = 0
            ret = ''

            if 'pid' not in params or 'fileid' not in params or 'gameid' not in params:
                logger.log(logging.DEBUG, "Could not find expected parameters")
                retcode = 3
            else:
                fileid = int(params['fileid'][0])
                gameid = int(params['gameid'][0])
                playerid = int(params['pid'][0])

                logger.log(logging.DEBUG, "SakeFileServer Download Request in game %s, user %s, file %s", gameid, playerid, fileid)

                cursor = self.server.db.cursor()
                cursor.execute('SELECT path FROM filepaths WHERE fileid = ?', (fileid,))

                try:
                    filename = cursor.fetchone()[0]

                    if os.path.exists(filename):
                        with open(filename, 'rb') as fi:
                            ret = fi.read()
                    else:
                        logger.log(logging.ERROR, "User is trying to access file that should exist according to DB, but doesn't! (%s)", filename)
                except:
                    logger.log(logging.WARNING, "User is trying to access non-existing file!")
                    ret = '1234' # apparently some games use the download command just to increment the "downloads" counter, and get the actual file from dls1
                    #retcode = 4

            filelen = len(ret)
            self.send_response(200)
            self.send_header('Sake-File-Result', str(retcode))
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', filelen)
            self.end_headers()

            logger.log(logging.DEBUG, "Returning download request with file of %s bytes", filelen)

            self.wfile.write(ret)

        else:
            logger.log(logging.INFO, "[NOT IMPLEMENTED] Got GET request %s from %s", self.path, self.client_address)


if __name__ == "__main__":
    storage_server = StorageServer()
    storage_server.start()
