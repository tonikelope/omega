# -*- coding: utf-8 -*-

r"""
  ___  __  __ _____ ____    _    
 / _ \|  \/  | ____/ ___|  / \   
| | | | |\/| |  _|| |  _  / _ \  
| |_| | |  | | |__| |_| |/ ___ \ 
 \___/|_|  |_|_____\____/_/   \_\

 _   _ _____ ___ ____  _____ ____  ____  ___ ____  
| \ | | ____|_ _|  _ \| ____| __ )|  _ \|_ _|  _ \ 
|  \| |  _|  | || | | |  _| |  _ \| |_) || || | | |
| |\  | |___ | || |_| | |___| |_) |  _ < | || |_| |
|_| \_|_____|___|____/|_____|____/|_| \_\___|____/ 
                                                   
 _              _ _        _                  
| |_ ___  _ __ (_) | _____| | ___  _ __   ___ 
| __/ _ \| '_ \| | |/ / _ \ |/ _ \| '_ \ / _ \
| || (_) | | | | |   <  __/ | (_) | |_) |  __/
 \__\___/|_| |_|_|_|\_\___|_|\___/| .__/ \___|
                                  |_|         
                                  
Conector de vídeo para NEI (OMEGA)

Incluye un servidor proxy http local que permite:
    1) Aumentar velocidad de descarga de Real/Alldebrid al utilizar conexiones paralelas (configurable).
    2) Usar enlaces MegaCrypter con Real/Alldebrid.
    3) Reproducir por streaming vídeos troceados de forma transparente para el reproductor de KODI.

Enlaces de vídeo que maneja este conector: 

    1) Enlaces de MegaCrypter/MEGA (SIN trocear) con Real/Alldebrid desactivado -> se reproducen con la librería de MEGA (parcheada por OMEGA para soportar descarga multi-hilo).
    2) Enlaces de MegaCrypter/MEGA (troceados o no) con Real/Alldebrid activado -> se reproducen con este proxy.

"""

from core import scrapertools
from platformcode import config, logger, platformtools
from http.server import BaseHTTPRequestHandler, HTTPServer
from servers.debriders import realdebrid, alldebrid
import urllib.parse
import urllib.request
import time
from socketserver import ThreadingMixIn
import threading
import re
import base64
import hashlib
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import pickle
import shutil
import json
import http.cookiejar
import urllib.error


KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')
KODI_USERDATA_PATH = xbmcvfs.translatePath("special://userdata/")
KODI_NEI_COOKIES_PATH = KODI_USERDATA_PATH + "kodi_nei_cookies"
MEGA_FILES = None

DEFAULT_HTTP_TIMEOUT = 300

DEBRID_PROXY_HOST = 'localhost'
DEBRID_PROXY_PORT = int(config.get_setting("omega_debrid_proxy_port", "omega").strip())
OMEGA_REALDEBRID = config.get_setting("omega_realdebrid", "omega")
OMEGA_ALLDEBRID = config.get_setting("omega_alldebrid", "omega")

MAX_PBAR_CLOSE_WAIT = 60
MEGACRYPTER2DEBRID_ENDPOINT = 'https://noestasinvitado.com/megacrypter2debrid.php'
MEGACRYPTER2DEBRID_TIMEOUT = 300 #Cuando aumente la demanda habrá que implementar en el server de NEI un sistema de polling asíncrono
MEGACRYPTER2DEBRID_MULTI_RETRY = 5
VIDEO_MULTI_DEBRID_URL = None
VIDEO_MULTI_DEBRID_URL_LOCK = threading.Lock()

WORKER_CHUNK_SIZE = 5*1024*1024 #COMPROMISO
DEBRID_WORKERS = int(config.get_setting("omega_debrid_proxy_workers", "omega"))+1
MAX_CHUNKS_IN_QUEUE = ((int(config.get_setting("omega_debrid_proxy_chunks", "omega"))+1)*10) #Si sobra la RAM se puede aumentar (este buffer se suma al propio buffer de KODI)

DEBRID_ACCOUNT_FREE_SPACE = None
DEBRID_AUX_MEGA_ACCOUNTS = []

RESPONSE_READ_CHUNK_SIZE = 8*1024

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


class HTTPClient:
    def __init__(self, cookies_file=KODI_NEI_COOKIES_PATH, user_agent=None, proxy=None, ignore_config_proxy=False):
        self.cookies_file = cookies_file
        self.cookie_jar = http.cookiejar.LWPCookieJar()

        # Cargar cookies si existen
        if os.path.exists(self.cookies_file):
            self.cookie_jar.load(self.cookies_file, ignore_discard=True, ignore_expires=True)

        # Configurar el manejador de cookies
        cookie_handler = urllib.request.HTTPCookieProcessor(self.cookie_jar)

        # Configurar el proxy si se proporciona
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            self.opener = urllib.request.build_opener(cookie_handler, proxy_handler)
        elif not ignore_config_proxy and config.get_setting("omega_nei_proxy", "omega") and config.get_setting("omega_nei_proxy_url", "omega"):
            proxy = config.get_setting("omega_nei_proxy_url", "omega")
            proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            self.opener = urllib.request.build_opener(cookie_handler, proxy_handler)
        else:
            self.opener = urllib.request.build_opener(cookie_handler)

        # Configurar User-Agent si se proporciona
        self.headers = DEFAULT_HEADERS

    def save_cookies(self):
        """Guarda las cookies en un archivo."""
        self.cookie_jar.save(self.cookies_file, ignore_discard=True, ignore_expires=True)

    def request(self, url, method="GET", data=None, headers=None, timeout=10, ignore_errors=False):
        """Realiza una solicitud HTTP con GET o POST."""
        if data:
            data = urllib.parse.urlencode(data).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers={**self.headers, **(headers or {})}, method=method)

        try:
            response = self.opener.open(request, timeout=timeout)
            self.save_cookies()
            return response.read().decode("utf-8")

        except urllib.error.HTTPError as e:
            if ignore_errors:
                return e.read().decode("utf-8")  # Devuelve el contenido a pesar del error
            else:
                raise  # Relanza la excepción si no se quiere ignorar errores

        except urllib.error.URLError as e:
            raise RuntimeError(f"Error de conexión: {e}")

    def get(self, url, headers=None, timeout=10, ignore_errors=False):
        """Realiza una solicitud GET."""
        return self.request(url, method="GET", headers=headers, timeout=timeout, ignore_errors=ignore_errors)

    def post(self, url, data=None, headers=None, timeout=10, ignore_errors=False):
        """Realiza una solicitud POST."""
        return self.request(url, method="POST", data=data, headers=headers, timeout=timeout, ignore_errors=ignore_errors)

try:
    if config.get_setting("omega_debrid_mega_url", "omega"):
        client = HTTPClient(ignore_config_proxy=True)
        DEBRID_AUX_MEGA_ACCOUNTS=json.loads(client.get(config.get_setting("omega_debrid_mega_url", "omega"), timeout=DEFAULT_HTTP_TIMEOUT).encode('utf-8').decode('utf-8-sig'))
except:
    DEBRID_AUX_MEGA_ACCOUNTS = []


def notification_title():
    return "OMEGA NEIDEBRID"


def omegaNotification(msg, timeout=5000, sound=True):
    xbmcgui.Dialog().notification(notification_title(), msg, os.path.join(xbmcaddon.Addon().getAddonInfo("path"),"resources","media","channels","thumb","omega.gif"), timeout, sound)

"""
Esta clase convierte una URL de Real/Alldebrid normal en una múltiple para reproducir por streaming vídeos 
troceados (al estilo MegaBasterd o el comando de Unix split)
"""
class multiPartVideoDebridURL():
    def __init__(self, url):
        self.url = url
        self.multi_urls = self.__loadMultiURLFile()
        self.__updateSizeAndRanges()
        
    #Carga un fichero temporal con una lista de tuplas [(absolute_start_offset, absolute_end_offset, url1), (absolute_start_offset, absolute_end_offset, url2)...] si el vídeo está troceado
    def __loadMultiURLFile(self):
        hash_url = hashlib.sha256(self.url.encode('utf-8')).hexdigest()

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_multi_' + hash_url

        if os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    multi_urls = pickle.load(file)
                    return multi_urls
                except:
                    return None

        return None

    #Carga el tamaño del vídeo y si el servidor acepta consultas parciales por rangos 
    def __updateSizeAndRanges(self):

        if self.multi_urls:

            self.accept_ranges = True
            self.size = 0

            for url in self.multi_urls:
                data = self.__getUrlSizeAndRanges(url[2])
                self.size+=data[0]

                if self.accept_ranges:
                    self.accept_ranges = data[1]

        else:
            self.size, self.accept_ranges = self.__getUrlSizeAndRanges(self.url)

        if not self.accept_ranges:
            omegaNotification("ESTE VÍDEO NO PERMITE AVANZAR/RETROCEDER")

    def __getUrlSizeAndRanges(self, url):
        request = urllib.request.Request(url, method='HEAD')
        response = urllib.request.urlopen(request)

        if 'Content-Length' in response.headers:
            return (int(response.headers['Content-Length']), ('Accept-Ranges' in response.headers and response.headers['Accept-Ranges']!='none'))
        else:
            return (-1, False)

    
    #Este método traduce una petición de un rango de bytes absoluto en una lista de tuplas con rangos parciales de las diferentes URLS involucradas (en caso de que el vídeo esté troceado)
    def absolute2PartialRanges(self, start_offset, end_offset):
        if self.multi_urls == None:
            return [(start_offset, end_offset, self.url)]
        else:

            inicio = start_offset
            final = end_offset
            u = 0

            while inicio>self.multi_urls[u][1] and u<len(self.multi_urls):
                u+=1

            if u>=len(self.multi_urls):
                return None

            rangos_parciales=[]

            while inicio < final and u < len(self.multi_urls):
                
                url_trozo = self.multi_urls[u][2]

                rango_absoluto = (inicio, min(final, self.multi_urls[u][1]))

                inicio+=rango_absoluto[1]-rango_absoluto[0]+1

                rango_parcial = (rango_absoluto[0] - self.multi_urls[u][0], rango_absoluto[1] - self.multi_urls[u][0], url_trozo)

                rangos_parciales.append(rango_parcial)

                u+=1

            return rangos_parciales


"""
Esta clase se encarga de mandarle al reproductor de vídeo de KODI el rango de bytes que ha solicitado
Los lee de una cola de chunks que van llenando varios workers de la clase neiDebridVideoProxyChunkDownloader
"""
class neiDebridVideoProxyChunkWriter():

    def __init__(self, wfile, start_offset, end_offset):
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.output = wfile
        self.chunk_downloaders = []
        self.queue = {}
        self.cv_queue_full = threading.Condition()
        self.cv_new_element = threading.Condition()
        self.bytes_written = start_offset
        self.exit = False
        self.next_offset_required = start_offset
        self.chunk_offset_lock = threading.Lock()
        self.chunk_queue_lock = threading.Lock()
        self.chunk_error_notify = False
        self.rejected_offsets = []


    def run(self):

        logger.info('CHUNKWRITER '+' ['+str(self.start_offset)+'-] HELLO')

        if DEBRID_WORKERS > 1:

            for c in range(0, DEBRID_WORKERS):
                chunk_downloader = neiDebridVideoProxyChunkDownloader(c+1, self)
                self.chunk_downloaders.append(chunk_downloader)
                t = threading.Thread(target=chunk_downloader.run)
                t.daemon = True
                t.start()

            try:

                while not self.exit and self.bytes_written < self.end_offset:
                    
                    while not self.exit and self.bytes_written < self.end_offset and self.bytes_written in self.queue:

                        with self.chunk_queue_lock:

                            current_chunk = self.queue.pop(self.bytes_written)

                        with self.cv_queue_full:

                            self.cv_queue_full.notify_all()

                        self.output.write(current_chunk)

                        self.bytes_written+=len(current_chunk)
                        
                    if not self.exit and self.bytes_written < self.end_offset:
                        
                        with self.cv_new_element:
                            self.cv_new_element.wait(1)

            except Exception as ex:
                logger.info(ex)

            self.exit = True

            for downloader in self.chunk_downloaders:
                downloader.exit = True

            with self.chunk_queue_lock:
                self.queue.clear()
        else:
            partial_ranges = VIDEO_MULTI_DEBRID_URL.absolute2PartialRanges(self.start_offset, self.end_offset)

            for partial_range in partial_ranges:

                p_inicio = partial_range[0]

                p_final = partial_range[1]

                url = partial_range[2]

                p_length = p_final-p_inicio+1

                request_headers = {'Range': 'bytes='+str(p_inicio)+'-'+str(p_final+5)} #Chapu-hack: pedimos unos bytes extra porque a veces RealDebrid devuelve alguno menos

                request = urllib.request.Request(url, headers=request_headers)

                with urllib.request.urlopen(request) as response:
                    p_chunk_read = 0
                    while p_chunk_read < p_length:
                        p_chunk = response.read(min(RESPONSE_READ_CHUNK_SIZE, p_length-p_chunk_read))
                        p_chunk_read+=len(p_chunk)
                        self.output.write(p_chunk)

        logger.info('CHUNKWRITER '+' ['+str(self.start_offset)+'-] BYE')


    def nextOffsetRequired(self):
        with self.chunk_offset_lock:

            if len(self.rejected_offsets) > 0:
                return self.rejected_offsets.pop(0)

            next_offset = self.next_offset_required

            self.next_offset_required = self.next_offset_required + WORKER_CHUNK_SIZE if self.next_offset_required + WORKER_CHUNK_SIZE < self.end_offset else -1

            return next_offset


    def getRunningWorkers(self):
        r=0

        for d in self.chunk_downloaders:
            if not d.exit:
                r+=1

        return r


    def rejectThisOffset(self, downloader, offset):
        with self.chunk_offset_lock:
            if not offset in self.rejected_offsets:
                self.rejected_offsets.append(offset)

            if self.getRunningWorkers() > 1:
                downloader.exit = True

                if not self.chunk_error_notify:
                    self.chunk_error_notify = True
                    omegaNotification('CUIDADO: ¿Demasiados HILOS en ajustes?')


    
#Clase de los workers de descarga.
class neiDebridVideoProxyChunkDownloader():
    
    def __init__(self, id, chunk_writer):
        self.id = id
        self.url = VIDEO_MULTI_DEBRID_URL
        self.exit = False
        self.chunk_writer = chunk_writer
        

    def run(self):

        logger.info('CHUNKDOWNLOADER ['+str(self.chunk_writer.start_offset)+'-] '+str(self.id)+' HELLO')

        bytes_downloaded = 0

        while not self.exit and not self.chunk_writer.exit:

            offset = self.chunk_writer.nextOffsetRequired()

            try:

                if offset >=0:

                    final = min(offset + WORKER_CHUNK_SIZE - 1, self.chunk_writer.end_offset)

                    required_chunk_size = final-offset+1

                    partial_ranges = self.url.absolute2PartialRanges(offset, final) #Si el vídeo está troceado, es posible que el chunk pedido por el reproductor de KODI tenga bytes de diferentes trozos (URLs)

                    while not self.exit and not self.chunk_writer.exit and len(self.chunk_writer.queue) >= MAX_CHUNKS_IN_QUEUE and offset!=self.chunk_writer.bytes_written:
                        with self.chunk_writer.cv_queue_full:
                            self.chunk_writer.cv_queue_full.wait(1)

                    if not self.chunk_writer.exit and not self.exit:
                        
                        chunk_error = True

                        while not self.exit and not self.chunk_writer.exit and chunk_error:

                            chunk = bytearray()

                            for partial_range in partial_ranges:

                                p_offset = partial_range[0]

                                p_final = partial_range[1]

                                url = partial_range[2]

                                request_headers = {'Range': 'bytes='+str(p_offset)+'-'+str(p_final+5)} #Chapu-hack: pedimos unos bytes extra porque a veces RealDebrid devuelve alguno menos

                                partial_chunk_error = True

                                while not self.exit and not self.chunk_writer.exit and partial_chunk_error:
                                    
                                    request = urllib.request.Request(url, headers=request_headers)

                                    with urllib.request.urlopen(request) as response:

                                        required_partial_chunk_size = p_final-p_offset+1

                                        partial_chunk=response.read(required_partial_chunk_size)

                                        bytes_downloaded+=len(partial_chunk)

                                        if len(partial_chunk) == required_partial_chunk_size:
                                            chunk+=partial_chunk
                                            partial_chunk_error = False
                                        else:
                                            logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(p_offset)+'-'+str(p_final)+' ('+str(len(partial_chunk))+' bytes) PARTIAL CHUNK SIZE ERROR! (¿posible bug del DEBRIDER?)')

                            if not self.exit and not self.chunk_writer.exit:

                                if len(chunk) == required_chunk_size:

                                    with self.chunk_writer.chunk_queue_lock:
                                    
                                        if not self.exit and not self.chunk_writer.exit:
                                            self.chunk_writer.queue[offset]=chunk

                                    with self.chunk_writer.cv_new_element:
                                        self.chunk_writer.cv_new_element.notify_all()

                                    chunk_error = False
                                else:
                                    logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(offset)+'-'+str(final)+' ('+str(len(chunk))+' bytes) CHUNK SIZE ERROR! (¿posible bug del DEBRIDER?)')

                else:
                    with self.chunk_writer.chunk_offset_lock:
                        if len(self.chunk_writer.rejected_offsets) == 0:
                            self.exit = True

            except Exception as ex:
                logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> OFFSET '+str(offset)+' HTTP ERROR! (¿muchos hilos?)')
                logger.debug(ex)
                self.chunk_writer.rejectThisOffset(self, offset)

        self.exit = True

        logger.info('CHUNKDOWNLOADER ['+str(self.chunk_writer.start_offset)+'-] '+str(self.id)+' BYE ('+str(bytes_downloaded)+' bytes downloaded)')


"""
Esta clase crea un servidor PROXY HTTP para manejar las peticiones del reproductor de vídeo de KODI y simular que los vídeos troceados no lo son.
Además mejora la velocidad de descarga de Real/Alldebrid al utilizar múltiples conexiones paralelas.
"""
class neiDebridVideoProxy(BaseHTTPRequestHandler):

    def do_HEAD(self):

        self.__updateURL()

        if VIDEO_MULTI_DEBRID_URL.size < 0:
            
            self.send_response(503)
            self.end_headers()

        else:

            self.__sendResponseHeaders()

    
    def do_GET(self):
          
        if self.path.startswith('/shutdown'):
            
            self.send_response(200)

            self.end_headers()

            self.server.shutdown()

        elif self.path.startswith('/isalive'):
            
            self.send_response(200)

            self.end_headers()
        else:

            self.__updateURL()

            if VIDEO_MULTI_DEBRID_URL.size < 0:
                
                self.send_response(503)
                self.end_headers()

            else:
                try:

                    range_request = self.__sendResponseHeaders()
                    
                    if range_request:

                        chunk_writer = neiDebridVideoProxyChunkWriter(self.wfile, int(range_request[0]), int(range_request[1]) if range_request[1] else int(VIDEO_MULTI_DEBRID_URL.size-1))
                        t = threading.Thread(target=chunk_writer.run)
                        t.start()
                        t.join()
                                          
                    else:

                        if VIDEO_MULTI_DEBRID_URL.multi_urls:
                            for murl in VIDEO_MULTI_DEBRID_URL.multi_urls:
                                request = urllib.request.Request(murl[2])
                                with urllib.request.urlopen(request) as response:
                                    shutil.copyfileobj(response, self.wfile)
                        else:
                            request = urllib.request.Request(VIDEO_MULTI_DEBRID_URL.url)
                            with urllib.request.urlopen(request) as response:
                                shutil.copyfileobj(response, self.wfile)

                except Exception as ex:
                    logger.info(ex)

    
    def __updateURL(self):
        global VIDEO_MULTI_DEBRID_URL

        url = proxy2DebridURL(self.path)

        logger.debug(url)

        with VIDEO_MULTI_DEBRID_URL_LOCK:
        
            if not VIDEO_MULTI_DEBRID_URL or VIDEO_MULTI_DEBRID_URL.url != url:
            
                VIDEO_MULTI_DEBRID_URL = multiPartVideoDebridURL(url)


    def __sendResponseHeaders(self):
        range_request = self.__parseRequestRanges()

        if not range_request or not VIDEO_MULTI_DEBRID_URL.accept_ranges:
            self.__sendCompleteResponseHeaders()
            return False
        else:

            inicio = int(range_request[0])

            final = int(range_request[1]) if range_request[1] else (int(VIDEO_MULTI_DEBRID_URL.size) - 1)

            self.__sendPartialResponseHeaders(inicio, final)

            return range_request

    
    def __parseRequestRanges(self):

        if 'Range' in self.headers:

            m = re.compile(r'bytes=([0-9]+)-([0-9]+)?', re.DOTALL).search(self.headers['Range'])

            return (m.group(1), m.group(2))

        else:

            return None

    
    def __sendPartialResponseHeaders(self, inicio, final):

        headers = {'Accept-Ranges':'bytes', 'Content-Length': str(int(final)-int(inicio)+1), 'Content-Range': 'bytes '+str(inicio)+'-'+str(final)+'/'+str(VIDEO_MULTI_DEBRID_URL.size), 'Content-Disposition':'attachment', 'Content-Type':'application/octet-stream', 'Connection':'close'}

        self.send_response(206)

        logger.debug('OMEGA RESPONSE 206')

        for h in headers:
            self.send_header(h, headers[h])
            logger.debug('OMEGA RESPONSE HEADER '+h+' '+headers[h])

        self.end_headers()

    
    def __sendCompleteResponseHeaders(self):
        headers = {'Accept-Ranges':'bytes' if VIDEO_MULTI_DEBRID_URL.accept_ranges else 'none', 'Content-Length': str(VIDEO_MULTI_DEBRID_URL.size), 'Content-Disposition':'attachment', 'Content-Type':'application/octet-stream', 'Connection':'close'}

        self.send_response(200)

        logger.debug('OMEGA RESPONSE 200')

        for h in headers:
            self.send_header(h, headers[h])
            logger.debug('OMEGA RESPONSE HEADER '+h+' '+headers[h])

        self.end_headers()



class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

if OMEGA_REALDEBRID or OMEGA_ALLDEBRID:
    try:
        proxy_server = ThreadingSimpleServer((DEBRID_PROXY_HOST, DEBRID_PROXY_PORT), neiDebridVideoProxy)
        
        if DEBRID_WORKERS > 1:
            omegaNotification('PROXY ON ('+str(DEBRID_WORKERS)+' hilos + '+str(round((WORKER_CHUNK_SIZE*MAX_CHUNKS_IN_QUEUE)/(1024*1024)))+'MB)', sound=False)
        else:
            omegaNotification('PROXY ON (un hilo sin buffer)', sound=False)
    except:
        proxy_server = None 


"""
Este método convierte un enlace de MegaCrypter en un enlace temporal auxiliar de MEGA. 
Devuelve el enlace de MEGA temporal (compatible con Real/Alldebrid) y un hash del FID de MEGA del fichero original
"""
def megacrypter2auxmega(link, clean=True, account=1):

    global DEBRID_ACCOUNT_FREE_SPACE

    try:

        if DEBRID_AUX_MEGA_ACCOUNTS:
            cuenta = DEBRID_AUX_MEGA_ACCOUNTS[account-1]
            email = base64.urlsafe_b64encode(cuenta['email'].encode('utf-8'))
            password = base64.urlsafe_b64encode(cuenta['password'].encode('utf-8'))
        else:
            email = base64.urlsafe_b64encode(config.get_setting("omega_debrid_mega_email"+str(account), "omega").encode('utf-8'))
            password = base64.urlsafe_b64encode(config.get_setting("omega_debrid_mega_password"+str(account), "omega").encode('utf-8'))

        megacrypter_link = link.split('#')

        link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

        noexpire = urllib.parse.quote(megacrypter_link[4]) #Hay que hacerlo así porque el noexpire está en base64 normal (no url safe)

        client = HTTPClient()

        mega_link_response = client.get(MEGACRYPTER2DEBRID_ENDPOINT+'?noexpire='+noexpire+'&c='+('1' if clean else '0')+'&l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''), timeout=MEGACRYPTER2DEBRID_TIMEOUT)

        logger.info(MEGACRYPTER2DEBRID_ENDPOINT+'?c='+('1' if clean else '0')+'&l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''))

        logger.info(mega_link_response)

        json_response = json.loads(mega_link_response.encode('utf-8').decode('utf-8-sig'))

        logger.info(json_response)

        if 'error' in json_response:
            logger.debug(json_response['error'])
            return None

        if 'link' in json_response and 'fid_hash' in json_response:
            mega_link = json_response['link']
            
            fid_hash = json_response['fid_hash']
            
            DEBRID_ACCOUNT_FREE_SPACE = int(json_response['free_space'])

            return (mega_link, fid_hash)
        else:
            return None
    except:
        return None


"""
Este método es como el anterior pero no genera el enlaces auxiliar de MEGA, sino 
que nos devuelve el hash del FID original (para ver si ya lo tenemos cacheado).
"""
def megacrypter2auxmegaHASH(link):
    megacrypter_link = link.split('#')

    link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

    noexpire = urllib.parse.quote(megacrypter_link[4]) #Hay que hacerlo así porque el noexpire está en base64 normal (no url safe)

    client = HTTPClient()

    mega_link_response = client.get(MEGACRYPTER2DEBRID_ENDPOINT+'?noexpire='+noexpire+'&l='+link_data, timeout=MEGACRYPTER2DEBRID_TIMEOUT)

    logger.info(MEGACRYPTER2DEBRID_ENDPOINT+'?l='+link_data)

    logger.info(mega_link_response)

    json_response = json.loads(mega_link_response.encode('utf-8').decode('utf-8-sig'))

    logger.info(json_response)

    if 'error' in json_response:
        logger.debug(json_response['error'])
        return None

    if 'fid_hash' in json_response:
        return json_response['fid_hash']
    else:
        return None


def test_video_exists(page_url):
    
    if OMEGA_REALDEBRID or OMEGA_ALLDEBRID:
        return True, ""

    from megaserver import Client
    
    c = Client(url=page_url, is_playing_fnc=platformtools.is_playing)
    
    global MEGA_FILES
    
    MEGA_FILES = c.get_files()
    
    if isinstance(MEGA_FILES, int):
        return False, "Error codigo %s" % str(MEGA_FILES)

    return True, ""


#Para comprobar si las urls de Real/Alldebrid cacheadas aún funcionan
def check_debrid_urls(itemlist):

    try:
        for i in itemlist:
            url = proxy2DebridURL(i[1])
            logger.info(url)
            request = urllib.request.Request(url, method='HEAD')
            response = urllib.request.urlopen(request)

            if response.status != 200 or 'Content-Length' not in response.headers:
                return False
            elif 'Accept-Ranges' in response.headers and response.headers['Accept-Ranges']!='none':
                size = int(response.headers['Content-Length'])
                request2 = urllib.request.Request(url, headers={'Range': 'bytes='+str(size-1)+'-'+str(size-1)})
                response2 = urllib.request.urlopen(request2)

                if response2.status != 206:
                    return False
    except:
        return False

    return True


#Comprueba la cache de URLS convertidas MEGA/MegaCrypter -> Real/Alldebrid (devuelve True si el enlace no está cacheado)
def neiURL2DEBRIDCheckCache(page_url):

    if 'megacrypter.noestasinvitado' in page_url:

        fid_hash = megacrypter2auxmegaHASH(page_url)

        if not fid_hash:
            return True

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_'+getDebridServiceString()+'_' + fid_hash

        if os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                    logger.info('DEBRID LEYENDO CACHE -> '+fid_hash)
                except:
                    urls = None

            return not urls or not check_debrid_urls(urls)
        else:
            return True
    else:

        fid = re.subr(r'^.*?#F?!(.*?)!.*$', r'\1', page_url)

        fid_hash = hashlib.sha256(fid).hexdigest()

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_'+getDebridServiceString()+'_' + fid_hash

        if os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                    logger.info('DEBRID LEYENDO CACHE -> '+fid_hash)
                except:
                    urls = None

            return not urls or not check_debrid_urls(urls)
        else:
            return True


def getDebridServiceString():
    if OMEGA_REALDEBRID:
        return 'realdebrid'
    elif OMEGA_ALLDEBRID:
        return 'alldebrid'
    else:
        return None


#Este método convierte un enlace de noestasinvitado.com MEGA/MegaCrypter en uno de Real/Alldebrid ("proxyficado" para el reproductor de KODI)
def neiURL2DEBRID(page_url, clean=True, cache=True, progress_bar=True, account=1):

    global DEBRID_ACCOUNT_FREE_SPACE

    if progress_bar:
        pbar = xbmcgui.DialogProgressBG()
        pbar.create('[B]OMEGA[/B]', '[B][COLOR yellow]Cocinando enlace[/COLOR] ['+getDebridServiceString()+'] (paciencia)...[/B]')
    
    if 'megacrypter.noestasinvitado' in page_url:

        fid_hash = megacrypter2auxmegaHASH(page_url)

        if not fid_hash:
            if progress_bar:
                close_background_pbar(pbar)
            omegaNotification("ERROR: POSIBLE ENLACE MEGACRYPTER CADUCADO")
            xbmcgui.Dialog().dialog.ok('MEGACRYPTER ERROR', "Hay algún error con MEGACRYPTER (posible enlace caducado)\n\n[B]Sugerencia: purga la caché de OMEGA y vuelve a entrar en la carpeta.[/B]")
            return [["NEI DEBRID ERROR (posible enlace de MegaCrypter caducado (purga la caché de OMEGA, sal y vuelve a entrar en la carpeta))", ""]]

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_'+getDebridServiceString()+'_' + fid_hash

        if cache and os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                except:
                    urls = None

            urls_ok=(urls and check_debrid_urls(urls))

            if urls_ok:
                logger.info('DEBRID USANDO CACHE -> '+fid_hash)
            else:
                os.remove(filename_hash)

        if not cache or not os.path.isfile(filename_hash):
            with open(filename_hash, "wb") as file:

                response = megacrypter2auxmega(page_url, clean=clean, account=account)

                if not response:
                    if progress_bar:
                        close_background_pbar(pbar)
                    omegaNotification("ERROR: REVISA TUS CUENTAS DE MEGA AUXILIARES")
                    xbmcgui.Dialog().dialog.ok('DEBRID ERROR (FALLO EN CUENTAS DE MEGA AUXILIARES)', "Ha fallado la generación del enlace de MEGA auxiliar.\n\n[B]Sugerencia: revisa que haya espacio suficiente en tus cuentas de MEGA auxiliares.[/B]")
                    return [["NEI DEBRID ERROR (revisa que haya espacio suficiente en tus cuentas de MEGA auxiliares)", ""]]

                page_url = response[0]

                if OMEGA_REALDEBRID:
                    urls = realdebrid.get_video_url(page_url)
                elif OMEGA_ALLDEBRID:
                    urls = alldebrid.get_video_url(page_url)
                else:
                    return None

                if urls and len(urls)>0:
                    for u in urls:
                        u[0]='VIDEO NEIDEBRID'

                        if u[1]:
                            u[1]=debrid2proxyURL(u[1])
                        else:
                            if progress_bar:
                                close_background_pbar(pbar)
                            
                            omegaNotification("DEBRID ERROR")
                            xbmcgui.Dialog().ok('DEBRID ERROR', "HAY ALGÚN PROBLEMA ENTRE TU SERVICIO DE DEBRID Y MEGA\n(REVISA EL ESTADO DE PAGO TU SUSCRIPCIÓN O ESPERA UNOS MINUTOS)\n\n[B]Sugerencia: puedes probar a desactivar Real/AllDebrid en ajustes y conectar a MEGA directamente.[/B]")
                            return [["ERROR: REAL/ALLDEBRID <----> MEGA", ""]]

                    pickle.dump(urls, file)
                else:
                    if progress_bar:
                        close_background_pbar(pbar)

                    omegaNotification("DEBRID ERROR")
                    xbmcgui.Dialog().ok('DEBRID ERROR', "HAY ALGÚN PROBLEMA ENTRE TU SERVICIO DE DEBRID Y MEGA\n(REVISA EL ESTADO DE PAGO TU SUSCRIPCIÓN O ESPERA UNOS MINUTOS)\n\n[B]Sugerencia: puedes probar a desactivar Real/AllDebrid en ajustes y conectar a MEGA directamente.[/B]")
                    return [["ERROR: REAL/ALLDEBRID <----> MEGA", ""]]
    else:

        fid = re.subr(r'^.*?#F?!(.*?)!.*$', r'\1', page_url)

        fid_hash = hashlib.sha256(fid).hexdigest()

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_'+getDebridServiceString()+'_' + fid_hash

        if cache and os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                except:
                    urls = None
       
            urls_ok=(urls and check_debrid_urls(urls))

            if urls_ok:
                logger.info('DEBRID USANDO CACHE -> '+fid_hash)
            else:
                os.remove(filename_hash)

        if not cache or not os.path.isfile(filename_hash):
            with open(filename_hash, "wb") as file:
                
                if OMEGA_REALDEBRID:
                    urls = realdebrid.get_video_url(page_url)
                elif OMEGA_ALLDEBRID:
                    urls = alldebrid.get_video_url(page_url)
                else:
                    urls = None

                if urls and len(urls)>0:
                    for u in urls:
                        u[0]='VIDEO NEIDEBRID'
                        
                        if u[1]:
                            u[1]=debrid2proxyURL(u[1])
                        else:
                            if progress_bar:
                                close_background_pbar(pbar)
                            
                            omegaNotification("DEBRID ERROR")
                            xbmcgui.Dialog().ok('DEBRID ERROR', "HAY ALGÚN PROBLEMA ENTRE TU SERVICIO DE DEBRID Y MEGA\n(REVISA EL ESTADO DE PAGO TU SUSCRIPCIÓN O ESPERA UNOS MINUTOS)\n\n[B]Sugerencia: puedes probar a desactivar Real/AllDebrid en ajustes y conectar a MEGA directamente.[/B]")
                            return [["ERROR: REAL/ALLDEBRID <----> MEGA", ""]]

                    pickle.dump(urls, file)
                else:
                    if progress_bar:
                        close_background_pbar(pbar)

                    omegaNotification("DEBRID ERROR")
                    xbmcgui.Dialog().ok('DEBRID ERROR', "HAY ALGÚN PROBLEMA ENTRE TU SERVICIO DE DEBRID Y MEGA\n(REVISA EL ESTADO DE PAGO TU SUSCRIPCIÓN O ESPERA UNOS MINUTOS)\n\n[B]Sugerencia: puedes probar a desactivar Real/AllDebrid en ajustes y conectar a MEGA directamente.[/B]")
                    return [["ERROR: REAL/ALLDEBRID <----> MEGA", ""]]

    if progress_bar:
        close_background_pbar(pbar)
    
    return urls


"""
Este método (común en todos los conectores de ALFA) se encarga de generar las URLS de vídeo para el reproductor de KODI.

Los enlaces de MEGA/MegaCrypter sin trocear y sin Real/Alldebrid activado se envían a la librería de MEGA (parcheada por OMEGA)

Los enlaces de MEGA/Megacrypter (troceados o no) y con Real/Alldebrid activado se "proxifican" y si el vídeo
está troceado se genera un fichero en disco con las URLS Real/Alldebrid de las diferentes partes que 
más tarde usará el proxy para responder a las peticiones del reproductor de KODI y simular que 
el vídeo NO está troceado.
"""
def get_video_url(page_url, premium=False, user="", password="", video_password=""):

    global DEBRID_ACCOUNT_FREE_SPACE

    logger.info(page_url)

    pbar = xbmcgui.DialogProgressBG()

    pbar.create('[B]OMEGA[/B]', '[B]Cargando conector NEI...[/B]')

    #El proxy se carga una vez con el primer vídeo y se queda cargado mientras KODI esté corriendo
    if (OMEGA_REALDEBRID or OMEGA_ALLDEBRID) and proxy_server:
        start_proxy()

    close_background_pbar(pbar)

    if page_url[0]=='*':
        #ENLACE MULTI-URL-DEBRID (vídeo troceado)

        logger.info(page_url)

        if OMEGA_REALDEBRID or OMEGA_ALLDEBRID:

            multi_video_proxy_urls=[]

            video_sizes=[]

            page_urls = page_url.split('#')

            pbar = xbmcgui.DialogProgressBG()

            pbar.create('[B]OMEGA[/B]', '[B][COLOR yellow]Cocinando enlace troceado[/COLOR] M('+str(len(page_urls)-1)+') ['+getDebridServiceString()+'] (paciencia)...[/B]')

            pbar_increment = round(100/(len(page_urls)-1))

            pbar_tot = 100

            pbar_counter = 0

            i = 1

            #Primero comprobamos si existe en la cache MegaCrypter -> Real/Alldebrid una entrada para este vídeo concreto
            cache_error=False

            while i<len(page_urls) and not cache_error:
                url = base64.b64decode(page_urls[i].encode('utf-8')).decode('utf-8')
                cache_error = neiURL2DEBRIDCheckCache(url)
                i+=1

            i = 1

            use_cache = not cache_error

            megacrypter2debrid_error = False

            account = 1

            DEBRID_ACCOUNT_FREE_SPACE = None

            #Traducimos los enlaces MegaCrypter de los trozos del vídeo a enlaces Real/Alldebrid (usamos la caché si está disponible para este vídeo)
            while i<len(page_urls) and not megacrypter2debrid_error:
                url = base64.b64decode(page_urls[i].encode('utf-8')).decode('utf-8')
                logger.info(url)

                if 'megacrypter.noestasinvitado' in url:
                    url_parts = url.split('#')
                    current_video_size = int(url_parts[2])
                else:
                    url_parts = url.split('@')
                    current_video_size = int(url_parts[1])
                
                video_sizes.append(current_video_size)

                #Debemos ir controlando el espacio libre en las cuentas de MEGA AUXILIARES al crear los trozos para cambiar de cuenta
                new_account = (account+1 if (DEBRID_ACCOUNT_FREE_SPACE and current_video_size > DEBRID_ACCOUNT_FREE_SPACE) else account)

                if new_account!=account:
                    DEBRID_ACCOUNT_FREE_SPACE = None

                #La cuenta auxiliar de MEGA se trunca al empezar a trabajar con ella
                clean = (i==1 or new_account!=account)

                account = new_account

                retry = 0

                megacrypter2debrid_error = True

                while megacrypter2debrid_error and retry<MEGACRYPTER2DEBRID_MULTI_RETRY:

                    debrid_url = neiURL2DEBRID(url, clean=clean, cache=use_cache, progress_bar=False, account=account)

                    if debrid_url[0][1] and debrid_url[0][1].strip():
                        megacrypter2debrid_error = False
                    else:
                        retry+=1

                if not megacrypter2debrid_error:
                    multi_video_proxy_urls.append(debrid_url)

                pbar_counter+=min(pbar_increment, 100-pbar_counter)

                pbar.update(pbar_counter)

                i+=1

            close_background_pbar(pbar)

            if not megacrypter2debrid_error:

                """
                Ahora generamos la tabla de traducción multi_urls_ranges con las URLS Real/Alldebrid de cada trozo y 
                los rangos de bytes absolutos que más tarde usará el proxy para traducir al vuelo las peticiones de 
                rangos de bytes absolutos del reproductor de vídeo de KODI por rangos parciales de cada trozo.
                [
                (absolute_start_offset, absolute_end_offset, debrid_url_1), 
                (absolute_start_offset, absolute_end_offset, debrid_url_2),
                (absolute_start_offset, absolute_end_offset, debrid_url_3),
                ...]
                """

                logger.info(multi_video_proxy_urls)

                multi_urls_ranges=[]

                s=0

                i=0

                for murl in multi_video_proxy_urls:
                    multi_urls_ranges.append((s, s+video_sizes[i]-1, proxy2DebridURL(murl[0][1])))
                    s+=video_sizes[i]
                    i+=1

                logger.info(multi_urls_ranges)

                first_multi_proxy_url_title = multi_video_proxy_urls[0][0][0]

                first_multi_proxy_url = multi_video_proxy_urls[0][0][1]

                #Se usa el hash de la primera URL Real/Alldebrid (sin "proxyficar") como ID del fichero de traducción de rangos
                hash_url = hashlib.sha256(proxy2DebridURL(first_multi_proxy_url).encode('utf-8')).hexdigest()
                filename_hash = KODI_TEMP_PATH + 'kodi_nei_multi_' + hash_url

                with open(filename_hash, "wb") as file:
                    pickle.dump(multi_urls_ranges, file)

                return [[first_multi_proxy_url_title.replace('VIDEO', 'VIDEO TROCEADO'), first_multi_proxy_url]]
            else:
                omegaNotification("ERROR: FALLO AL GENERAR ENLACES DEBRID")
                return [["NEI DEBRID ERROR (revisa que haya espacio suficiente en tu cuenta de MEGA auxiliar)", ""]]

        else:
            #PENDIENTE DE IMPLEMENTAR ENLACES DE VÍDEO TROCEADOS CONECTANDO A MEGA DIRECTAMENTE (SIN DEBRID)
            omegaNotification("ERROR: VÍDEOS TROCEADOS NO SOPORTADOS (DE MOMENTO)")
            return [["NO SOPORTADO", ""]]

    else:

        if OMEGA_REALDEBRID or OMEGA_ALLDEBRID:
            return neiURL2DEBRID(page_url)

        page_url = page_url.replace('/embed#', '/#')
        
        logger.info("(page_url='%s')" % page_url)
        
        video_urls = []

        for f in MEGA_FILES:
            media_url = f["url"]
            video_urls.append([scrapertools.get_filename_from_url(media_url)[-4:] + " [mega]", media_url])

        return video_urls


def thread_close_pbar(pbar):
    monitor = xbmc.Monitor()

    pbar.close()

    conta_wait=0

    while not monitor.abortRequested() and not pbar.isFinished() and conta_wait<MAX_PBAR_CLOSE_WAIT:
        pbar.close()
        monitor.waitForAbort(1)
        conta_wait+=1


def close_background_pbar(pbar):
    pbar.update(100)
    t = threading.Thread(target=thread_close_pbar, args=(pbar,))
    t.setDaemon(True)
    t.start()


def debrid2proxyURL(url):
    return 'http://'+DEBRID_PROXY_HOST+':'+str(DEBRID_PROXY_PORT)+'/proxy/'+urllib.parse.quote(url)
    

def proxy2DebridURL(url):
    return urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', url))


def proxy_run():
    logger.info(time.asctime(), "NEI DEBRID VIDEO PROXY SERVER Starts - %s:%s" % (DEBRID_PROXY_HOST, DEBRID_PROXY_PORT))
    proxy_server.serve_forever()


def start_proxy():
    t = threading.Thread(target=proxy_run)
    t.setDaemon(True)
    t.start()
