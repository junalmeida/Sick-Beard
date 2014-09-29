# Author: Alexandre Espinosa Menor <aemenor@gmail.com>
# URL: https://github.com/alexandregz/Sick-Beard
# URL: https://github.com/junalmeida/Sick-Beard
# 
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

import requests

try:
    import json
except ImportError:
    from lib import simplejson as json


import sickbeard

from sickbeard import logger
from sickbeard.common import notifyStrings, NOTIFY_SNATCH, NOTIFY_DOWNLOAD
from sickbeard.exceptions import ex

API_URL = "https://api.pushbullet.com/v2/pushes"



class PushbulletNotifier:
    """
    Sick-beard notifier for pushbullet
    """

    def test_notify(self, apiKey=None):
        return self._sendPushbullet("This is a test notification from SickBeard", 'Test', None )

    def _sendPushbullet(self, msg, title, device=None):
        """
        Sends a pushbullet notification with API key and to indicate device (ToDo)

        msg: The message to send 
        title: The title of the message
        device: Device ID to send notification (ToDo)


        returns: True if the message succeeded, False otherwise
        """

        apiKey = sickbeard.PUSHBULLET_APIKEY

        # build up the URL and parameters
        msg = msg.strip()

        s = requests.Session()
        s.auth = (apiKey, '')
        s.headers.update({'Content-Type': 'application/json'})
        
        payload = {'type':'note', 'title': title, 'body': msg}
        if device:
            payload['device_iden'] = device

        r = s.post(API_URL, data=json.dumps(payload))
        if r.status_code != 200:
                logger.log("Wrong data sent to pushbullet", logger.ERROR)
                return False

        response = r.json()
        if response['active'] == True and response['dismissed'] == False:
            logger.log("Pushbullet notification successful.", logger.DEBUG)
            return True


    def notify_snatch(self, ep_name, title=notifyStrings[NOTIFY_SNATCH]):
        if sickbeard.PUSHBULLET_NOTIFY_ONSNATCH:
            self._notifyPushbullet(title, ep_name)


    def notify_download(self, ep_name, title=notifyStrings[NOTIFY_DOWNLOAD]):
        if sickbeard.PUSHBULLET_NOTIFY_ONDOWNLOAD:
            self._notifyPushbullet(title, ep_name)

    def _notifyPushbullet(self, title, message, device=None):
        """
        Sends a pushbullet notification 

        title: The title of the notification to send
        message: The message string to send
        device: Device to send. None to send all devices
        """

        if not sickbeard.USE_PUSHBULLET:
            logger.log("Notification for Pushbullet not enabled, skipping this notification", logger.DEBUG)
            return False

        apiKey = sickbeard.PUSHBULLET_APIKEY

        logger.log("Sending notification for " + message, logger.DEBUG)

        self._sendPushbullet(message, title)
        return True

notifier = PushbulletNotifier
