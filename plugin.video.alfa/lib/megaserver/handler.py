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

import http.server
import urllib.parse
import time
import urllib.request, urllib.parse, urllib.error
import types
import os
import re


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        pass

    def __parse_range(self, range):
        if range:
            m = re.compile(r'bytes=(\d+)-(\d+)?').match(range)
            if m:
                return m.group(1), m.group(2)
        return None, None

    def do_GET(self):
        self.server._client.connected = True

        if self.do_HEAD():
            with self.server._client.file.create_cursor(self.offset) as f:
                sended = 0
                while sended < self.size:
                    buf = f.read(1024 * 16)
                    if buf:
                        if sended + len(buf) > self.size:
                            buf = buf[:self.size - sended]
                        self.wfile.write(buf)
                        sended += len(buf)
                    else:
                        break

    def __send_pls(self, files):
        playlist = "[playlist]\n\n"
        for x, f in enumerate(files):
            playlist += "File" + str(x + 1) + "=http://" + self.server._client.ip + ":" + str(
                self.server._client.port) + "/" + urllib.parse.quote(f.name) + "\n"
            playlist += "Title" + str(x + 1) + "=" + f.name + "\n"

        playlist += "NumberOfEntries=" + str(len(files))
        playlist += "Version=2"
        self.send_response(200, 'OK')
        self.send_header("Content-Length", str(len(playlist)))
        self.finish_header()
        self.wfile.write(playlist)

    def do_HEAD(self):
        url = urllib.parse.urlparse(self.path).path

        while not self.server._client.files:
            time.sleep(1)

        if url == "/playlist.pls":
            self.__send_pls(self.server._client.files)
            return False

        if not self.server._client.file or urllib.parse.unquote(url)[1:] != self.server._client.file.name:
            for f in self.server._client.files:
                if f.name == urllib.parse.unquote(url)[1:]:
                    self.server._client.file = f
                    break

        if self.server._client.file and urllib.parse.unquote(url)[1:] == self.server._client.file.name:
            range = False
            self.offset = 0
            size, mime = self.__file_info()
            start, end = self.__parse_range(self.headers.get('Range', ""))
            self.size = size

            if start is not None:
                if end is None:
                    end = size - 1
                self.offset = int(start)
                self.size = int(end) - int(start) + 1
                range = (int(start), int(end), int(size))
            else:
                range = None

            self.__send_resp_header(mime, size, range)
            return True

        else:
            self.send_error(404, 'Not Found')

    def __file_info(self):
        size = self.server._client.file.size
        ext = os.path.splitext(self.server._client.file.name)[1]
        mime = self.server._client.VIDEO_EXTS.get(ext)
        if not mime:
            mime = 'application/octet-stream'
        return size, mime

    def __send_resp_header(self, cont_type, size, range=False):

        if range:
            self.send_response(206, 'Partial Content')
        else:
            self.send_response(200, 'OK')

        self.send_header('Content-Type', cont_type)
        self.send_header('Accept-Ranges', 'bytes')

        if range:
            if isinstance(range, (tuple, list)) and len(range) == 3:
                self.send_header('Content-Range', 'bytes %d-%d/%d' % range)
                self.send_header('Content-Length', range[1] - range[0] + 1)
            else:
                raise ValueError('Invalid range value')
        else:
            self.send_header('Content-Length', size)

        self.send_header('Connection', 'close')
        self.end_headers()
