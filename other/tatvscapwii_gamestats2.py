import re,struct,utils,logging,hashlib,base64,sqlite3,time,json

salt='QFFeWypIFepXgAhZxeNy'

lbheader='\x05\x00\x00\x00A\x00\x00\x00<\x05\x00\x00;\x03\x00\x00'

rankinglabels = ["Beginner","Rookie","SuperRookie","UltraRookie","Fighter","SuperFighter",\
"UltraFighter","Ace","SuperAce","UltraAce","Champ","SuperChamp","UltraChamp","Master",\
"SuperMaster","UltraMaster","King","SuperKing","UltraKing","Star","SuperStar",\
"UltraStar","Hero","SuperHero","UltraHero","LegendHero","UltimateHero"]

respheaders ="""HTTP/1.1 200 OK\r
Date: Thu, 19 May 2011 07:34:16 GMT\r
Server: Microsoft-IIS/6.0\r
p3p: CP='NOI ADMa OUR STP'\r
X-Powered-By: ASP.NET(but really altwfc's twisted python)\r
cluster-server: gstprdweb13.las1.colo.ignops.com\r
Content-Length: _CONTENT_LENGTH\r
Content-Type: text/html\r
Set-Cookie: ASPSESSIONIDSQQQDSCC=GIPIIGECEJLOAHGENKMFFPOC; path=/\r
Cache-control: private\r\n\r\n"""

tokenreply="""HTTP/1.1 200 OK\r
Date: Thu, 19 May 2011 07:34:09 GMT\r
Server: Microsoft-IIS/6.0\r
p3p: CP='NOI ADMa OUR STP'\r
X-Powered-By: ASP.NET\r
cluster-server: gstprdweb13.las1.colo.ignops.com\r
Content-Length: 32\r
Content-Type: text/html\r
Set-Cookie: ASPSESSIONIDCASRDSQR=KIFBODGCOEEENDODFFHCIKIG; path=/\r
Cache-control: private\r
\r
Oro9JPebT0c3gPr0VshyZ1bF6PNL6T1k"""

donereply="""HTTP/1.1 200 OK\r
Date: Sat, 07 May 2011 13:08:35 GMT\r
Server: Microsoft-IIS/6.0\r
p3p: CP='NOI ADMa OUR STP'\r
X-Powered-By: ASP.NET\r
cluster-server: gstprdweb13.las1.colo.ignops.com\r
Content-Length: 44\r
Content-Type: text/html\r
Set-Cookie: ASPSESSIONIDQQCADDRC=FNGBCLJCKMKJGCDPPGCPGNJG; path=/\r
Cache-control: private\r
\r
doneb7e684e8313b5729fd1c70a3fc19e425700449f6"""


# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "TATVSCAPWIIgamestats2"
logger_filename = "tatvscapwii_gamestats2.log"
dbfilename = 'tatvscapwii_leaderboard.db'
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

conn = sqlite3.connect(dbfilename)
conn.cursor().execute('CREATE TABLE IF NOT EXISTS leaderboard (ingamesn TEXT, profileid INT UNIQUE, battlepoints INT, chartdata TEXT, utctimestamp INT)')
conn.commit()
conn.close()

def emptyreply():
  replypayload = '\x00'*200
  replypayload = lbheader.replace("A",struct.pack('B',0))+replypayload
  replypayload += hashlib.sha1(salt+base64.urlsafe_b64encode(replypayload)+salt).hexdigest()
  return respheaders.replace("_CONTENT_LENGTH",str(len(replypayload)))+replypayload

def leaderboard_best_ingame():
    replypayload = '' 
    conn = sqlite3.connect(dbfilename)
    count = 0
    for row in conn.cursor().execute('select chartdata from leaderboard order by battlepoints desc limit 20'):
      replypayload += base64.urlsafe_b64decode(str(row[0]))
      count += 1
    conn.close()
    replypayload = lbheader.replace("A",struct.pack('B',count))+replypayload
    replypayload += hashlib.sha1(salt+base64.urlsafe_b64encode(replypayload)+salt).hexdigest()
    return respheaders.replace("_CONTENT_LENGTH",str(len(replypayload)))+replypayload 

def leaderboard_json(limit):
    records = []
    conn = sqlite3.connect(dbfilename)
    count = 0
    for row in conn.cursor().execute('select * from leaderboard order by battlepoints desc limit ?',(limit,)):
      binarydata = base64.urlsafe_b64decode(str(row[3]))
      r = {}
      r['ingamesn'] = row[0]
      r['dwc_pid'] = str(row[1])
      r['BP'] = str(row[2])
      r['utctimestamp'] = str(int(row[4]))
      r['totalmatches'] = str(struct.unpack(">H",binarydata[34:36])[0])
      r['wins'] = str(struct.unpack(">H",binarydata[22:24])[0])
      r['losses'] = str(struct.unpack(">H",binarydata[30:32])[0])
      r['draws'] = str(struct.unpack(">H",binarydata[26:28])[0])
      r['ranking'] = rankinglabels[struct.unpack("B",binarydata[63])[0]] 
      records.append(r)
    replypayload = json.dumps(records)      
    return respheaders.replace("_CONTENT_LENGTH",str(len(replypayload)))+replypayload 
  
def handle_request(httpserver):
  p = httpserver.path
  address = str(httpserver.client_address)
  logger.log(logging.INFO,address+" Received "+p)

  if "pid=" in p and "hash=" not in p:
    logger.log(logging.INFO,address+" Replying with token")
    httpserver.wfile.write(tokenreply)

  elif 'limit' in p:
    limit = re.findall('limit=(\d+)',p)[0]
    logger.log(logging.INFO,address+"reply with leaderboard data limit "+limit)
    httpserver.wfile.write(leaderboard_json(limit))

  elif "hash=" in p and "put2.asp" in p:
    d = re.findall('data=(.*)',p)[0]
    binarydata = base64.urlsafe_b64decode(d)
    if binarydata[16] == '\x00' and len(binarydata) == 104:#This is data for overall best chart.
      ingamesn = binarydata[72:].replace('\x00','').lstrip(' ').rstrip(' ')
      pid = struct.unpack("<I",binarydata[4:8])[0]
      bp = struct.unpack("<H",binarydata[20:22])[0]
      binarydata = binarydata[4:]#remove 4-byte checksum
      #structure needs rearranging(and dropping of 4 bytes) for leaderboard.
      part1 = binarydata[:4]
      part2 = binarydata[16:20]
      part3 = binarydata[8:16]
      part4 = binarydata[20:]
      binarydata = part1+part2+part3+part4+'\x00\x00\x00\x00'
      d = base64.urlsafe_b64encode(binarydata)
      conn = sqlite3.connect(dbfilename)
      conn.cursor().execute('INSERT OR REPLACE INTO leaderboard values (?,?,?,?,?)',(ingamesn,pid,bp,d,time.time()))
      conn.commit()
      conn.close()
      logger.log(logging.INFO,address+" Leaderboard entry: %s %s %s" % (ingamesn,str(pid),str(bp)))
    logger.log(logging.INFO,address+" Replying with done")
    httpserver.wfile.write(donereply)

  elif "hash=" in p and "get2.asp" in p:
    d = re.findall('data=(.*)',p)[0]
    binarydata = base64.urlsafe_b64decode(d)
    if binarydata[16] == '\x00' and binarydata[32] == '\x14':
      logger.log(logging.INFO,address+"reply with leaderboard data")
      httpserver.wfile.write(leaderboard_best_ingame())
    elif binarydata[16] == '\x00' and binarydata[32] == '\x02': 
      logger.log(logging.INFO,address+"reply with emptydata because no selfdata support right now")
      httpserver.wfile.write(emptyreply())
    else: 
      logger.log(logging.INFO,address+"Reply with emptydata")
      httpserver.wfile.write(emptyreply())

  else:
    logger.log(logging.INFO,address+" I have no idea what's going on")
    httpserver.wfile.write('Do not know what to tell you')

