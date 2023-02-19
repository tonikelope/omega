# -*- coding: utf-8 -*-
# tonikelope MULTI-THREAD para OMEGA

class Chunk():
	
	def __init__(self, offset, size):
		self.offset = offset
		self.size = size
		self.data = None
