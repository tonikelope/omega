# -*- coding: utf-8 -*-
#Basado en la librería de MEGA que programó divadr y modificado por tonikelope para dar soporte MULTI-THREAD + MEGACRYPTER

import urllib.request, urllib.error, urllib.parse
import threading
from . import MegaProxyManager
from .cursor import Cursor

SOCKET_TIMEOUT=15

class File(object):
    def __init__(self, info, file_id, key, file, client, folder_id=None):
        self._client = client
        self.folder_id = folder_id
        self.file_id = file_id
        self.cursor = False
        self.cursors = []
        self.key = key
        self.file = file
        self.info = info
        self.name = info["n"]
        self.size = file["s"]
        self.request = None
        self.k = self.key[0] ^ self.key[4], self.key[1] ^ self.key[5], self.key[2] ^ self.key[6], self.key[3] ^ \
            self.key[7]
        self.iv = self.key[4:6] + (0, 0)
        self.initial_value = (((self.iv[0] << 32) + self.iv[1]) << 64)
        if not self.folder_id:
            self.url = self.file["g"]
        else:
            self.url = None
        self.url_lock = threading.Lock()
        self.proxy_manager = MegaProxyManager.MegaProxyManager()


    def create_cursor(self, offset):
        c = Cursor(self)
        c.seek(offset)
        self.cursor = True
        self.cursors.append(c)
        return c


    def checkMegaDownloadUrl(self, url):

        print(("Checking MEGA DL URL %s" % url))

        error509 = False

        proxy = None

        error = False

        while not error:

            if error509:
                if proxy:
                    self.proxy_manager.block_proxy(proxy)

                proxy = self.proxy_manager.get_fastest_proxy()

            error509 = False


            try:

                req = urllib.request.Request(url+'/0-0')

                if proxy:
                    req.set_proxy(proxy, 'http')

                connection = urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT)

                connection.read()

                print("MEGA DL URL IS OK!")
                return True

            except urllib.error.HTTPError as err:
                print(("CHECKING MEGA DL URL ERROR %d" % err.code))

                if err.code == 509:
                    error509 = True
                else:
                    error = True
            except urllib2.socket.timeout:
            	if not proxy:
            		error = True


    def refreshMegaDownloadUrl(self):

        with self.url_lock():

            url = self.url
        
            while not url or not self.checkMegaDownloadUrl(url):
                url=self.get_new_url_from_api()

            self.url = url

            return url

    def get_new_url_from_api(self):
        if self.folder_id:
            file = self._client.api_req({"a": "g", "g": 1, "n": self.file_id}, "&n=" + self.folder_id)
            return file["g"]
        elif self.file_id != -1:
            file = self._client.api_req({'a': 'g', 'g': 1, 'p': self.file_id})
            return file["g"]
        else:
            mc_req_data = {'m': 'dl', 'link': self.info['mc_link']}

            if 'noexpire' in self.info:
                mc_req_data['noexpire'] = self.info['noexpire']

            if 'reverse' in self.info:
                mc_req_data['reverse'] = self.info['reverse']

            if 'sid' in self.info:
                mc_req_data['sid'] = self.info['sid']

            mc_dl_res=self._client.mc_api_req(self.info['mc_api_url'], mc_req_data)

            return mc_dl_res['url']

