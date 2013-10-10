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

import urllib, urllib2, StringIO, zlib, gzip, socket
import traceback, generic, sickbeard
from httplib import BadStatusLine

from sickbeard import logger, tvcache, exceptions
from sickbeard.common import USER_AGENT
from sickbeard.exceptions import ex

try:
    import json
except ImportError:
    from lib import simplejson as json


class HDBitsProvider(generic.TorrentProvider):

    def __init__(self):

        generic.TorrentProvider.__init__(self, "HDBits")

        self.supportsBacklog = True

        self.cache = HDBitsCache(self)

        self.url = 'https://hdbits.org'
        self.search_url = 'https://hdbits.org/api/torrents'
        self.rss_url = self.search_url
        self.dl_url = 'http://hdbits.org/download.php?'

    def isEnabled(self):
        return sickbeard.HDBITS

    def imageName(self):
        return 'hdbits.png'

    def _get_episode_search_strings(self, episode):
        return [ self._make_JSON(show=episode.show, episode=episode) ]


    def _get_season_search_strings(self, show, season):
        return  [ self._make_JSON(show=show, season=season) ]


    def _doSearch(self, search_params, show=None):
        response = json.loads(self.getJSON(url=self.search_url, json=search_params))['data']
        return response

    def _get_title_and_url(self, item):
        return (item['name'], self._make_download_url(item))

    def _make_download_url(self, item):
        return self.dl_url + urllib.urlencode({'id': item['id'], 'passkey': sickbeard.HDBITS_PASSKEY})

    def _make_JSON(self, show=None, episode=None, season=None):
        body = {
            'username': sickbeard.HDBITS_USERNAME,
            'passkey': sickbeard.HDBITS_PASSKEY,
            'category': [2],  # TV Category
 #           'medium': [3]  # x264
        }

        if episode:
            body['tvdb'] = {
                'id': show.tvdbid,
                'season': episode.season,
                'episode': episode.episode
            }

        if season:
            body['tvdb'] = {
                'id': show.tvdbid,
                'season': season,
            }
        return json.dumps(body)


    #def getQuality(self, item):

    def getJSON(self, url=None, json=None):
        """
        Returns a byte-string retrieved from the url provider.
        Needed here to support json POST.
        """

        opener = urllib2.build_opener()
        opener.addheaders = [('User-Agent', USER_AGENT), ('Accept-Encoding', 'gzip,deflate')]

        try:
            usock = opener.open(url, json)
            url = usock.geturl()
            encoding = usock.info().get("Content-Encoding")

            if encoding in ('gzip', 'x-gzip', 'deflate'):
                content = usock.read()
                if encoding == 'deflate':
                    data = StringIO.StringIO(zlib.decompress(content))
                else:
                    data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(content))
                result = data.read()
            else:
                result = usock.read()
            usock.close()

        except urllib2.HTTPError, e:
            logger.log(u"HTTP error " + str(e.code) + " while loading URL " + url, logger.WARNING)
            return None
        except urllib2.URLError, e:
            logger.log(u"URL error " + str(e.reason) + " while loading URL " + url, logger.WARNING)
            return None
        except BadStatusLine:
            logger.log(u"BadStatusLine error while loading URL " + url, logger.WARNING)
            return None
        except socket.timeout:
            logger.log(u"Timed out while loading URL " + url, logger.WARNING)
            return None
        except ValueError:
            logger.log(u"Unknown error while loading URL " + url, logger.WARNING)
            return None
        except Exception:
            logger.log(u"Unknown exception while loading URL " + url + ": " + traceback.format_exc(), logger.WARNING)
            return None

        return result

class HDBitsCache(tvcache.TVCache):

    def __init__(self, provider):

        tvcache.TVCache.__init__(self, provider)

        # only poll HDBits every 15 minutes max
        self.minTime = 15

    def updateCache(self):

        if not self.shouldUpdate():
            return

        data = self._getRSSData()

        # as long as the http request worked we count this as an update
        if data:
            self.setLastUpdate()
        else:
            return []

        # now that we've loaded the current RSS feed lets delete the old cache
        logger.log(u"Clearing " + self.provider.name + " cache and updating with new information")
        self._clearCache()

        if not self._checkAuth(data):
            raise exceptions.AuthException("Your authentication info for " + self.provider.name + " is incorrect, check your config")

        try:
            parsedJSON = json.loads(data)
            items = parsedJSON['data']
        except Exception, e:
            logger.log(u"Error trying to load " + self.provider.name + " RSS feed: " + ex(e), logger.ERROR)
            logger.log(u"Feed contents: " + repr(data), logger.DEBUG)
            return []

        for item in items:

            self._parseItem(item)

    def _parseItem(self, item):

        title = item['name']
        url = self.provider._make_download_url(item)

        if not title or not url:
            logger.log(u"The JSON returned from the " + self.provider.name + " feed is incomplete, this result is unusable", logger.ERROR)
            return

        logger.log(u"Adding item from RSS to cache: " + title, logger.DEBUG)

        self._addCacheEntry(title, url)

    def _getRSSData(self):
        return self.provider.getJSON(url=self.provider.search_url, json=self.provider._make_JSON())

provider = HDBitsProvider()
