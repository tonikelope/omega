# -*- coding: utf-8 -*-

r"""
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
                                
Soporte de lista de proxys para esquivar límite de descarga diario de MEGA

"""

import urllib.request, urllib.error, urllib.parse
import collections
import time
import threading
import random
from platformcode import config,logger

PROXY_LIST_URL='https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt'
PROXY_BLOCK_TIME = 120

def synchronized_with_attr(lock_name):
    
    def decorator(method):
        
        def synced_method(self, *args, **kws):
            lock = getattr(self, lock_name)
            with lock:
                return method(self, *args, **kws)
                
        return synced_method

    return decorator

class MegaProxyManager():

    def __init__(self):
        self.proxy_list=collections.OrderedDict()
        self.proxy_list_url=PROXY_LIST_URL
        self.lock = threading.RLock()

        custom_proxy_list = config.get_setting("omega_mega_proxy_list", "omega")

        if custom_proxy_list:
            self.proxy_list_url=custom_proxy_list
        
        logger.info("USANDO LISTA DE PROXYS PARA MEGA: "+self.proxy_list_url)

    @synchronized_with_attr("lock")
    def error_509(self, client):
        client.error_509_notify()

    @synchronized_with_attr("lock")
    def __refresh_proxy_list(self):

        self.proxy_list.clear()
        
        try:
            logger.info(self.proxy_list_url)

            req = urllib.request.Request(self.proxy_list_url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"})

            proxy_data = urllib.request.urlopen(req).read().decode("utf-8")

            for p in proxy_data.split('\n'):
                self.proxy_list[p]=time.time()
                logger.info(p)

        except Exception as ex:
            logger.info(ex)
            logger.info("ERROR "+self.proxy_list_url)

    @synchronized_with_attr("lock")
    def get_next_proxy(self):

        if len(self.proxy_list) == 0:
            self.__refresh_proxy_list()
            return next(iter(self.proxy_list.items()))[0] if len(self.proxy_list) > 0 else None
        else:
            next_proxy = self.__get_next_rand_proxy()

            if next_proxy:
                return next_proxy

            self.__refresh_proxy_list()

            return self.__get_next_rand_proxy()

    @synchronized_with_attr("lock")
    def block_proxy(self,proxy):

        if proxy in self.proxy_list:
            self.proxy_list[proxy] = time.time() + PROXY_BLOCK_TIME

    
    @synchronized_with_attr("lock")
    def __get_next_rand_proxy(self):
        
        pos = random.randint(0, len(self.proxy_list)-1)

        i = 0

        for proxy, timestamp in self.proxy_list.items():
            if i < pos:
                i+=1
            elif time.time() > timestamp:
                return proxy

        return None