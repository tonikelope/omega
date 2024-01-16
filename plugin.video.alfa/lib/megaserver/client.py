# -*- coding: utf-8 -*-

"""
  ___  __  __ _____ ____    _    
 / _ \|  \/  | ____/ ___|  / \   
| | | | |\/| |  _|| |  _  / _ \  
| |_| | |  | | |__| |_| |/ ___ \ 
 \___/|_|  |_|_____\____/_/   \_\

 _              _ _        _                  
| |_ ___  _ __ (_) | _____| | ___  _ __   ___ 
| __/ _ \| '_ \| | |/ / _ \ |/ _ \| '_ \ / _ \
| || (_) | | | | |   <  __/ | (_) | |_) |  __/
 \__\___/|_| |_|_|_|\_\___|_|\___/| .__/ \___|
                                  |_|         
                                 
Basado en la librería de MEGA que programó divadr y modificado por tonikelope para dar soporte MULTI-THREAD + MEGACRYPTER

"""

import base64
import hashlib
import json
import random
import struct
import xbmcgui
import xbmcaddon
import time
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import socket
import os
from .crypto import *
from threading import Thread
from .file import File
from .handler import Handler
from .server import Server
from .proxy import MegaProxyServer
from platformcode import logger, config


class Client(object):
    VIDEO_EXTS = {'.avi': 'video/x-msvideo', '.mp4': 'video/mp4', '.mkv': 'video/x-matroska',
                  '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.mpg': 'video/mpeg', '.ogv': 'video/ogg',
                  '.ogg': 'video/ogg', '.webm': 'video/webm', '.ts': 'video/mp2t', '.3gp': 'video/3gpp'}

    def __init__(self, url, port=None, ip=None, auto_shutdown=True, wait_time=90, timeout=90, is_playing_fnc=None):

        self.port = port if port else random.randint(8000, 8099)
        self.ip = ip if ip else "127.0.0.1"
        self.connected = False
        self.start_time = None
        self.last_connect = None
        self.is_playing_fnc = is_playing_fnc
        self.auto_shutdown = auto_shutdown
        self.wait_time = wait_time
        self.timeout = timeout
        self.running = False
        self.file = None
        self.files = []
        self.error_509_notified = False

        self._server = Server((self.ip, self.port), Handler, client=self)
        self.__add_url(url)
        self.start()

    def start(self):
        self.start_time = time.time()
        self.running = True
        self._server.run()
        t = Thread(target=self._auto_shutdown)
        t.setDaemon(True)
        t.start()
        logger.info("MEGA Server Started")

    def error_509_notify(self):
        
        if not self.error_509_notified:
            self.error_509_notified = True
            xbmcgui.Dialog().notification('OMEGA', "AVISO: LÍMITE DE MEGA ALCANZADO (probando proxys...)",os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

    def load_mega_proxy(self, host, port, password):
        try:
            mega_proxy = MegaProxyServer(host, port, password)
            mega_proxy.daemon = True
            mega_proxy.start()
        except socket.error:
            pass

    def _auto_shutdown(self):
        while self.running:
            time.sleep(1)

            if (self.file and self.file.cursor) or (self.is_playing_fnc and self.is_playing_fnc()):
                self.last_connect = time.time()

            if self.auto_shutdown and ((self.connected and self.last_connect and self.is_playing_fnc and not self.is_playing_fnc() and time.time() - self.last_connect - 1 > self.timeout) or ((not self.file or not self.file.cursor) and self.start_time and self.wait_time and not self.connected and time.time() - self.start_time - 1 > self.wait_time) or ((not self.file or not self.file.cursor) and self.timeout and self.connected and self.last_connect and not self.is_playing_fnc and time.time() - self.last_connect - 1 > self.timeout)):
                self.stop()

    def stop(self):
        self.running = False
        self._server.stop()
        logger.info("MEGA Server Stopped")

    def get_play_list(self):
        if len(self.files) > 1:
            return "http://" + self.ip + ":" + str(self.port) + "/playlist.pls"
        else:
            return "http://" + self.ip + ":" + str(self.port) + "/" + urllib.parse.quote(self.files[0].name.encode("utf8"))

    def get_files(self):
        if self.files:
            files = []
            for file in self.files:
                n = file.name.encode("utf8")
                u = "http://" + self.ip + ":" + str(self.port) + "/" + urllib.parse.quote(n)
                s = file.size
                files.append({"name": n, "url": u, "size": s})
        return files

    def __add_url(self, url):

        logger.info(url)

        if '/!' in url:
            url_split = url.split('#')
            url = url_split[0]
            name = url_split[1]
            size = int(url_split[2])
            key = base64_to_a32(url_split[3])

            if len(url_split) > 4:
                noexpire = url_split[4]
            else:
                noexpire = None

            if len(url_split) > 5:
                reverse = url_split[5]
            else:
                reverse = None

            if len(url_split) > 6:
                mega_sid = url_split[6]
            else:
                mega_sid = None

            url_split = url.split('/!')
            mc_api_url = url_split[0] + '/api'
            url = '!' + url_split[1]

            attributes = {'n': name, 'mc_api_url': mc_api_url, 'mc_link': url}

            mc_req_data = {'m': 'dl', 'link': url}

            if noexpire:
                attributes['noexpire'] = noexpire
                mc_req_data['noexpire'] = noexpire

            if reverse:
                attributes['reverse'] = reverse
                mc_req_data['reverse'] = reverse
                mega_proxy_port = int(reverse.split(":")[0])
                mega_proxy_pass = base64.b64decode(reverse.split(":")[1]).split(":")[1]
                self.load_mega_proxy('',mega_proxy_port,mega_proxy_pass)

            if mega_sid:
                attributes['sid'] = mega_sid
                mc_req_data['sid'] = mega_sid

            mc_dl_res = self.mc_api_req(mc_api_url, mc_req_data)

            file = {'g': mc_dl_res['url'], 's': size}
            self.files.append(File(info=attributes, file_id=-1, key=key, file=file, client=self))
        else:
            url = url.split("/#")[1]
            if url.startswith("F!"):
                if len(url.split("!")) == 3:
                    folder_id = url.split("!")[1]
                    folder_key = url.split("!")[2]
                    master_key = base64_to_a32(folder_key)
                    files = self.mega_api_req({"a": "f", "c": 1}, "&n=" + folder_id)
                    for file in files["f"]:
                        if file["t"] == 0:
                            key = file['k'][file['k'].index(':') + 1:]
                            key = decrypt_key(base64_to_a32(key), master_key)
                            k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
                            attributes = base64_url_decode(file['a'])
                            attributes = decrypt_attr(attributes, k)
                            self.files.append(
                                File(info=attributes, file_id=file["h"], key=key, folder_id=folder_id, file=file,
                                     client=self))
                else:
                    raise Exception("Enlace no válido")

            elif url.startswith("!") or url.startswith("N!"):
                if len(url.split("!")) == 3:
                    file_id = url.split("!")[1]
                    file_key = url.split("!")[2]
                    file = self.mega_api_req({'a': 'g', 'g': 1, 'p': file_id})
                    key = base64_to_a32(file_key)
                    k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
                    attributes = base64_url_decode(file['at'])
                    attributes = decrypt_attr(attributes, k)
                    self.files.append(File(info=attributes, file_id=file_id, key=key, file=file, client=self))
                else:
                    raise Exception("Enlace no válido")
            else:
                raise Exception("Enlace no válido")

    def mega_api_req(self, req, get=""):
        seqno = random.randint(0, 0xFFFFFFFF)
        url = 'https://g.api.mega.co.nz/cs?id=%d%s' % (seqno, get)
        return json.loads(self.__post(url, json.dumps([req])))[0]

    def mc_api_req(self, api_url, req):
        res = self.__post(api_url, json.dumps(req))
        return json.loads(res)

    def __post(self, url, data):
        import ssl
        from functools import wraps

        def sslwrap(func):
            @wraps(func)
            def bar(*args, **kw):
                kw['ssl_version'] = ssl.PROTOCOL_TLSv1
                return func(*args, **kw)

            return bar

        ssl.wrap_socket = sslwrap(ssl.wrap_socket)

        request = urllib.request.Request(url, data=data.encode("utf-8"), headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko)"
                          " Chrome/30.0.1599.101 Safari/537.36"})

        contents = urllib.request.urlopen(request).read()

        return contents
