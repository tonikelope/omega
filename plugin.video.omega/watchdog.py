# -*- coding: utf-8 -*-
import hashlib
import os
import re
import sys
from urllib.request import urlretrieve
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

CHECK_OMEGA_ALFA_STUFF_INTEGRITY = True

MONITOR_TIME = 15

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.alfa/"

KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

PROTECTED_OMEGA_FILES = ['channels/omega.py', 'channels/omega.json', 'servers/nei.py', 'servers/nei.json', 'resources/media/channels/banner/omega.png', 'resources/media/channels/thumb/omega.gif', 'resources/media/channels/thumb/omega.png']

if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed')):
    xbmc.executebuiltin('RunAddon(plugin.video.omega)')

# CHECK OMEGA CHANNEL UPDATES

urlretrieve(ALFA_URL + 'channels/checksum.sha1', KODI_TEMP_PATH + 'omega_channel.sha1')

sha1_checksums = {}

with open(KODI_TEMP_PATH + 'omega_channel.sha1') as f:
    for line in f:
        strip_line = line.strip()
        if strip_line:
            parts = re.split(' +', line.strip())
            sha1_checksums[parts[1]] = parts[0]

updated = False

broken = False

for filename, checksum in sha1_checksums.items():
    if os.path.exists(ALFA_PATH + 'channels/' + filename):
        with open(ALFA_PATH + 'channels/' + filename, 'rb') as f:
            file_hash = hashlib.sha1(f.read()).hexdigest()

        if file_hash != checksum:
            updated = True
            break
    else:
        broken = True
        break

os.remove(KODI_TEMP_PATH + 'omega_channel.sha1')

if CHECK_OMEGA_ALFA_STUFF_INTEGRITY and updated:
    for f in PROTECTED_OMEGA_FILES:
        urlretrieve(ALFA_URL + f, ALFA_PATH + f)

    xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA actualizado!',
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)

elif CHECK_OMEGA_ALFA_STUFF_INTEGRITY and broken:
    for f in PROTECTED_OMEGA_FILES:
        urlretrieve(ALFA_URL + f, ALFA_PATH + f)

    xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA instalado/reparado!',
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)
    
elif CHECK_OMEGA_ALFA_STUFF_INTEGRITY is False:
    xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA ALTERADO PERO NO REPARADO!',
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)


# MONITORS SOME OMEGA FILE IS DELETED AND RE-DOWNLOAD IT
monitor = xbmc.Monitor()

while not monitor.abortRequested():
    updated = False

    for f in PROTECTED_OMEGA_FILES:
        if not os.path.exists(ALFA_PATH + f):
            urlretrieve(ALFA_URL + f, ALFA_PATH + f)
            updated = True

    if updated:
        xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA reparado!',os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)

    monitor.waitForAbort(MONITOR_TIME)