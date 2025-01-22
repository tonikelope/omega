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
                                 
MEGACRYPTER REVERSE MODE

Basado en el código de gschizas y modificado por tonikelope para OMEGA

"""

import socket
import select
import re
import hashlib
import base64
from threading import Thread
from threading import Lock
from platformcode import config, logger


BUFFER_SIZE = 4096
MAX_LISTEN = 10
CONNECT_PATTERN = "CONNECT (.*mega(?:\.co)?\.nz):(443) HTTP/(1\.[01])"
AUTH_PATTERN = "Proxy-Authorization: Basic +(.+)"


class Forward:
    def __init__(self):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            print(e)
            return False


class MegaProxyServer(Thread):
    stop = False
    input_list = []
    channel = {}

    def synchronized(func):

        func.__lock__ = Lock()

        def synced_func(*args, **kws):
            with func.__lock__:
                return func(*args, **kws)

        return synced_func

    def __init__(self, host, port, password):
        Thread.__init__(self)
        self.password = password
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(MAX_LISTEN)

    @synchronized
    def stop_server(self):
        print("Stopping server...")
        self.stop = True

    @synchronized
    def __is_stop_server(self):
        return self.stop

    def run(self):
        self.input_list.append(self.server)

        while not self.__is_stop_server():
            ss = select.select
            inputready, outputready, exceptready = ss(self.input_list, [], [], 1.0)
            for self.s in inputready:
                if self.s == self.server:
                    self.on_accept()
                    break

                self.data = self.s.recv(BUFFER_SIZE)
                if len(self.data) == 0:
                    self.on_close()
                    break
                else:
                    self.on_recv()

        print("Bye bye")

    def on_accept(self):

        clientsock, clientaddress = self.server.accept()

        print(clientaddress, "has connected")

        self.input_list.append(clientsock)

    def on_close(self):
        print(self.s.getpeername(), "has disconnected")
        # remove objects from input_list
        self.input_list.remove(self.s)
        self.input_list.remove(self.channel[self.s])
        out = self.channel[self.s]
        # close the connection with client
        self.channel[out].close()  # equivalent to do self.s.close()
        # close the connection with remote server
        self.channel[self.s].close()
        # delete both objects from channel dict
        del self.channel[out]
        del self.channel[self.s]

    def on_recv(self):

        data = self.data

        if data.find("CONNECT") != -1:

            m = re.search(AUTH_PATTERN, data)

            proxy_pass = base64.b64decode(m.group(1)).split(':')

            logger.info("channels.omega PROXY " + proxy_pass[1] + " " + self.password)

            if proxy_pass[1] == self.password:

                m = re.search(CONNECT_PATTERN, data)

                forward = Forward().start(m.group(1), int(m.group(2)))

                print((m.group(1)))

                if forward:
                    self.input_list.append(forward)
                    self.channel[self.s] = forward
                    self.channel[forward] = self.s
                    self.s.send("HTTP/1.1 200 Connection established\r\nProxy-agent: Omega/0.1\r\n\r\n")
                else:
                    print("Can't establish connection with remote server.", end=' ')
                    print("Closing connection with client side")
                    self.s.close()
            else:
                print("Can't establish connection with remote server.", end=' ')
                print("Closing connection with client side")
                self.s.close()
        else:
            self.channel[self.s].send(data)
