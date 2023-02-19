# -*- coding: utf-8 -*-
#Basado en la librería de MEGA para pelisalacarte que programó divadr y modificado por tonikelope para dar soporte a MEGACRYPTER

from .client import Client
from .server import Server
from .mega import Mega, RequestError
from .proxy import MegaProxyServer

__all__ = ['Client', 'Server', 'Mega', 'MegaProxyServer', 'RequestError']
