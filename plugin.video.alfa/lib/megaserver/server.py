# -*- coding: utf-8 -*-
#Basado en la librería de MEGA que programó divadr y modificado por tonikelope para dar soporte MULTI-THREAD + MEGACRYPTER

import urllib.request, urllib.error, urllib.parse
import traceback
import http.server
from socketserver import ThreadingMixIn
from threading import Thread


class Server(ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    timeout = 1

    def __init__(self, address, handler, client):
        http.server.HTTPServer.__init__(self, address, handler)
        self._client = client
        self.running = True
        self.request = None

    def stop(self):
        self.running = False
        
        try:
            urllib.request.urlopen('http://%s:%s/' % (self.server_name, self.server_port))
        except urllib.error.URLError:
            pass

        self.server_close()

    def serve(self):
        while self.running:
            try:
                self.handle_request()
            except Exception:
                print(traceback.format_exc())

    def run(self):
        t = Thread(target=self.serve, name='HTTP Server')
        t.daemon = self.daemon_threads
        t.start()

    def handle_error(self, request, client_address):
        if "socket.py" not in traceback.format_exc():
            print(traceback.format_exc())
