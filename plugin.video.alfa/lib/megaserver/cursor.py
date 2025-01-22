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
                                 
Basado en la librería de MEGA que programó divadr y modificado por tonikelope para dar soporte MULTI-THREAD + MEGACRYPTER

"""

import time
import os
import shutil
import urllib.request, urllib.error, urllib.parse
from platformcode import platformtools,logger,config
import threading
from . import Chunk
from . import ChunkDownloader
from . import MegaProxyManager
from . import ChunkWriter
from .crypto import *

try:
    from Cryptodome.Util import Counter
except:
    from Crypto.Util import Counter

CHUNK_WORKERS = int(config.get_setting("omega_megalib_workers", "omega"))+1
TURBO_CHUNK_WORKERS = 20
SOCKET_TIMEOUT = 15

class Cursor(object):
    def __init__(self, file):
        self._file = file
        self.pos = 0
        self.pipe_r=None
        self.pipe_w=None
        self.chunk_writer=None
        self.chunk_downloaders=None
        self.initial_value = file.initial_value
        self.k = file.k
        self.proxy_manager = MegaProxyManager.MegaProxyManager()
        self.turbo_mode = False
        self.response = None
        self.turbo_lock = threading.Lock()


    def turbo(self):
        if not self.turbo_mode and CHUNK_WORKERS>1:
            with self.turbo_lock:
                if not self.turbo_mode:
                    self.turbo_mode = True
                    logger.info("ACTIVANDO PROXY TURBO MODE!")
                    for c in range(CHUNK_WORKERS-1, TURBO_CHUNK_WORKERS):
                        chunk_downloader = ChunkDownloader.ChunkDownloader(c+1, self)
                        self.chunk_downloaders.append(chunk_downloader)
                        t = threading.Thread(target=chunk_downloader.run)
                        t.daemon = True
                        t.start()


    def mega_request(self, offset):
        if not self._file.url:
            self._file.url = self._file.refreshMegaDownloadUrl()

        try:
            self.__start_multi_download(offset)
            self.__prepare_decoder(offset)
        except Exception as e:
            logger.info(str(e))
            self.stop_multi_download()
            

    def __start_multi_download(self, offset):

        if CHUNK_WORKERS > 1:
            self.pipe_r,self.pipe_w=os.pipe()
            self.chunk_writer = ChunkWriter.ChunkWriter(self, self.pipe_w, offset, self._file.size - 1)

            t = threading.Thread(target=self.chunk_writer.run)
            t.daemon = True
            t.start()

            self.chunk_downloaders = []

            if len(self.chunk_downloaders) < CHUNK_WORKERS:
                for c in range(0,CHUNK_WORKERS):
                    chunk_downloader = ChunkDownloader.ChunkDownloader(c+1, self)
                    self.chunk_downloaders.append(chunk_downloader)
                    t = threading.Thread(target=chunk_downloader.run)
                    t.daemon = True
                    t.start()
        else:
            req = urllib.request.Request(self._file.url+('/%d-%d' % (offset, self._file.size - 1)))
            self.response = urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT)


    def stop_multi_download(self):

        logger.info("Cursor stopping multi download!")

        if self.response:
            self.response.close()
        else:

            if self.pipe_r:
                try:
                    os.close(self.pipe_r)
                except Exception as e:
                    logger.info(str(e))

            if self.pipe_w:
                try:
                    os.close(self.pipe_w)
                except Exception as e:
                    logger.info(str(e))
            
            try:
                if self.chunk_writer:
                    self.chunk_writer.exit = True

                    with self.chunk_writer.cv_new_element:
                        self.chunk_writer.cv_new_element.notify()

            except Exception as e:
                logger.info(str(e))

            if self.chunk_downloaders is not None:
                for c in self.chunk_downloaders:
                    try:
                        c.exit = True
                    except Exception as e:
                        logger.info(str(e))

            self.chunk_downloaders = None


    def read(self, n=None):
        if self.response:
            try:    
                res = self.response.read(n)
            except Exception:
                res = None
        else:
            if not self.pipe_r:
                return

            try:    
                res = os.read(self.pipe_r, n)
            except Exception:
                res = None

        if res:
            res = self.decode(res)
            self.pos += len(res)
        return res


    def seek(self, n):
        if n > self._file.size:
            n = self._file.size
        elif n < 0:
            raise ValueError('Seeking negative')
        self.mega_request(n)
        self.pos = n


    def tell(self):
        return self.pos


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_multi_download()

        self._file.cursors.remove(self)

        if len(self._file.cursors) == 0:
            self._file.cursor = False


    def decode(self, data):
        return self.decryptor.decrypt(data)


    def __prepare_decoder(self, offset):
        initial_value = self.initial_value + int(offset / 16)
        self.decryptor = AES.new(a32_to_str(self.k), AES.MODE_CTR, counter=Counter.new(128, initial_value=initial_value))
        rest = offset - int(offset / 16) * 16
        if rest:
            self.decode(b'\0' * rest)
