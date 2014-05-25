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
            cursor.execute('CREATE TABLE g2649_bbdx_search (recordid INTEGER PRIMARY KEY AUTOINCREMENT, song_name TEXT, creator_name TEXT, average_rating REAL, serialid INT, filestore INT, is_lyric INT, num_ratings INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_search", "recordid", "intValue"), ("g2649_bbdx_search", "song_name", "asciiStringValue"), ("g2649_bbdx_search", "creator_name", "asciiStringValue"), ("g2649_bbdx_search", "average_rating", "floatValue"), ("g2649_bbdx_search", "serialid", "intValue"), ("g2649_bbdx_search", "filestore", "intValue"), ("g2649_bbdx_search", "is_lyric", "booleanValue"), ("g2649_bbdx_search", "num_ratings", "intValue")')
        
        # load column info into memory, unfortunately there's no simple way
        # to check for column-existence so get that data in advance
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabledata = cursor.fetchall()
        for t in tabledata:
            cursor.execute("PRAGMA table_info(%s)" % t[0]) # yeah I know but parameters don't work in pragmas, and inserting table names like that should be safe
            columns = cursor.fetchall()
            columndata = []
            for c in columns:
                columndata.append(c[1])
            self.tables[t[0]] = columndata
        
        self.db.commit()
        
    def table_exists(self, name):
        cursor = self.db.cursor()
        cursor.execute("SELECT Count(1) FROM sqlite_master WHERE type='table' AND name=?", (name,))
        exists = cursor.fetchone()[0]
        return True if exists else False
    
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
            if not colname in self.server.tables[table]:
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
                statement += columns[0]
                for c in columns[1:]:
                    statement += ',' + c
                statement += ' FROM ' + table

                if shortaction == 'SearchForRecords':
                    # this is ugly as hell but SearchForRecords can request specific ownerids like this
                    owneriddata = data.getElementsByTagName('ns1:ownerids')
                    if owneriddata:
                        oids = owneriddata[0].getElementsByTagName('ns1:int')
                        statement += ' WHERE ownerid = ' + str(int(oids[0].firstChild.data))
                        for oid in oids[1:]:
                            statement += ' OR ownerid = ' + str(int(oid.firstChild.data))

                elif shortaction == 'GetMyRecords':
                    profileid = self.server.gamespydb.get_profileid_from_loginticket(loginticket)
                    statement += ' WHERE ownerid = ' + str(profileid)
                
                elif shortaction == 'GetSpecificRecords':
                    recordids = data.getElementsByTagName('ns1:recordids')[0].getElementsByTagName('ns1:int')
                    
                    # limit to requested records
                    id = int(recordids[0].firstChild.data)
                    statement += ' WHERE recordid = ' + str(id)
                    for r in recordids[1:]:
                        id = int(r.firstChild.data)
                        statement += ' OR recordid = ' + str(id)
                        
                    
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
                                    ret += '<value>' + str(c) + '</value>'
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

                columndata = []
                values = data.getElementsByTagName('ns1:values')[0]
                recordfields = values.getElementsByTagName('ns1:RecordField')
                for rf in recordfields:
                    columndata.append( rf.getElementsByTagName('ns1:name')[0] )
                    
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
                    
                    statement += columns[0] + ' = ?'
                    for c in columns[1:]:
                        statement += ', ' + c + ' = ?'
                    statement += ' WHERE recordid = ? AND ownerid = ?'
                    rowdata.append( recordid )
                    rowdata.append( profileid )
                elif shortaction == 'CreateRecord':
                    statement = 'INSERT INTO ' + table + ' ('
                    
                    for c in columns:
                        statement += c + ', '
                    statement += 'ownerid) VALUES ('
                    for i in xrange(len(columns)):
                        statement += '?, '
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
                            filename = 'usercontent/' + str(gameid) + '/' + str(profileid) + '/' + str(rowdata[i])
                            filesize = os.path.getsize(filename)
                        cursor.execute('UPDATE ' + table + ' SET ' + attrcol + ' = ? WHERE recordid = ?', (filesize, recordid))
                
                self.server.db.commit()
            
            ret += '</' + shortaction + 'Response>'
            ret += '</soap:Body></soap:Envelope>'
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.end_headers()
            
            logger.log(logging.DEBUG, "%s response to %s", action, self.client_address)
            logger.log(logging.DEBUG, ret)
            self.wfile.write(ret)
        
        elif self.path.startswith("/SakeFileServer/upload.aspx?"):
            params = urlparse.parse_qs(self.path[self.path.find('?')+1:])

            gameid = int(params['gameid'][0])
            playerid = int(params['pid'][0])
            
            logger.log(logging.DEBUG, "SakeFileServer Upload Request in game %s, user %s", gameid, playerid)
            
            ctype, pdict = cgi.parse_header(self.headers['Content-Type'])
            filedata = cgi.parse_multipart(self.rfile, pdict) 
            
            # each user gets his own directory
            userdir = 'usercontent/' + str(gameid) + '/' + str(playerid)
            if not os.path.exists(userdir):
                os.makedirs(userdir)
            
            # filename is the storage database's file_id (at least in WarioWare DIY)
            fileid = random.randint(1, 2147483647)
            while os.path.exists(userdir + '/' + str(fileid)):
                fileid = random.randint(1, 2147483647)
            
            file = open(userdir + '/' + str(fileid), 'wb')
            file.write(filedata['data'][0])
            file.close()
            
            self.send_response(200)
            self.send_header('Sake-File-Id', str(fileid))
            self.send_header('Sake-File-Result', '0')
            self.end_headers()
            
            logger.log(logging.DEBUG, "SakeFileServer Upload Reply Sake-File-Id %s", fileid)
            self.wfile.write('')

        else:
            logger.log(logging.INFO, "[NOT IMPLEMENTED] Got POST request %s from %s", self.path, self.client_address)

    def do_GET(self):
        if self.path.startswith("/SakeFileServer/download.aspx?"):
            params = urlparse.parse_qs(self.path[self.path.find('?')+1:])

            fileid = int(params['fileid'][0])
            gameid = int(params['gameid'][0])
            playerid = int(params['pid'][0])

            logger.log(logging.DEBUG, "SakeFileServer Download Request in game %s, user %s, file %s", gameid, playerid, fileid)

            filename = 'usercontent/' + str(gameid) + '/' + str(playerid) + '/' + str(fileid)
            if not os.path.exists(filename):
                logger.log(logging.WARNING, "User is trying to access non-existing file!")
                return

            file = open(filename, 'rb')
            ret = file.read()
            file.close()
            
            self.send_response(200)
            self.send_header('Sake-File-Result', '0')
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(ret))
            self.end_headers()
            
            self.wfile.write(ret)

        else:
            logger.log(logging.INFO, "[NOT IMPLEMENTED] Got GET request %s from %s", self.path, self.client_address)


if __name__ == "__main__":
    storage_server = StorageServer()
    storage_server.start()
