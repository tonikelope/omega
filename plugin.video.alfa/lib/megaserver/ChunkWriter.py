# -*- coding: utf-8 -*-
# tonikelope MULTI-THREAD para OMEGA

import threading
import time
import queue
from . import Chunk
import os
from platformcode import logger


CHUNK_SIZE = 5*1024*1024 #COMPROMISO

class ChunkWriter():

	def __init__(self, cursor, pipe, start_offset, end_offset):
		self.cursor = cursor
		self.pipe = pipe
		self.start_offset = start_offset
		self.end_offset = end_offset
		self.queue = {}
		self.cv_queue_full = threading.Condition()
		self.cv_new_element = threading.Condition()
		self.bytes_written = start_offset
		self.exit = False
		self.next_offset_required = start_offset
		self.chunk_offset_lock = threading.Lock()
		self.offset_rejected = queue.Queue()


	def run(self):

		logger.info("ChunkWriter HELLO!")

		while not self.exit and self.bytes_written < self.end_offset:

			while not self.exit and self.bytes_written < self.end_offset and self.bytes_written in self.queue:

				current_chunk = self.queue.pop(self.bytes_written)

				try:
					os.write(self.pipe, current_chunk.data)

					logger.info("ChunkWriter chunk %d escrito"%current_chunk.offset)

					self.bytes_written+=current_chunk.size

					with self.cv_queue_full:
						self.cv_queue_full.notifyAll()

				except Exception as e:
					logger.info(str(e))

			if not self.exit and self.bytes_written < self.end_offset:

				logger.info("ChunkWriter me duermo hasta que haya chunks nuevos en la cola")

				with self.cv_new_element:
					self.cv_new_element.wait(1)

		self.exit = True

		logger.info("ChunkWriter BYE BYE")


	def nextOffset(self):
		
		try:
			next_offset = self.offset_rejected.get(False)
		except queue.Empty:
			self.chunk_offset_lock.acquire()

			next_offset = self.next_offset_required

			self.next_offset_required = self.next_offset_required + CHUNK_SIZE if self.next_offset_required + CHUNK_SIZE < self.end_offset else -1;

			self.chunk_offset_lock.release()

		return next_offset


	def calculateChunkSize(self, offset):
		return min(CHUNK_SIZE, self.end_offset - offset + 1) if offset <= self.end_offset else -1


