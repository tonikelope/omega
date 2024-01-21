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

PROTECTED_OMEGA_FILES = ['patch.py', 'channels/omega.py', 'channels/omega.json', 'servers/nei.py', 'servers/nei.json', 'resources/media/channels/banner/omega.png', 'resources/media/channels/thumb/omega.gif', 'resources/media/channels/thumb/omega.png']

if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed')):
    xbmc.executebuiltin('RunAddon(plugin.video.omega)')

def check_protected_file_integrity(remote_file_path, temp_sha1_path):
    urlretrieve(ALFA_URL+remote_file_path+"/checksum.sha1", temp_sha1_path)

    sha1_checksums = {}

    with open(temp_sha1_path) as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    updated = False

    broken = False

    for filename, checksum in sha1_checksums.items():
        if os.path.exists(ALFA_PATH + remote_file_path + "/" + filename):
            with open(ALFA_PATH + remote_file_path + "/" + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:
                updated = True
                break
        else:
            broken = True
            break

    os.remove(temp_sha1_path)

    return (updated, broken)

# CHECK OMEGA CHANNEL UPDATES

pbar = xbmcgui.DialogProgressBG()
            
pbar.create('OMEGA', 'Verificando integridad...')

alfa_patch_check = check_protected_file_integrity('', KODI_TEMP_PATH +'alfa_patch.sha1')

omega_check = check_protected_file_integrity('/channels', KODI_TEMP_PATH +'omega_channel.sha1')

if CHECK_OMEGA_ALFA_STUFF_INTEGRITY and (alfa_patch_check[0] or omega_check[0]):
    for f in PROTECTED_OMEGA_FILES:
        urlretrieve(ALFA_URL + f, ALFA_PATH + f)

    xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA actualizado!',
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)

elif CHECK_OMEGA_ALFA_STUFF_INTEGRITY and (alfa_patch_check[1] or omega_check[1]):
    for f in PROTECTED_OMEGA_FILES:
        urlretrieve(ALFA_URL + f, ALFA_PATH + f)

    xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA instalado/reparado!',
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)
    
elif CHECK_OMEGA_ALFA_STUFF_INTEGRITY is False:
    xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA ALTERADO PERO NO REPARADO!',
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)

pbar.update(100)

pbar.close()

# MONITORS SOME OMEGA FILE IS DELETED AND RE-DOWNLOAD IT
if CHECK_OMEGA_ALFA_STUFF_INTEGRITY:
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

