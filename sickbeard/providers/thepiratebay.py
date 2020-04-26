###################################################################################################
# Author: Jodi Jones <venom@gen-x.co.nz>
# Added in manual proxy override.
# Based on work by: Mr_Orange <mr_orange@hotmail.it>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.
###################################################################################################

import re
import json
import urllib, urllib2
import sys
import datetime
import os

import sickbeard
import generic
from sickbeard.common import Quality
from sickbeard import logger
from sickbeard import tvcache
from sickbeard import helpers
from sickbeard import show_name_helpers
from sickbeard import db
from sickbeard.common import Overview
from sickbeard.exceptions import ex
from sickbeard import encodingKludge as ek

proxy_dict = {'proxyfofree.com (US)' : 'http://proxyfofree.com/',
              'meganprx.info (FR)': 'http://www.meganprx.info/',
              'alexandraprx.info (FR)' : 'http://www.alexandraprx.info/',
              'imspecial.me (DE)' : 'http://imspecial.me/',
              'proxite.eu (DE)' :'http://proxite.eu/',
              'shieldmagic.com (GB)' : 'http://www.shieldmagic.com/',
              'wowspeed.co.uk (GB)' : 'http://wowspeed.co.uk/' ,
              'webproxy.cz (CZ)' : 'http://webproxy.cz/',
              'freeproxy.cz (CZ)' : 'http://www.freeproxy.cz/',
             }

class ThePirateBayProvider(generic.TorrentProvider):
    ###################################################################################################
    def __init__(self):
        generic.TorrentProvider.__init__(self, "ThePirateBay")
        self.supportsBacklog = True
        self.cache = ThePirateBayCache(self)
        self.proxy = ThePirateBayWebproxy() 
        self.url = 'http://thepiratebay.org/'
        self.apiURL = None
        self.jsURL = None
        self.trackers = None
        self.trusted = [
            "trusted",
            "vip",
            "helpers",
        ]

    ###################################################################################################
    def isEnabled(self):
        return sickbeard.THEPIRATEBAY
    
    ###################################################################################################
    def imageName(self):
        return 'thepiratebay.png'
    
    ###################################################################################################
    def getQuality(self, item):
        
        quality = Quality.nameQuality(item[0])
        return quality    
    
    ###################################################################################################
    def _get_airbydate_season_range(self, season):
            if season == None:
                return ()
        
            year, month = map(int, season.split('-'))
            min_date = datetime.date(year, month, 1)
            if month == 12:
                max_date = datetime.date(year, month, 31)
            else:    
                max_date = datetime.date(year, month+1, 1) -  datetime.timedelta(days=1)

            return (min_date, max_date)    
      
    ###################################################################################################
    def _get_season_search_strings(self, show, season=None):
        search_string = []
    
        if not show:
            return []

        #Building the search string with the season we need
        #1) ShowName SXX 
        #2) ShowName Season X
        for show_name in set(show_name_helpers.allPossibleShowNames(show)):
            ep_string = show_name + ' ' + 'S%02d' % int(season)   
            search_string.append(ep_string)
          
            ep_string = show_name + ' ' + 'Season' + ' ' + str(season)   
            search_string.append(ep_string)

        #Building the search string with the episodes we need         
        myDB = db.DBConnection()
        
        if show.air_by_date:
            (min_date, max_date) = self._get_airbydate_season_range(season)
            sqlResults = myDB.select("SELECT * FROM tv_episodes WHERE showid = ? AND airdate >= ? AND airdate <= ?", [show.tvdbid,  min_date.toordinal(), max_date.toordinal()])
        else:
            sqlResults = myDB.select("SELECT * FROM tv_episodes WHERE showid = ? AND season = ?", [show.tvdbid, season])
            
        for sqlEp in sqlResults:
            if show.getOverview(int(sqlEp["status"])) in (Overview.WANTED, Overview.QUAL):
                
                if show.air_by_date:
                    for show_name in set(show_name_helpers.allPossibleShowNames(show)):
                        ep_string = show_name_helpers.sanitizeSceneName(show_name) +' '+ str(datetime.date.fromordinal(sqlEp["airdate"])).replace('-', '.')
                        search_string.append(ep_string)
                else:
                    for show_name in set(show_name_helpers.allPossibleShowNames(show)):
                        ep_string = show_name_helpers.sanitizeSceneName(show_name) +' '+ sickbeard.config.naming_ep_type[2] % {'seasonnumber': season, 'episodenumber': int(sqlEp["episode"])}
                        search_string.append(ep_string)                       
        
        return search_string

    ###################################################################################################
    def _get_episode_search_strings(self, ep_obj):
       
        search_string = []
       
        if not ep_obj:
            return []
                
        if ep_obj.show.air_by_date:
            for show_name in set(show_name_helpers.allPossibleShowNames(ep_obj.show)):
                ep_string = show_name_helpers.sanitizeSceneName(show_name) +' '+ str(ep_obj.airdate).replace('-', '.')
                search_string.append(ep_string)
        else:
            for show_name in set(show_name_helpers.allPossibleShowNames(ep_obj.show)):
                ep_string = show_name_helpers.sanitizeSceneName(show_name) +' '+ sickbeard.config.naming_ep_type[2] % {'seasonnumber': ep_obj.season, 'episodenumber': ep_obj.episode}
                search_string.append(ep_string)
    
        return search_string

    ###################################################################################################
    def _doSearch(self, search_params, show=None):
        results = []

        if not self.apiURL:
            self.getAPI()
        
        searchURL = self.apiURL + "/q.php?q=" + urllib.quote(search_params)
        logger.log(u"Search string: " + searchURL, logger.DEBUG)
                    
        data = self.getURL(searchURL)
        if not ":" in data:
            return []

        torrents = json.loads(data)
        if torrents[0]["name"] == "No results returned":
            return []
        
        for torrent in torrents:
            if torrent["seeders"] == "0":
                continue

            if sickbeard.THEPIRATEBAY_TRUSTED and not torrent["status"] in self.trusted:
                logger.log(u"ThePirateBay Provider found result "+torrent.group('title')+" but that doesn't seem like a trusted result so I'm ignoring it",logger.DEBUG)
                continue

            magnet_link = self.createMagnet(torrent["info_hash"],torrent["name"],self.trackers)

            #Do not know why but Sick Beard skip release with a '_' in name
            item = (torrent["name"].replace('_','.'),magnet_link)

            results.append(item)
        return results

    ###################################################################################################
    def _get_title_and_url(self, item):
        (title, url) = item
        if url:
            url = url.replace('&amp;','&')
        return (title, url)

    ###################################################################################################
    def getURL(self, url, headers=None):
        if not headers:
            headers = []

        # Glype Proxies does not support Direct Linking.
        # We have to fake a search on the proxy site to get data
        if self.proxy.isEnabled():
            headers.append(('Referer', self.proxy.getProxyURL()))
            
        result = None

        try:
            result = helpers.getURL(url, headers=headers)
        except (urllib2.HTTPError, IOError), e:
            logger.log(u"Error loading "+self.name+" URL: " + str(sys.exc_info()) + " - " + ex(e), logger.ERROR)
            return None

        return result

    ###################################################################################################
    def downloadResult(self, result):
        """
        Save the result to disk.
        """
        
        #Hack for rtorrent user (it will not work for other torrent client)
        if sickbeard.TORRENT_METHOD == "blackhole" and result.url.startswith('magnet'): 
            magnetFileName = ek.ek(os.path.join, sickbeard.TORRENT_DIR, helpers.sanitizeFileName(result.name) + '.' + self.providerType)
            magnetFileContent = 'd10:magnet-uri' + `len(result.url)` + ':' + result.url + 'e'

            try:
                fileOut = open(magnetFileName, 'wb')
                fileOut.write(magnetFileContent)
                fileOut.close()
                helpers.chmodAsParent(magnetFileName)
            except IOError, e:
                logger.log("Unable to save the file: "+ex(e), logger.ERROR)
                return False
            logger.log(u"Saved magnet link to "+magnetFileName+" ", logger.MESSAGE)
            return True

    ###################################################################################################
    def getAPI(self):
        """
        scrapes the tpb javascript files for api server and trackers
        """
        scrape_tpb = self.getURL(self.url)
        self.jsURL = re.findall('<script.*?src="(?P<url>.*\.js)".*?>',scrape_tpb)[0]
        scrape_js = self.getURL(self.jsURL)
        self.apiURL = re.findall("var server='(?P<server>.*?)'", scrape_js)[0]

        # scrape trackers from api
        trackers = re.findall("&tr='.*?'(?P<tracker>.*?)\'\)", scrape_js)
        self.trackers = "&tr=".join(trackers)

    ###################################################################################################
    def createMagnet(self,info_hash,dn,trackers):
        magnet_link = "magnet:?xt=urn:btih:" + info_hash + "&dn=" + dn + "&tr=" + trackers
        return magnet_link

class ThePirateBayCache(tvcache.TVCache):
    ###################################################################################################
    def __init__(self, provider):
        tvcache.TVCache.__init__(self, provider)
        # only poll ThePirateBay every 10 minutes max
        self.minTime = 10

    ###################################################################################################
    def updateCache(self):
        if not self.shouldUpdate():
            return
        data = self._getData()
        # as long as the http request worked we count this as an update
        if ":" in data:
            self.setLastUpdate()
        else:
            return []
        # now that we've loaded the current RSS feed lets delete the old cache
        logger.log(u"Clearing "+self.provider.name+" cache and updating with new information")
        self._clearCache()

        torrents = json.loads(data)
        if torrents[0]["name"] == "No results returned":
            return []

        for torrent in torrents:
            if torrent["seeders"] == "0":
                continue

            if sickbeard.THEPIRATEBAY_TRUSTED and not torrent["status"] in self.provider.trusted:
                continue

            magnet_link = self.provider.createMagnet(torrent["info_hash"],torrent["name"],self.provider.trackers)

            item = (torrent["name"].replace('_','.'),magnet_link)
            self._parseItem(item)

    ###################################################################################################
    def _getData(self):
        if not self.provider.apiURL:
            self.provider.getAPI()

        # this builds the URL for the top 100 of a certain category
        # however, filtering by category doesnt work, even on the
        # offical site as of 4/26/2020. This url should be rechecked
        # in the future
        url = self.provider.apiURL + '/precompiled/data_top100_recent.json?cat=205' #url for the last 100 tv-show
        logger.log(u"ThePirateBay cache update URL: "+ url, logger.DEBUG)

        data = self.provider.getURL(url)
        return data

    ###################################################################################################
    def _parseItem(self, item):
        (title, url) = item
        if not title or not url:
            return
        logger.log(u"Adding item to cache: "+title, logger.DEBUG)
        self._addCacheEntry(title, url)

class ThePirateBayWebproxy:
    ###################################################################################################
    def __init__(self):
        self.Type   = 'GlypeProxy'
        self.param  = 'browse.php?u='
        self.option = '&b=32'
        
    ###################################################################################################
    def isEnabled(self):
        """ Return True if we Choose to call TPB via Proxy """ 
        return sickbeard.THEPIRATEBAY_PROXY
    
    ###################################################################################################
    def getProxyURL(self):
        """ Return the Proxy URL Choosen via Provider Setting """
        return str(sickbeard.THEPIRATEBAY_PROXY_URL)
    
    ###################################################################################################
    def _buildURL(self,url):
        """ Return the Proxyfied URL of the page """ 
        url = url.replace(provider.url,sickbeard.THEPIRATEBAY_URL_OVERRIDE) if sickbeard.THEPIRATEBAY_URL_OVERRIDE else url
        if self.isEnabled():
            url = self.getProxyURL() + self.param + url + self.option   
        return url

    ###################################################################################################
    def _buildRE(self,re):
        """ Return the Proxyfied RE string """
        if self.isEnabled():
            re = re %('&amp;b=32','&amp;b=32')
        else:
            re = re %('','')   
        return re

provider = ThePirateBayProvider()
