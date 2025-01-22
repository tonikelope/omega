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
                                
Worker para descarga/streaming multi-hilo de vídeos de MEGA

"""

import threading
import urllib.request, urllib.error, urllib.parse
from . import Chunk
import time
import socket
from platformcode import logger,config

MAX_CHUNK_BUFFER_SIZE = ((int(config.get_setting("omega_megalib_chunks", "omega"))+1)*10)
BLOCK_SIZE = 8*1024
SOCKET_TIMEOUT = 15
SOCKET_PROXY_TIMEOUT = 5
FORCE_PROXY_MODE = False
PAUSE_HTTP_429 = 10
BLOCK_ERROR_PROXY = True

class ChunkDownloader():

	def __init__(self, id, cursor):
		self.id = id
		self.fatal_error = False
		self.cursor = cursor
		self.chunk_writer = cursor.chunk_writer
		self.proxy_manager = cursor.proxy_manager
		self.url = self.chunk_writer.cursor._file.url
		self.proxy = None
		self.exit = False
		self.error_509_aviso = False


	def run(self):

		logger.info("ChunkDownloader [%d] HELLO!" % self.id)

		error = False

		error509 = False

		proxy_error = False

		offset = -1

		while not self.chunk_writer.exit and not self.exit:

			try:

				while not self.chunk_writer.exit and not self.exit and len(self.chunk_writer.queue) >= MAX_CHUNK_BUFFER_SIZE:
					logger.info("ChunkDownloader %d me duermo porque la cola está llena!" % self.id)
					with self.chunk_writer.cv_queue_full:
						self.chunk_writer.cv_queue_full.wait(1)

				if not self.chunk_writer.exit and not self.exit:

					if error509 or proxy_error or FORCE_PROXY_MODE:

						if not self.error_509_aviso:
							self.error_509_aviso = True
							self.proxy_manager.error_509(self.cursor._file._client)

						if BLOCK_ERROR_PROXY and self.proxy and (error509 or proxy_error):
							logger.info("ChunkDownloader[%d] bloqueando proxy %s" % (self.id, self.proxy))
							self.proxy_manager.block_proxy(self.proxy)

						self.proxy = self.proxy_manager.get_next_proxy()

						self.cursor.turbo()

						if not self.proxy:
							logger.info("ChunkDownloader[%d] NO QUEDAN PROXYS" % self.id)
							self.exit = True
							self.fatal_error = True
						else:
							logger.info("ChunkDownloader[%d] usando proxy %s" % (self.id, self.proxy))

					if offset<0 or not error:
						offset = self.chunk_writer.nextOffset()

					error = False

					error509 = False

					proxy_error = False

					if offset >= 0 and not self.exit:

						chunk = Chunk.Chunk(offset, self.chunk_writer.calculateChunkSize(offset))

						logger.info("ChunkDownloader[%d] leyendo CHUNK %d" % (self.id, offset))

						try:

							logger.info("ChunkDownloader[%d] leyendo %s" % (self.id, self.url+('/%d-%d' % (int(offset), int(offset)+chunk.size-1))))

							req = urllib.request.Request(self.url+('/%d-%d' % (int(offset), int(offset)+chunk.size-1)))

							if self.proxy:
								req.set_proxy(self.proxy, 'http')

							connection = urllib.request.urlopen(req, timeout=SOCKET_PROXY_TIMEOUT if self.proxy else SOCKET_TIMEOUT)

							bytes_read = 0

							chunk.data = bytearray()

							while bytes_read < chunk.size and not self.chunk_writer.exit and not self.exit:
								to_read = min(BLOCK_SIZE, chunk.size - bytes_read)

								try:
									chunk.data+=connection.read(to_read)
									bytes_read+=to_read
								except Exception:
									pass

							if not self.chunk_writer.exit and not self.exit:

								if len(chunk.data) != chunk.size:
									error = True
								else:
									self.chunk_writer.queue[chunk.offset]=chunk
									with self.chunk_writer.cv_new_element:
										self.chunk_writer.cv_new_element.notifyAll()

						except urllib.error.HTTPError as err:
							logger.info("ChunkDownloader[%d] HTTP ERROR %d" % (self.id, err.code))

							error = True

							if offset >= 0:
								self.chunk_writer.offset_rejected.put(offset)
								offset=-1

							if self.proxy:
								proxy_error = True
							
							if err.code == 509:
								error509 = True
							elif err.code == 403:
								self.url = self.chunk_writer.cursor._file.refreshMegaDownloadUrl()
							elif err.code == 429:
								logger.info("ChunkDownloader %d me pauso %d segundos por error 429!" % (self.id, PAUSE_HTTP_429))
								time.sleep(PAUSE_HTTP_429)
								
						except urllib.error.URLError as err:
							logger.info("ChunkDownloader[%d] URL ERROR" % (self.id))

							error = True

							if isinstance(err.reason, socket.timeout):
								logger.info("ChunkDownloader[%d] socket timeout" % self.id)

							if offset >= 0:
								self.chunk_writer.offset_rejected.put(offset)
								offset=-1

							if self.proxy:
								proxy_error = True
					else:
						logger.info("ChunkDownloader[%d] END OFFSET" % self.id)
						self.exit = True

			except Exception as e:
				logger.info("ChunkDownloader[%d] %s" % (self.id, str(e)))
				
				if offset >= 0:
					self.chunk_writer.offset_rejected.put(offset)
					offset=-1
				
				if self.proxy:
					proxy_error = True
				else:
					self.exit = True
					self.fatal_error = True

		if self.fatal_error:
			logger.info("ChunkDownloader [%d] FATAL ERROR" % self.id)
			self.cursor.stop_multi_download()

		logger.info("ChunkDownloader [%d] BYE BYE" % self.id)

