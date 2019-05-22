"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
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

import os
import random
import time
from datetime import date

from gamespy.gs_database import GamespyDatabase

"""
  Pokemon Gen 4 Region Codes:
  
  Diamond:
    ADAE (US)
    ADAP (ENG-EUR)
    ADAF (FRA)
    ADAD (GER)
    ADAI (ITA)
    ADAS (SPA)
    ADAJ (JPN)
    ADAK (KOR)
  Pearl:
    APAE (US)
    APAP (ENG-EUR)
    APAF (FRA)
    APAD (GER)
    APAI (ITA)
    APAS (SPA)
    APAJ (JPN)
    APAK (KOR)
  Platinum:
    CPUE (US)
    CPUP (ENG-EUR)
    CPUF (FRA)
    CPUD (GER)
    CPUI (ITA)
    CPUS (SPA)
    CPUJ (JPN)
    CPUK (KOR)
  HeartGold:
    IPKE (US)
    IPKP (ENG-EUR)
    IPKF (FRA)
    IPKD (GER)
    IPKI (ITA)
    IPKS (SPA)
    IPKJ (JPN)
    IPKK (KOR)
  SoulSilver:
    IPGE (US)
    IPGP (ENG-EUR)
    IPGF (FRA)
    IPGD (GER)
    IPGI (ITA)
    IPGS (SPA)
    IPGJ (JPN)
    IPGK (KOR)
  """

# Gen 4 Pokemon Games (for Mystery Gift Distribution)
# If a game from this list requests a file listing, the server will compare
# the client Nintendo DS's date setting to the list of Mystery Gifts
# that were actually distributed in real life at the given time.
# This way, if someone knows exactly when an event happened in real life,
# they know exactly which date to change to in order to receive a particular gift.
gen_4_pokemon_gamecodes = [
    'ADAE',
    'ADAP',
    'ADAF',
    'ADAD',
    'ADAI',
    'ADAS',
    'ADAJ',
    'ADAK',
    'APAE',
    'APAP',
    'APAF',
    'APAD',
    'APAI',
    'APAS',
    'APAJ',
    'APAK',
    'CPUE',
    'CPUP',
    'CPUF',
    'CPUD',
    'CPUI',
    'CPUS',
    'CPUJ',
    'CPUK',
    'IPKE',
    'IPKP',
    'IPKF',
    'IPKD',
    'IPKI',
    'IPKS',
    'IPKJ',
    'IPKK',
    'IPGE',
    'IPGP',
    'IPGF',
    'IPGD',
    'IPGI',
    'IPGS',
    'IPGJ',
    'IPGK'
]

filter_bit_g5 = {
    'A': 0x100000,
    'B': 0x200000,
    'D': 0x400000,
    'E': 0x800000
}


def get_file_count(data):
    return sum(1 for line in data.splitlines() if line)


def filter_list(data, attr1=None, attr2=None, attr3=None,
                num=None, offset=None):
    """Filter the list based on the attribute fields.

    If nothing matches, at least return a newline.
    Pokemon BW at least expects this and will error without it.
    """
    if attr1 is None and attr2 is None and attr3 is None and \
       num is None and offset is None:
        # Nothing to filter, just return the input data
        return data

    def attrs(data):
        """Filter attrs."""
        def nc(a, b):
            """Filter nc."""
            return a is None or a == b
        return \
            len(data) == 6 and \
            nc(attr1, data[2]) and \
            nc(attr2, data[3]) and \
            nc(attr3, data[4])
    output = filter(lambda line: attrs(line.split("\t")), data.splitlines())

    if offset is not None:
        output = output[offset:]

    if num is not None:
        output = output[:num]

    return '\r\n'.join(output) + '\r\n'


def filter_list_random_files(data, count):
    """Get [count] random files from the filelist."""
    samples = random.sample(data.splitlines(), count)
    return '\r\n'.join(samples) + '\r\n'

def todays_g4_event_filename(today, gamecd):
  # Pokemon Diamond/Pearl/Platinum/HeartGold/SoulSilver Events
  if (gamecd.endswith("J") or gamecd.endswith("K")) == False:
    # International Events

    # Secret Key, WC 17, Platinum Only (First and Second Distributions)
    if(date(2009, 4, 20) <= today <= date(2009, 5, 12)) or (date(2009, 6, 8) <= today <= date(2009, 7, 19)):
      if gamecd in ['CPUE', 'CPUP']:
        return "ENG_017_Plat_SecretKey.myg"
      elif gamecd == "CPUF":
        return "FRA_017_Plat_SecretKey.myg"
      elif gamecd == "CPUD":
        return "GER_017_Plat_SecretKey.myg"
      elif gamecd == "CPUI":
        return "ITA_017_Plat_SecretKey.myg"
      elif gamecd == "CPUS":
        return "SPN_017_Plat_SecretKey.myg"

    # Member Card, WC 18, Platinum Only
    if date(2009, 8, 3) <= today <= date(2009, 9, 13):
      if gamecd in ['CPUE', 'CPUP']:
        return "ENG_018_Plat_MemberCard.myg"
      elif gamecd == "CPUF":
        return "FRA_018_Plat_MemberCard.myg"
      elif gamecd == "CPUD":
        return "GER_018_Plat_MemberCard.myg"
      elif gamecd == "CPUI":
        return "ITA_018_Plat_MemberCard.myg"
      elif gamecd == "CPUS":
        return "SPN_018_Plat_MemberCard.myg"

    # Oak's Letter, WC 20, Platinum Only
    if date(2009, 9, 28) <= today <= date(2009, 11, 8):
      if gamecd in ['CPUE', 'CPUP']:
        return "ENG_020_Plat_OaksLetter.myg"
      elif gamecd == "CPUF":
        return "FRA_020_Plat_OaksLetter.myg"
      elif gamecd == "CPUD":
        return "GER_020_Plat_OaksLetter.myg"
      elif gamecd == "CPUI":
        return "ITA_020_Plat_OaksLetter.myg"
      elif gamecd == "CPUS":
        return "SPN_020_Plat_OaksLetter.myg"

    # Azure Flute, WC 119, Platinum Only (Custom, never released)
    # Distribution time is set to around the same time as
    # the real-life Arceus distribution in the US, with an extension past the movie airdate
    if date(2009, 11, 9) <= today <= date(2009, 11, 30):
      if gamecd in ['CPUE', 'CPUP']:
        return "ENG_119_Plat_AzureFlute.myg"
      elif gamecd == "CPUF":
        return "FRA_119_Plat_AzureFlute.myg"
      elif gamecd == "CPUD":
        return "GER_119_Plat_AzureFlute.myg"
      elif gamecd == "CPUI":
        return "ITA_119_Plat_AzureFlute.myg"
      elif gamecd == "CPUS":
        return "SPN_119_Plat_AzureFlute.myg"

    # Pikachu-Colored Pichu, WC 21, D/P/Pt
    if date(2010, 3, 5) <= today <= date(2010, 3, 25):
      if gamecd in ['CPUE', 'CPUP', 'ADAE', 'ADAP', 'APAE', 'APAP']:
        return "ENG_021_DPPt_ShinyPichu.myg"
      elif gamecd in ['ADAF','APAF', 'CPUF']:
        return "FRA_021_DPPt_ShinyPichu.myg"
      elif gamecd in ['ADAD','APAD', 'CPUD']:
        return "GER_021_DPPt_ShinyPichu.myg"
      elif gamecd in ['ADAI','APAI', 'CPUI']:
        return "ITA_021_DPPt_ShinyPichu.myg"
      elif gamecd in ['ADAS','APAS', 'CPUS']:
        return "SPN_021_DPPt_ShinyPichu.myg"
    
    # Yellow Forest Pokewalker Route, WC 48, HG/SS
    if date(2010, 4, 1) <= today <= date(2010, 5, 5):
      if gamecd in ['IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_048_HGSS_YForest.myg"
      elif gamecd in ['IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_048_HGSS_YForest.myg"
      elif gamecd in ['IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_048_HGSS_YForest.myg"
      elif gamecd in ['IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_048_HGSS_YForest.myg"
      elif gamecd in ['IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_048_HGSS_YForest.myg"
    
    # Winner's Path Pokewalker Route, WC 51, HG/SS
    if date(2010, 5, 6) <= today <= date(2010, 6, 25):
      if gamecd in ['IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_051_HGSS_WinPath.myg"
      elif gamecd in ['IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_051_HGSS_WinPath.myg"
      elif gamecd in ['IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_051_HGSS_WinPath.myg"
      elif gamecd in ['IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_051_HGSS_WinPath.myg"
      elif gamecd in ['IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_051_HGSS_WinPath.myg"

    # Summer 2010 Jirachi (Night Sky), WC 24, D/P/Pt/HG/SS
    if date(2010, 6, 26) <= today <= date(2010, 7, 16):
      if gamecd in ['CPUE', 'CPUP', 'ADAE', 'ADAP', 'APAE', 'APAP', 'IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_024_ALL_Jirachi_NightSky.myg"
      elif gamecd in ['ADAF','APAF', 'CPUF', 'IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_024_ALL_Jirachi_NightSky.myg"
      elif gamecd in ['ADAD','APAD', 'CPUD', 'IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_024_ALL_Jirachi_NightSky.myg"
      elif gamecd in ['ADAI','APAI', 'CPUI', 'IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_024_ALL_Jirachi_NightSky.myg"
      elif gamecd in ['ADAS','APAS', 'CPUS', 'IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_024_ALL_Jirachi_NightSky.myg"
    
    # Engima Stone, WC 54, HG/SS
    if date(2010, 7, 31) <= today <= date(2010, 8, 27):
      if gamecd in ['IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_054_HGSS_EnigmaStone.myg"
      elif gamecd in ['IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_054_HGSS_EnigmaStone.myg"
      elif gamecd in ['IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_054_HGSS_EnigmaStone.myg"
      elif gamecd in ['IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_054_HGSS_EnigmaStone.myg"
      elif gamecd in ['IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_054_HGSS_EnigmaStone.myg"
    
    # Fall 2010/10th Anniversary Mew, WC 53, HG/SS
    if date(2010, 10, 15) <= today <= date(2010, 10, 30):
      if gamecd in ['IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_053_HGSS_10AnnivMew.myg"
      elif gamecd in ['IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_053_HGSS_10AnnivMew.myg"
      elif gamecd in ['IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_053_HGSS_10AnnivMew.myg"
      elif gamecd in ['IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_053_HGSS_10AnnivMew.myg"
      elif gamecd in ['IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_053_HGSS_10AnnivMew.myg"
    
    # Winter 2011 Shiny Raikou, WC 59, D/P/Pt/HG/SS
    if date(2011, 2, 7) <= today <= date(2011, 2, 13):
      if gamecd in ['CPUE', 'CPUP', 'ADAE', 'ADAP', 'APAE', 'APAP', 'IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_059_ALL_ShinyRaikou.myg"
      elif gamecd in ['ADAF','APAF', 'CPUF', 'IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_059_ALL_ShinyRaikou.myg"
      elif gamecd in ['ADAD','APAD', 'CPUD', 'IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_059_ALL_ShinyRaikou.myg"
      elif gamecd in ['ADAI','APAI', 'CPUI', 'IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_059_ALL_ShinyRaikou.myg"
      elif gamecd in ['ADAS','APAS', 'CPUS', 'IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_059_ALL_ShinyRaikou.myg"
    
    # Winter 2011 Shiny Entei, WC 60, D/P/Pt/HG/SS
    if date(2011, 2, 14) <= today <= date(2011, 2, 20):
      if gamecd in ['CPUE', 'CPUP', 'ADAE', 'ADAP', 'APAE', 'APAP', 'IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_060_ALL_ShinyEntei.myg"
      elif gamecd in ['ADAF','APAF', 'CPUF', 'IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_060_ALL_ShinyEntei.myg"
      elif gamecd in ['ADAD','APAD', 'CPUD', 'IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_060_ALL_ShinyEntei.myg"
      elif gamecd in ['ADAI','APAI', 'CPUI', 'IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_060_ALL_ShinyEntei.myg"
      elif gamecd in ['ADAS','APAS', 'CPUS', 'IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_060_ALL_ShinyEntei.myg"
    
    #Winter 2011 Shiny Suicune, WC 61, D/P/Pt/HG/SS
    if date(2011, 2, 21) <= today <= date(2011, 2, 27):
      if gamecd in ['CPUE', 'CPUP', 'ADAE', 'ADAP', 'APAE', 'APAP', 'IPKE', 'IPGE', 'IPKP', 'IPGP']:
        return "ENG_061_ALL_ShinySuicune.myg"
      elif gamecd in ['ADAF','APAF', 'CPUF', 'IPKF', 'IPGF', 'IPKF', 'IPGF']:
        return "FRA_061_ALL_ShinySuicune.myg"
      elif gamecd in ['ADAD','APAD', 'CPUD', 'IPKD', 'IPGD', 'IPKD', 'IPGD']:
        return "GER_061_ALL_ShinySuicune.myg"
      elif gamecd in ['ADAI','APAI', 'CPUI', 'IPKI', 'IPGI', 'IPKI', 'IPGI']:
        return "ITA_061_ALL_ShinySuicune.myg"
      elif gamecd in ['ADAS','APAS', 'CPUS', 'IPKS', 'IPGS', 'IPKS', 'IPGS']:
        return "SPN_061_ALL_ShinySuicune.myg"
    
    # If we reach this point without returning an event, no event was found
    return "null"
  elif gamecd.endswith("J"):
    # Japanese Events
    # Secret Key, WC 156, Platinum Only (First Distribution)
    if date(2008, 9, 28) <= today <= date(2008, 11, 14):
      if gamecd == "CPUJ":
        return "JPN_156_Plat_SecretKey.myg"
    
    # Member Card, WC 36, Platinum Only
    if date(2008, 12, 1) <= today <= date(2009, 1, 15):
      if gamecd == "CPUJ":
        return "JPN_036_Plat_MemberCard.myg"
    
    # Secret Key, WC 156, Platinum Only (Second Distribution)
    if date(2009, 1, 16) <= today <= date(2009, 3, 2):
      if gamecd == "CPUJ":
        return "JPN_156_Plat_SecretKey.myg"
    
    # Oak's Letter, WC 44, Platinum Only
    if date(2009, 4, 18) <= today <= date(2009, 5, 11):
      if gamecd == "CPUJ":
        return "JPN_044_Plat_OaksLetter.myg"
    
    # Nintendo Zone Jirachi, WC 46, D/P/Pt
    if date(2009, 6, 19) <= today <= date(2009, 7, 17):
      if gamecd in ['ADAJ', 'APAJ', 'CPUJ']:
        return "JPN_046_DPPt_NZ_Jirachi.myg"
    
    # Azure Flute, WC 119, Platinum Only (Custom, never released)
    # Distribution time is set to nearly the same date range as the real-life
    # Japanese Arceus distribution, apart from being cut short for the
    # Pokewalker distribution directly below this code block
    if date(2009, 7, 18) <= today <= date(2009, 9, 17):
      if gamecd in ['CPUJ']:
        return "JPN_119_Plat_AzureFlute.myg"

    # Yellow Forest Pokewalker Route, WC 48, HG/SS (First Distribution)
    if date(2009, 9, 18) <= today <= date(2009, 11, 10):
      if gamecd in ['IPKJ', 'IPGJ']:
        return "JPN_048_HGSS_YForest.myg"
    
    # 10th Anniversary Mew, WC 53, HG/SS (First Distribution)
    if date(2009, 11, 11) <= today <= date(2009, 11, 23):
      if gamecd in ['IPKJ', 'IPGJ']:
        return "JPN_053_HGSS_10AnnivMew.myg"
      
    # Engima Stone, WC 54, HG/SS
    if date(2009, 11, 27) <= today <= date(2010, 1, 11):
      if gamecd in ['IPKJ', 'IPGJ']:
        return "JPN_054_HGSS_EnigmaStone.myg" 
    
    # Winner's Path Pokewalker Route, WC 51, HG/SS
    if date(2010, 1, 13) <= today <= date(2010, 1, 27):
      if gamecd in ['IPKJ', 'IPGJ']:
        return "JPN_051_HGSS_WinPath.myg"
    
    # 10th Anniversary Mew, WC 53, D/P/Pt/HG/SS (Second Distribution)
    if date(2010, 1, 29) <= today <= date(2010, 2, 14):
      if gamecd in ['IPKJ', 'IPGJ']:
        return "JPN_053_ALL_10AnnivMew.myg"

    # Yellow Forest Pokewalker Route, WC 48, HG/SS (Second Distribution)
    if date(2010, 2, 16) <= today <= date(2010, 2, 28):
      if gamecd in ['IPKJ', 'IPGJ']:
        return "JPN_048_HGSS_YForest.myg"

    # Goone's Scizor, WC 63, D/P/Pt/HG/SS
    if date(2010, 6, 18) <= today <= date(2010, 7, 14):
      if gamecd in ['ADAJ', 'APAJ', 'CPUJ', 'IPKJ', 'IPGJ']:
        return "JPN_063_ALL_GooneScizor.myg"

    # Ash's Pikachu, WC 65, D/P/Pt/HG/SS
    if date(2010, 7, 15) <= today <= date(2010, 8, 10):
      if gamecd in ['ADAJ', 'APAJ', 'CPUJ', 'IPKJ', 'IPGJ']:
        return "JPN_065_ALL_AshPikachu.myg"
    
    # Nintendo Zone Manaphy, WC 66, D/P/Pt/HG/SS
    if date(2010, 8, 14) <= today <= date(2010, 9, 12):
      if gamecd in ['ADAJ', 'APAJ', 'CPUJ', 'IPKJ', 'IPGJ']:
        return "JPN_066_ALL_NZ_Manaphy.myg"
    
    # If we reach this point without returning an event, no event was found
    return "null"
  elif gamecd.endswith("K"):
    # Korean Events

    # Azure Flute, WC 119, Platinum Only (Custom, never released)
    # Distribution time is set to the same date range as the real-life
    # Korean Arceus distribution, which was distributed at showings of
    # "Arceus and the Jewel of Life"
    if date(2009, 12, 24) <= today <= date(2010, 1, 31):
      if gamecd in ['CPUK']:
        return "KOR_119_Plat_AzureFlute.myg"

    # Yellow Forest Pokewalker Route, WC 22, HG/SS
    if date(2010, 2, 4) <= today <= date(2010, 3, 31):
      if gamecd in ['IPKK', 'IPGK']:
        return "KOR_022_HGSS_YForest.myg"

    # Enigma Stone, WC 26, HG/SS
    if date(2010, 7, 26) <= today <= date(2010, 8, 31):
      if gamecd in ['IPKK', 'IPGK']:
        return "KOR_026_HGSS_EnigmaStone.myg"

    # Winner's Path Pokewalker Route, WC 25, HG/SS
    if date(2010, 9, 1) <= today <= date(2010, 10, 31):
      if gamecd in ['IPKK', 'IPGK']:
        return "KOR_025_HGSS_WinPath.myg"

    # Goone's Scizor, WC 63, D/P/Pt/HG/SS
    if date(2011, 1, 7) <= today <= date(2011, 1, 31):
      if gamecd in ['ADAK', 'APAK', 'CPUK', 'IPKK', 'IPGK']:
        return "KOR_063_ALL_GooneScizor.myg"

    # Ash's Pikachu, WC 65, D/P/Pt/HG/SS
    if date(2011, 2, 1) <= today <= date(2011, 2, 28):
      if gamecd in ['ADAK', 'APAK', 'CPUK', 'IPKK', 'IPGK']:
        return "KOR_065_ALL_AshPikachu.myg"

    # If we reach this point without returning an event, no event was found
    return "null"
  else:
    return "null"

def filter_list_g4_mystery_gift(data, token, gamecd, dlc_path):
    """Allow user to control which file to receive by setting the local date.

    Selected file will be served according to that file's original real-life Mystery Gift release date,
    on a per-gameid basis. For example, the Member Card will be served to gameid CPUJ between the local
    dates of December 1st 2008 and January 15th 2009, and to the gameid CPUE between the local dates of
    August 3rd 2009 and September 13th 2009.

    All Mystery Gift release timings were sourced from Bulbapedia and Serebii. They are defined in
    the function `todays_g4_event_filename()`

    I've done my best to include all events across all regions, however only Wi-Fi events have been included.
    However, I have also included my own custom-made Azure Flute distributions for all regions as well; we all
    know that the Azure Flute was never distributed, but I think we can all agree it absolutely should have been!"""
    try:
        userData = GamespyDatabase().get_nas_login(token)
        time_struct = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
        ds_date = date(time_struct.tm_year, time_struct.tm_mon, time_struct.tm_mday)
        event_filename = todays_g4_event_filename(ds_date, gamecd)
        if event_filename != "null":
          event_size = str(os.path.getsize(os.path.join(dlc_path, event_filename)))
          ret = event_filename + "\t\t\t\t\t" + event_size + '\r\n'
        else:
          files = data.splitlines()
          ret = files[(int(ds_date.tm_yday) - 1) % len(files)] + '\r\n'
    except:
        ret = filter_list_random_files(data, 1)
    return ret

def filter_list_by_date(data, token):
    """Allow user to control which file to receive by setting
    the local date selected file will be the one at
    index (day of year) mod (file count)."""
    try:
        userData = GamespyDatabase().get_nas_login(token)
        date = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
        files = data.splitlines()
        ret = files[(int(date.tm_yday) - 1) % len(files)] + '\r\n'
    except:
        ret = filter_list_random_files(data, 1)
    return ret


def filter_list_g5_mystery_gift(data, rhgamecd):
    """Custom selection for generation 5 mystery gifts, so that the random
    or data-based selection still works properly."""
    if len(rhgamecd) < 2 or rhgamecd[2] not in filter_bit_g5:
        # unknown game, can't filter
        return data
    filter_bit = filter_bit_g5[rhgamecd[2]]

    output = []
    for line in data.splitlines():
        attrs = line.split('\t')
        if len(attrs) < 3:
            continue
        line_bits = int(attrs[3], 16)
        if line_bits & filter_bit == filter_bit:
            output.append(line)
    return '\r\n'.join(output) + '\r\n'


def safeloadfi(dlc_path, name, mode='rb'):
    """safeloadfi : string -> string

    Safely load contents of a file, given a filename,
    and closing the file afterward.
    """
    try:
        with open(os.path.join(dlc_path, name), mode) as f:
            return f.read()
    except:
        return None


def download_count(dlc_path, post):
    """Handle download count request."""
    gamecd = post["gamecd"]

    if gamecd in gen_4_pokemon_gamecodes:
      userData = GamespyDatabase().get_nas_login(post["token"])
      time_struct = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
      ds_date = date(time_struct.tm_year, time_struct.tm_mon, time_struct.tm_mday)
      event_filename = todays_g4_event_filename(ds_date, gamecd)
      if todays_g4_event_filename(ds_date, gamecd) != "null":
        return "1"
      else:
        return "0"
    if os.path.exists(dlc_path):
        attr1 = post.get("attr1", None)
        attr2 = post.get("attr2", None)
        attr3 = post.get("attr3", None)
        if os.path.isfile(os.path.join(dlc_path, "_list.txt")):
            dlc_file = safeloadfi(dlc_path, "_list.txt")
            ls = filter_list(dlc_file, attr1, attr2, attr3)
            return "{}".format(get_file_count(ls))
        elif attr1 is None and attr2 is None and attr3 is None:
            return "{}".format(len(os.listdir(dlc_path)))
    return "0"


def download_size(dlc_path, name):
    """Return download filename and size.

    Used in download list.
    """
    return (name, str(os.path.getsize(os.path.join(dlc_path, name))))


def download_list(dlc_path, post):
    """Handle download list request.

    Look for a list file first. If the list file exists, send the
    entire thing back to the client.
    """
    # Get list file
    if not os.path.exists(dlc_path):
        return "\r\n"
    elif os.path.isfile(os.path.join(dlc_path, "_list.txt")):
        list_data = safeloadfi(dlc_path, "_list.txt") or "\r\n"
    else:
        # Doesn't have _list.txt file
        try:
            ls = [
                download_size(dlc_path, name)
                for name in sorted(os.listdir(dlc_path))
            ]
            list_data = "\r\n".join("\t\t\t\t\t".join(f) for f in ls) + "\r\n"
        except:
            return "\r\n"

    attr1 = post.get("attr1", None)
    attr2 = post.get("attr2", None)
    attr3 = post.get("attr3", None)

    if post["gamecd"].startswith("IRA") and attr1.startswith("MYSTERY"):
        # Pokemon BW Mystery Gifts, until we have a better solution for that
        ret = filter_list(list_data, attr1, attr2, attr3)
        ret = filter_list_g5_mystery_gift(ret, post["rhgamecd"])
        return filter_list_by_date(ret, post["token"])
    elif post["gamecd"] in gen_4_pokemon_gamecodes:
      ret = filter_list(list_data, attr1, attr2, attr3)
      return filter_list_g4_mystery_gift(ret, post["token"], post["gamecd"], dlc_path)
    else:
        # Default case for most games
        num = post.get("num", None)
        if num is not None:
            num = int(num)

        offset = post.get("offset", None)
        if offset is not None:
            offset = int(offset)

        return filter_list(list_data, attr1, attr2, attr3, num, offset)


def download_contents(dlc_path, post):
    """Handle download contents request.

    Get only the base filename just in case there is a path involved
    somewhere in the filename string.
    """
    contents = os.path.basename(post["contents"])
    return safeloadfi(dlc_path, contents)
