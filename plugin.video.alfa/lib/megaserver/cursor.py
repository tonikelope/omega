# -*- coding: utf-8 -*-
#Basado en la librería de MEGA que programó divadr y modificado por tonikelope para dar soporte MULTI-THREAD + MEGACRYPTER

import threading
from . import Chunk
from . import ChunkDownloader
from . import MegaProxyManager
from . import ChunkWriter
import time
import os
import urllib.request, urllib.error, urllib.parse
from platformcode import platformtools,logger
from .crypto import *
try:
    from Crypto.Util import Counter
except ImportError:
    from Cryptodome.Util import Counter

CHUNK_WORKERS = 6

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


    def mega_request(self, offset):
        if not self._file.url:
            self._file.url = self._file.refreshMegaDownloadUrl()

        try:
            self.start_multi_download(offset)
            self.prepare_decoder(offset)
        except Exception as e:
            logger.info(str(e))
            self.stop_multi_download()
            

    def start_multi_download(self, offset):

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


    def stop_multi_download(self):

        logger.info("Cursor stopping multi download!")

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


    def prepare_decoder(self, offset):
        initial_value = self.initial_value + int(offset / 16)
        self.decryptor = AES.new(a32_to_str(self.k), AES.MODE_CTR, counter=Counter.new(128, initial_value=initial_value))
        rest = offset - int(offset / 16) * 16
        if rest:
            self.decode(b'\0' * rest)
