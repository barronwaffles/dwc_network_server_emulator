import logging
import BaseHTTPServer
import sqlite3
import xml.dom.minidom as minidom

import other.utils as utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "StorageServer"
logger_filename = "storage_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

address = ("127.0.0.1", 8000)

class StorageServer(object):
    def start(self):
        httpd = StorageHTTPServer((address[0], address[1]), StorageHTTPServerHandler)
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()

class StorageHTTPServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        
        self.db = sqlite3.connect('storage.db')
        self.tables = {}
        
        cursor = self.db.cursor()
        
        if not self.table_exists('typedata'):
            cursor.execute('CREATE TABLE typedata (tbl TEXT, col TEXT, type TEXT)')
            
        if not self.table_exists('g2050_box_us_eu'):
            cursor.execute('CREATE TABLE g2050_box_us_eu (recordid INT, ownerid INT, m_enable INT, m_type INT, m_index INT, m_file_id INT, m_header TEXT, m_file_id___size INT, m_file_id___create_time DATETIME, m_file_id___downloads INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2050_box_us_eu", "recordid", "intValue"), ("g2050_box_us_eu", "ownerid", "intValue"), ("g2050_box_us_eu", "m_enable", "booleanValue"), ("g2050_box_us_eu", "m_type", "intValue"), ("g2050_box_us_eu", "m_index", "intValue"), ("g2050_box_us_eu", "m_file_id", "intValue"), ("g2050_box_us_eu", "m_header", "binaryDataValue"), ("g2050_box_us_eu", "m_file_id___size", "intValue"), ("g2050_box_us_eu", "m_file_id___create_time", "dateAndTimeValue"), ("g2050_box_us_eu", "m_file_id___downloads", "intValue")')
        
        if not self.table_exists('g2649_bbdx_player'):
            cursor.execute('CREATE TABLE g2649_bbdx_player (recordid INT, stat INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_player", "recordid", "intValue"), ("g2649_bbdx_player", "stat", "intValue")')
        if not self.table_exists('g2649_bbdx_info'):
            cursor.execute('CREATE TABLE g2649_bbdx_info (serialid INT, stat INT, message TEXT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_info", "serialid", "intValue"), ("g2649_bbdx_info", "stat", "intValue"), ("g2649_bbdx_info", "message", "unicodeStringValue")')
        if not self.table_exists('g2649_bbdx_search'):
            cursor.execute('CREATE TABLE g2649_bbdx_search (song_name TEXT, creator_name TEXT, average_rating REAL, serialid INT, recordid INT, filestore INT, is_lyric INT, num_ratings INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_search", "song_name", "asciiStringValue"), ("g2649_bbdx_search", "creator_name", "asciiStringValue"), ("g2649_bbdx_search", "average_rating", "floatValue"), ("g2649_bbdx_search", "serialid", "intValue"), ("g2649_bbdx_search", "recordid", "intValue"), ("g2649_bbdx_search", "filestore", "intValue"), ("g2649_bbdx_search", "is_lyric", "booleanValue"), ("g2649_bbdx_search", "num_ratings", "intValue")')
        
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
            
            shortaction = action[action.rfind('/')+1:-1]
            
            ret = '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><soap:Body>'
            
            dom = minidom.parseString(post)
            data = dom.getElementsByTagName('SOAP-ENV:Body')[0].getElementsByTagName('ns1:' + shortaction)[0]
            gameid = str(int(data.getElementsByTagName('ns1:gameid')[0].firstChild.data))
            tableid = data.getElementsByTagName('ns1:tableid')[0].firstChild.data
            
            table = 'g' + gameid + '_' + tableid
            
            if not self.server.table_exists(table):
                logger.log(logging.WARNING, "Unknown table access '%s' in %s by %s", table, shortaction, self.client_address)
                return
            
            # TODO: Actually make GetMyRecords only return *my* records
            if action == '"http://gamespy.net/sake/SearchForRecords"' or action == '"http://gamespy.net/sake/GetMyRecords"':
                columndata = data.getElementsByTagName('ns1:fields')[0].getElementsByTagName('ns1:string')
                try:
                    columns = self.confirm_columns(columndata, table)
                except IllegalColumnAccessException as e:
                    logger.log(logging.WARNING, "IllegalColumnAccess: %s in %s by %s", e.message, shortaction, self.client_address)
                    return
                    
                ret += '<SearchForRecordsResponse xmlns="http://gamespy.net/sake">'
                ret += '<SearchForRecordsResult>Success</SearchForRecordsResult>'

                # build SELECT statement, yes I know one shouldn't do this but I cross-checked the table name and all the columns above so it should be fine
                statement = 'SELECT '
                statement += columns[0]
                for c in columns[1:]:
                    statement += ',' + c
                statement += ' FROM ' + table
                    
                cursor = self.server.db.cursor()
                cursor.execute(statement)
                rows = cursor.fetchall()
                
                if rows:
                    ret += '<values>'
                    for r in rows:
                        ret += '<ArrayOfRecordValue>'
                        for i, c in enumerate(r):
                            ret += '<RecordValue>'
                            ret += '<' + self.server.get_typedata(table, columns[i]) + '>'
                            if c:
                                ret += '<value>' + str(c) + '</value>'
                            else:
                                ret += '<value/>'
                            ret += '</' + self.server.get_typedata(table, columns[i]) + '>'
                            ret += '</RecordValue>'
                        ret += '</ArrayOfRecordValue>'
                    ret += '</values>'
                else:
                    ret += '<values/>'
                
                ret += '</SearchForRecordsResponse>'
                
            elif action == '"http://gamespy.net/sake/GetRecordCount"':
                ret += '<GetRecordCountResponse xmlns="http://gamespy.net/sake">'
                ret += '<GetRecordCountResult>Success</GetRecordCountResult>'
                
                statement = 'SELECT COUNT(1) FROM ' + table
                    
                cursor = self.server.db.cursor()
                cursor.execute(statement)
                count = cursor.fetchone()[0]
                
                ret += '<count>' + str(count) + '</count>'                
                ret += '</GetRecordCountResponse>'
            
            ret += '</soap:Body></soap:Envelope>'
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.end_headers()
            
            logger.log(logging.DEBUG, "%s response to %s", action, self.client_address)
            logger.log(logging.DEBUG, ret)
            self.wfile.write(ret)
        
        else:
            logger.log(logging.INFO, "Got request %s from %s", self.path, self.client_address)

if __name__ == "__main__":
    storage_server = StorageServer()
    storage_server.start()
