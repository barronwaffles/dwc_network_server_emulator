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

logger_output_to_console = True
logger_output_to_file = True
logger_name = "StorageServer"
logger_filename = "storage_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

# Paths to ProxyPass: /SakeStorageServer, /SakeFileServer
address = ("127.0.0.1", 8000)

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
        
        cursor = self.db.cursor()
        
        if not self.table_exists('typedata'):
            cursor.execute('CREATE TABLE typedata (tbl TEXT, col TEXT, type TEXT)')
        if not self.table_exists('filepaths'):
            cursor.execute('CREATE TABLE filepaths (fileid INTEGER PRIMARY KEY AUTOINCREMENT, gameid INT, playerid INT, path TEXT)')

        if not self.table_exists('g1687_FriendInfo'):
            cursor.execute('CREATE TABLE g1687_FriendInfo (recordid INTEGER PRIMARY KEY AUTOINCREMENT, ownerid INT, info TEXT)')
            cursor.execute('INSERT INTO typedata VALUES ("g1687_FriendInfo", "recordid", "intValue"), ("g1687_FriendInfo", "ownerid", "intValue"), ("g1687_FriendInfo", "info", "binaryDataValue")')
        else:
            self.create_column_if_not_exists('g1687_FriendInfo', 'ownerid', 'INT',  'intValue')
            self.create_column_if_not_exists('g1687_FriendInfo', 'info',    'TEXT', 'binaryDataValue')
            
        if not self.table_exists('g2050_box'):
            cursor.execute('CREATE TABLE g2050_box (recordid INTEGER PRIMARY KEY AUTOINCREMENT, ownerid INT, m_enable INT, m_type INT, m_index INT, m_file_id INT, m_header TEXT, m_file_id___size INT, m_file_id___create_time DATETIME, m_file_id___downloads INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2050_box", "recordid", "intValue"), ("g2050_box", "ownerid", "intValue"), ("g2050_box", "m_enable", "booleanValue"), ("g2050_box", "m_type", "intValue"), ("g2050_box", "m_index", "intValue"), ("g2050_box", "m_file_id", "intValue"), ("g2050_box", "m_header", "binaryDataValue"), ("g2050_box", "m_file_id___size", "intValue"), ("g2050_box", "m_file_id___create_time", "dateAndTimeValue"), ("g2050_box", "m_file_id___downloads", "intValue")')
            cursor.execute('CREATE TRIGGER g2050ti_box AFTER INSERT ON g2050_box BEGIN UPDATE g2050_box SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\'), m_file_id___size = 0, m_file_id___downloads = 0 WHERE recordid = NEW.recordid; END')
            cursor.execute('CREATE TRIGGER g2050tu_box AFTER UPDATE ON g2050_box BEGIN UPDATE g2050_box SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\') WHERE recordid = NEW.recordid; END')
        if not self.table_exists('g2050_box_us_eu'):
            cursor.execute('CREATE TABLE g2050_box_us_eu (recordid INTEGER PRIMARY KEY AUTOINCREMENT, ownerid INT, m_enable INT, m_type INT, m_index INT, m_file_id INT, m_header TEXT, m_file_id___size INT, m_file_id___create_time DATETIME, m_file_id___downloads INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2050_box_us_eu", "recordid", "intValue"), ("g2050_box_us_eu", "ownerid", "intValue"), ("g2050_box_us_eu", "m_enable", "booleanValue"), ("g2050_box_us_eu", "m_type", "intValue"), ("g2050_box_us_eu", "m_index", "intValue"), ("g2050_box_us_eu", "m_file_id", "intValue"), ("g2050_box_us_eu", "m_header", "binaryDataValue"), ("g2050_box_us_eu", "m_file_id___size", "intValue"), ("g2050_box_us_eu", "m_file_id___create_time", "dateAndTimeValue"), ("g2050_box_us_eu", "m_file_id___downloads", "intValue")')
            cursor.execute('CREATE TRIGGER g2050ti_box_us_eu AFTER INSERT ON g2050_box_us_eu BEGIN UPDATE g2050_box_us_eu SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\'), m_file_id___size = 0, m_file_id___downloads = 0 WHERE recordid = NEW.recordid; END')
            cursor.execute('CREATE TRIGGER g2050tu_box_us_eu AFTER UPDATE ON g2050_box_us_eu BEGIN UPDATE g2050_box_us_eu SET m_file_id___create_time = strftime(\'%Y-%m-%dT%H:%M:%f\', \'now\') WHERE recordid = NEW.recordid; END')
        if not self.table_exists('g2050_contest'):
            cursor.execute('CREATE TABLE g2050_contest (recordid INTEGER PRIMARY KEY AUTOINCREMENT, ownerid INT, m_no INT, m_file_id INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2050_contest", "recordid", "intValue"), ("g2050_contest", "ownerid", "intValue"), ("g2050_contest", "m_no", "intValue"), ("g2050_contest", "m_file_id", "intValue")')
        if not self.table_exists('g2050_contest_us'):
            cursor.execute('CREATE TABLE g2050_contest_us (recordid INTEGER PRIMARY KEY AUTOINCREMENT, ownerid INT, m_no INT, m_file_id INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2050_contest_us", "recordid", "intValue"), ("g2050_contest_us", "ownerid", "intValue"), ("g2050_contest_us", "m_no", "intValue"), ("g2050_contest_us", "m_file_id", "intValue")')
        if not self.table_exists('g2050_contest_eu'):
            cursor.execute('CREATE TABLE g2050_contest_eu (recordid INTEGER PRIMARY KEY AUTOINCREMENT, ownerid INT, m_no INT, m_file_id INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2050_contest_eu", "recordid", "intValue"), ("g2050_contest_eu", "ownerid", "intValue"), ("g2050_contest_eu", "m_no", "intValue"), ("g2050_contest_eu", "m_file_id", "intValue")')

        if not self.table_exists('g2649_bbdx_player'):
            cursor.execute('CREATE TABLE g2649_bbdx_player (recordid INTEGER PRIMARY KEY AUTOINCREMENT, stat INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_player", "recordid", "intValue"), ("g2649_bbdx_player", "stat", "intValue")')
        if not self.table_exists('g2649_bbdx_info'):
            cursor.execute('CREATE TABLE g2649_bbdx_info (serialid INT, stat INT, message TEXT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_info", "serialid", "intValue"), ("g2649_bbdx_info", "stat", "intValue"), ("g2649_bbdx_info", "message", "unicodeStringValue")')
        if not self.table_exists('g2649_bbdx_search'):
            cursor.execute('CREATE TABLE g2649_bbdx_search (recordid INTEGER PRIMARY KEY AUTOINCREMENT, song_name TEXT, creator_name TEXT, average_rating REAL, serialid INT, filestore INT, is_lyric INT, num_ratings INT, song_code TEXT, artist_name TEXT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_search", "recordid", "intValue"), ("g2649_bbdx_search", "song_name", "asciiStringValue"), ("g2649_bbdx_search", "creator_name", "asciiStringValue"), ("g2649_bbdx_search", "average_rating", "floatValue"), ("g2649_bbdx_search", "serialid", "intValue"), ("g2649_bbdx_search", "filestore", "intValue"), ("g2649_bbdx_search", "is_lyric", "booleanValue"), ("g2649_bbdx_search", "num_ratings", "intValue"), ("g2649_bbdx_search", "song_code", "asciiStringValue"), ("g2649_bbdx_search", "artist_name", "asciiStringValue")')

        if not self.table_exists('g1443_bbdx_player'):
            cursor.execute('CREATE TABLE g1443_bbdx_player (recordid INTEGER PRIMARY KEY AUTOINCREMENT, stat INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g1443_bbdx_player", "recordid", "intValue"), ("g1443_bbdx_player", "stat", "intValue")')
        if not self.table_exists('g1443_bbdx_info'):
            cursor.execute('CREATE TABLE g1443_bbdx_info (serialid INT, stat INT, message TEXT)')
            cursor.execute('INSERT INTO typedata VALUES ("g1443_bbdx_info", "serialid", "intValue"), ("g1443_bbdx_info", "stat", "intValue"), ("g1443_bbdx_info", "message", "unicodeStringValue")')
        if not self.table_exists('g1443_bbdx_search'):
            cursor.execute('CREATE TABLE g1443_bbdx_search (recordid INTEGER PRIMARY KEY AUTOINCREMENT, song_name TEXT, creator_name TEXT, average_rating REAL, serialid INT, filestore INT, is_lyric INT, num_ratings INT, jasrac_code TEXT, artist_name TEXT)')
            cursor.execute('INSERT INTO typedata VALUES ("g1443_bbdx_search", "recordid", "intValue"), ("g1443_bbdx_search", "song_name", "asciiStringValue"), ("g1443_bbdx_search", "creator_name", "asciiStringValue"), ("g1443_bbdx_search", "average_rating", "floatValue"), ("g1443_bbdx_search", "serialid", "intValue"), ("g1443_bbdx_search", "filestore", "intValue"), ("g1443_bbdx_search", "is_lyric", "booleanValue"), ("g1443_bbdx_search", "num_ratings", "intValue"), ("g1443_bbdx_search", "jasrac_code", "asciiStringValue"), ("g1443_bbdx_search", "artist_name", "asciiStringValue")')
            
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

    def create_column_if_not_exists(self, table, column, sqlType, sakeType):
        if not self.column_exists(table, column):
            cursor = self.db.cursor()
            cursor.execute('ALTER TABLE ' + table + ' ADD COLUMN ' + column + ' ' + sqlType)
            cursor.execute('INSERT INTO typedata VALUES (?, ?, ?)', (table, column, sakeType))
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

    def do_POST(self):
        # Alright, in case anyone is wondering: Yes, I am faking a SOAP service
        # instead of using an actual one. That's because I've tried to do this
        # with several actual python SOAP services and none of them give me the
        # ability to return the exact format that I want.
        # (Or make any kind of sense in case of ZSI...)
        
        if self.path == "/SakeStorageServer/StorageServer.asmx":
            length = int(self.headers['content-length'])
            action = self.headers['SOAPAction']
            post = self.rfile.read(length)
            logger.log(logging.DEBUG, "SakeStorageServer SOAPAction %s", action)
            logger.log(logging.DEBUG, post)
            
            shortaction = action[action.rfind('/')+1:-1]
            
            ret = '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><soap:Body>'
            
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

                if shortaction == 'SearchForRecords':
                    # this is ugly as hell but SearchForRecords can request specific ownerids like this
                    owneriddata = data.getElementsByTagName('ns1:ownerids')
                    if owneriddata and owneriddata[0] and owneriddata[0].firstChild:
                        oids = owneriddata[0].getElementsByTagName('ns1:int')
                        statement += ' WHERE '
                        statement += ' OR '.join('ownerid = '+str(int(oid.firstChild.data)) for oid in oids)

                elif shortaction == 'GetMyRecords':
                    profileid = self.server.gamespydb.get_profileid_from_loginticket(loginticket)
                    statement += ' WHERE ownerid = ' + str(profileid)
                
                elif shortaction == 'GetSpecificRecords':
                    recordids = data.getElementsByTagName('ns1:recordids')[0].getElementsByTagName('ns1:int')
                    
                    # limit to requested records
                    statement += ' WHERE '
                    statement += ' OR '.join('recordid = '+str(int(r.firstChild.data)) for r in recordids)
                        
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
            filedata = cgi.parse_multipart(self.rfile, pdict) 
            
            # make sure users don't upload huge files, dunno what an actual sensible maximum is
            # but 64 KB seems reasonable for what I've seen in WarioWare
            if len(filedata['data'][0]) <= 65536:
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
                    fi.write(filedata['data'][0])
            else:
                logger.log(logging.WARNING, "Tried to upload big file, rejected. (%s bytes)", len(filedata['data'][0]))
                fileid = 0
                retcode = 1
            
            self.send_response(200)

            if retcode == 0:
                self.send_header('Sake-File-Id', str(fileid))

            self.send_header('Sake-File-Result', str(retcode))
            self.end_headers()
            
            logger.log(logging.DEBUG, "SakeFileServer Upload Reply Sake-File-Id %s", fileid)
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
