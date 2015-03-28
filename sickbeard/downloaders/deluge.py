# Author: Marcos Junior <junalmeida@gmail.com>
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

from urllib2 import Request, HTTPPasswordMgrWithDefaultRealm

try:
    import json
except ImportError:
    from lib import simplejson as json

import sickbeard
from sickbeard import logger
from sickbeard import helpers

RPC_URL = "json"

def _request(data):
    host = sickbeard.TORRENT_HOST
    if not host.endswith("/"):
        host += "/"
    host += RPC_URL
    password = sickbeard.TORRENT_PASSWORD
    
    # create a password manager with the required password for the deluge realm
    pw_mgr = HTTPPasswordMgrWithDefaultRealm()
    pw_mgr.add_password(realm='deluge', uri=host, user=None, passwd=password)
    # create the request with the provided data
    post_data = json.dumps(data)
    request = Request(host, data=post_data, headers={})
    
    # test the authentication before executing the request
    if (testAuthentication(host, None, password)):
        return helpers.getURL(request, password_mgr=pw_mgr)
    else:
        return None

    
def sendTORRENT(torrent):    
    result = None
    try:
        ratio = sickbeard.TORRENT_RATIO
        paused = sickbeard.TORRENT_PAUSED
        download_dir = sickbeard.TV_DOWNLOAD_DIR
        cookie = torrent.provider.token
        
        options = {}
        headers = {}
        if cookie:
            headers['Cookie'] = cookie
            
       
        post_data = {"method": "core.add_torrent_url",
                     "params": [torrent.url,
                                options,
                                headers],
                     
                     "id": 2
                    }
        
        result = _request(post_data)
        if result and not result["error"]:
            resultHash = result["result"]
            if paused:
                post_data = {"method": "core.pause_torrent",
                             "params": [[resultHash]],
                             "id": 5
                            }
                result = _request(post_data)
            if not (download_dir == ''):
                post_data = {"method": "core.set_torrent_move_completed",
                             "params": [resultHash, True],
                             "id": 3
                            }        
                result = _request(post_data)
                post_data = {"method": "core.set_torrent_move_completed_path",
                             "params": [resultHash, download_dir],
                             "id": 4
                            }
                result = _request(post_data)
            if ratio:
                post_data = {"method": "core.set_torrent_stop_at_ratio",
                             "params": [resultHash, True],
                             "id": 6
                            }        
                result = _request(post_data)
                post_data = {"method": "core.set_torrent_stop_ratio",
                             "params": [resultHash,float(ratio)],
                             "id": 7
                            }     
                result = _request(post_data)
            logger.log('Torrent added to deluge successfully.', logger.DEBUG)
            return True
        else:
            logger.log("Deluge error: " + str(result["error"]), logger.ERROR)
            return False
    except Exception, e:
        logger.log("Deluge error: " + str(e) + "\r\n" + str(result), logger.ERROR)
        return False
        
    
def testAuthentication(host, username, password):
    if not host.endswith("/"):
        host += "/"
    host += RPC_URL
    try:    
        # create headers required for authentication
        headers = {'X-Requested-With': 'XMLHttpRequest', 'Content-type': 'application/json', 'Accept-encoding': 'gzip'}
        # create a password manager with the required password for the deluge realm
        pw_mgr = HTTPPasswordMgrWithDefaultRealm()
        pw_mgr.add_password(realm='deluge', uri=host, user=None, passwd=password)
        # create the request with the provided data
        post_data = json.dumps({"method": "auth.login",
                                "params": [password],
                                "id": 1
                                })
        request = Request(host, post_data, headers)
        auth_data = helpers.getURL(request, password_mgr=pw_mgr, throw_exc=True)
        # read the json data retrieved from the URL
        jsonObject = json.loads(auth_data.read())
        if jsonObject["error"]:
            raise Exception("Deluge unknown Error." + str(jsonObject["error"]))
        elif jsonObject["result"] == False:
            raise Exception("Deluge unauthorized. Check your password.")
        else:
            return True, u"Connected and authenticated."
    except Exception, e:
        return False, u"Cannot connect to Deluge: " + str(e)