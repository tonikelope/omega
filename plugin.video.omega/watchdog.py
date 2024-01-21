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
   
Servicio de KODI para verificar en el arranque la integridad de diferentes ficheros de OMEGA
y corregirlos si han sido borrados o modificados.

"""

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

MONITOR_TIME = 300

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.alfa/"

KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

PROTECTED_OMEGA_FILES = ['patch.py', 'channels/omega.py', 'channels/omega.json', 'servers/nei.py', 'servers/nei.json', 'resources/media/channels/banner/omega.png', 'resources/media/channels/thumb/omega.gif', 'resources/media/channels/thumb/omega.png']


def restore_omega_files():
    for f in PROTECTED_OMEGA_FILES:
        try:
            urlretrieve(ALFA_URL + f, ALFA_PATH + f)
        except:
            pass


def check_protected_file_integrity(remote_file_path):
    temp_path = hashlib.sha1((ALFA_URL+remote_file_path+"/checksum.sha1").encode('utf-8')).hexdigest()

    urlretrieve(ALFA_URL+remote_file_path+"/checksum.sha1", temp_path)

    sha1_checksums = {}

    with open(temp_path) as f:
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

    os.remove(temp_path)

    return (updated, broken)



def check_omega_integrity(progress=True, no_action_msg=True):

    if progress:
        pbar = xbmcgui.DialogProgressBG()    
        pbar.create('OMEGA', 'Verificando integridad...')

    checks = ['', '/channels', '/servers']

    for c in checks:
        integrity = check_protected_file_integrity(c)

        if CHECK_OMEGA_ALFA_STUFF_INTEGRITY and (integrity[0] or integrity[1]):
            restore_omega_files()
            xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA actualizado!' if integrity[0] else '¡Canal OMEGA instalado/reparado!', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)
            break
        elif CHECK_OMEGA_ALFA_STUFF_INTEGRITY is False and (integrity[0] or integrity[1]) and no_action_msg:
            xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA ALTERADO! (NO se reparará)', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)
            break

    if progress:
        pbar.update(100)
        pbar.close()


#First run after OMEGA install
if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed')):
    xbmc.executebuiltin('RunAddon(plugin.video.omega)')

# MONITORS OMEGA PROTECTED FILES
monitor = xbmc.Monitor()

i=0

while not monitor.abortRequested():
    check_omega_integrity((i==0), (i==0))
    monitor.waitForAbort(MONITOR_TIME)
    i+=1
