# -*- coding: utf-8 -*-

"""
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
                                 
"""

import base64
import json
import os
import xml.etree.ElementTree as ET
import sys
import time
import urllib.parse
import urllib.request
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

KODI_USERDATA_PATH = xbmcvfs.translatePath("special://userdata/")

ALFA_PATH = xbmcvfs.translatePath("special://home/addons/plugin.video.alfa/")

OMEGA_PATH = xbmcvfs.translatePath("special://home/addons/plugin.video.omega/")

CURL_TIMEOUT = 300

def ajustesAvanzados():
    if os.path.exists(KODI_USERDATA_PATH+'/advancedsettings.xml'):
        os.rename(KODI_USERDATA_PATH+'/advancedsettings.xml', KODI_USERDATA_PATH+'/advancedsettings.xml'+"."+str(int(time.time()))+".bak")
    
    settings_xml = ET.ElementTree(ET.Element('advancedsettings'))

    cache = settings_xml.findall("cache")
    cache = ET.Element('cache')
    memorysize = ET.Element('memorysize')
    memorysize.text = '67108864'
    readfactor = ET.Element('readfactor')
    readfactor.text = '6'
    cache.append(memorysize)
    cache.append(readfactor)
    settings_xml.getroot().append(cache)

    network = settings_xml.findall("network")
    network = ET.Element('network')
    curlclienttimeout = ET.Element('curlclienttimeout')
    curlclienttimeout.text = str(CURL_TIMEOUT)
    network.append(curlclienttimeout)
    curllowspeedtime = ET.Element('curllowspeedtime')
    curllowspeedtime.text = str(CURL_TIMEOUT)
    network.append(curllowspeedtime)
    settings_xml.getroot().append(network)

    playlisttimeout = settings_xml.findall('playlisttimeout')
    playlisttimeout = ET.Element('playlisttimeout')
    playlisttimeout.text = str(CURL_TIMEOUT)
    settings_xml.getroot().append(playlisttimeout)

    settings_xml.write(KODI_USERDATA_PATH+'/advancedsettings.xml')


def favoritos():
    try:
        if os.path.exists(KODI_USERDATA_PATH+'/favourites.xml'):
            favourites_xml = ET.parse(KODI_USERDATA_PATH+'/favourites.xml')
        else:
            favourites_xml = ET.ElementTree(ET.Element('favourites'))

        omega = favourites_xml.findall("favourite[@name='OMEGA']")

        if omega:
            for e in omega:
                favourites_xml.getroot().remove(e)

        with open(OMEGA_PATH+'/favourite.json', 'r') as f:
            favourite = json.loads(f.read())

        favourite['fanart'] = ALFA_PATH + favourite['fanart']
        favourite['thumbnail'] = ALFA_PATH + favourite['thumbnail']
        omega = ET.Element('favourite', {'name': 'OMEGA', 'thumb': ALFA_PATH + '/resources/media/channels/thumb/omega.gif'})
        omega.text = 'ActivateWindow(10025,"plugin://plugin.video.alfa/?' + urllib.parse.quote(base64.b64encode(json.dumps(favourite).encode('utf-8')))  + '",return)'
        favourites_xml.getroot().append(omega)
        favourites_xml.write(KODI_USERDATA_PATH+'/favourites.xml')
    except:
        pass


if not os.path.exists(OMEGA_PATH+'/installed'):

    with open(OMEGA_PATH+'/installed', 'w+') as f:
        pass

    ajustesAvanzados()
    
    favoritos()
    
    if xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), "ES NECESARIO [COLOR yellow][B]REINICIAR[/B][/COLOR] KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres [COLOR yellow][B]REINICIAR[/B][/COLOR] KODI ahora mismo?"):
        xbmc.executebuiltin('RestartApp')
else:
    xbmcgui.Dialog().ok('OMEGA', 'PARA ENTRAR EN [B]OMEGA[/B] UTILIZA EL [B]ICONO DE FAVORITOS (el de la estrella)[/B] O BIEN BUSCA OMEGA EN LA LISTA DE CANALES DE ALFA')