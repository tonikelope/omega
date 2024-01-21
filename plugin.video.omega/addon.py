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

TIMEOUT = 300

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.alfa/"

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

PROTECTED_OMEGA_FILES = ['channels/omega.py', 'channels/omega.json', 'servers/nei.py', 'servers/nei.json', 'resources/media/channels/banner/omega.png', 'resources/media/channels/thumb/omega.gif', 'resources/media/channels/thumb/omega.png']

def ajustesAvanzados():
    if os.path.exists(xbmcvfs.translatePath('special://userdata/advancedsettings.xml')):
        os.rename(xbmcvfs.translatePath('special://userdata/advancedsettings.xml'), xbmcvfs.translatePath('special://userdata/advancedsettings.xml')+"."+str(int(time.time()))+".bak")
    
    settings_xml = ET.ElementTree(ET.Element('advancedsettings'))

    cache = settings_xml.findall("cache")
    cache = ET.Element('cache')
    memorysize = ET.Element('memorysize')
    memorysize.text = '52428800'
    readfactor = ET.Element('readfactor')
    readfactor.text = '8'
    cache.append(memorysize)
    cache.append(readfactor)
    settings_xml.getroot().append(cache)

    network = settings_xml.findall("network")
    network = ET.Element('network')
    curlclienttimeout = ET.Element('curlclienttimeout')
    curlclienttimeout.text = str(TIMEOUT)
    network.append(curlclienttimeout)
    curllowspeedtime = ET.Element('curllowspeedtime')
    curllowspeedtime.text = str(TIMEOUT)
    network.append(curllowspeedtime)
    settings_xml.getroot().append(network)

    playlisttimeout = settings_xml.findall('playlisttimeout')
    playlisttimeout = ET.Element('playlisttimeout')
    playlisttimeout.text = str(TIMEOUT)
    settings_xml.getroot().append(playlisttimeout)

    settings_xml.write(xbmcvfs.translatePath('special://userdata/advancedsettings.xml'))


def restore_omega_files():
    for f in PROTECTED_OMEGA_FILES:
        try:
            urlretrieve(ALFA_URL + f, ALFA_PATH + f)
        except:
            pass
            

def favoritos():
    try:
        if os.path.exists(xbmcvfs.translatePath('special://userdata/favourites.xml')):
            favourites_xml = ET.parse(xbmcvfs.translatePath('special://userdata/favourites.xml'))
        else:
            favourites_xml = ET.ElementTree(ET.Element('favourites'))

        omega = favourites_xml.findall("favourite[@name='OMEGA']")

        if omega:
            for e in omega:
                favourites_xml.getroot().remove(e)

        with open(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/favourite.json'), 'r') as f:
            favourite = json.loads(f.read())

        favourite['fanart'] = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa' + favourite['fanart'])
        favourite['thumbnail'] = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa' + favourite['thumbnail'])
        omega = ET.Element('favourite', {'name': 'OMEGA', 'thumb': xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/resources/media/channels/thumb/omega.gif')})
        omega.text = 'ActivateWindow(10025,"plugin://plugin.video.alfa/?' + urllib.parse.quote(base64.b64encode(json.dumps(favourite).encode('utf-8')))  + '",return)'
        favourites_xml.getroot().append(omega)
        favourites_xml.write(xbmcvfs.translatePath('special://userdata/favourites.xml'))
    except:
        pass


if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed')):

    with open(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed'), 'w+') as f:
        pass

    restore_omega_files()

    ajustesAvanzados()
    
    favoritos()
    
    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), "ES NECESARIO [COLOR yellow][B]REINICIAR[/B][/COLOR] KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres [COLOR yellow][B]REINICIAR[/B][/COLOR] KODI ahora mismo?")

    if ret:
        xbmc.executebuiltin('RestartApp')
else:
    xbmcgui.Dialog().ok('OMEGA', 'PARA ENTRAR EN OMEGA UTILIZA EL [B]ICONO DE FAVORITOS (el de la estrella)[/B] O BIEN BUSCA OMEGA EN LA LISTA DE CANALES DE ALFA')