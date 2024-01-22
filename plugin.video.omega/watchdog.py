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
   
Servicio de KODI para verificar la integridad de diferentes ficheros de ALFA/OMEGA
y corregirlos si han sido borrados o modificados.

"""

import hashlib
import os
import re
import sys
from urllib.request import urlretrieve, urlcleanup
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

REPAIR_OMEGA_ALFA_STUFF_INTEGRITY = True

MONITOR_TIME = 300

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.alfa/"

OMEGA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.omega/"

KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

OMEGA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.omega/')

PROTECTED_ALFA_DIRS = ['', '/channels', '/servers', '/lib/megaserver']

ALFA_NON_CRITICAL_DIRS = ['/resources/media/channels/thumb', '/resources/media/channels/banner']

OMEGA_NON_CRITICAL_DIRS = ['/resources']


def restore_files(remote_dir, local_dir, sha1_checksums=None, replace=True):
    
    if not sha1_checksums:
        sha1_checksums = read_remote_checksums(remote_dir)

    urlcleanup()

    updated = False

    for filename, checksum in sha1_checksums.items():
        if replace or not os.path.exists(local_dir + "/" + filename):
            try:
                urlretrieve(remote_dir+"/"+filename, local_dir+"/"+filename)
                updated = True        
            except:
                pass    
    
    return updated



def read_remote_checksums(remote_dir):
    temp_path = KODI_TEMP_PATH+hashlib.sha1((remote_dir+"/checksum.sha1").encode('utf-8')).hexdigest()

    urlcleanup()

    urlretrieve(remote_dir+"/checksum.sha1", temp_path)

    sha1_checksums = {}

    with open(temp_path) as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    os.remove(temp_path)

    return sha1_checksums



def check_files_integrity(remote_dir, local_dir):
    sha1_checksums = read_remote_checksums(remote_dir)

    integrity_error = False

    for filename, checksum in sha1_checksums.items():
        if os.path.exists(local_dir + "/" + filename):
            with open(local_dir + "/" + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:
                integrity_error = True
                break
        else:
            integrity_error = True
            break

    return (integrity_error, sha1_checksums)



def check_integrity(repair=True, notify=True):

    integrity_error = False

    non_critical_updated = False

    for protected_dir in PROTECTED_ALFA_DIRS:
        integrity = check_files_integrity(ALFA_URL+protected_dir, ALFA_PATH+protected_dir)

        if integrity[0]:

            integrity_error = True
            
            if repair:
                restore_files(ALFA_URL+protected_dir, ALFA_PATH+protected_dir, integrity[1])
            elif notify:
                xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA ALTERADO! (NO se reparará)', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)
                break

    if repair:
        for non_critical_dir in ALFA_NON_CRITICAL_DIRS:
            if restore_files(ALFA_URL+non_critical_dir, ALFA_PATH+non_critical_dir, sha1_checksums=None, replace=False):
                non_critical_updated = True

        for non_critical_dir in OMEGA_NON_CRITICAL_DIRS:
            if restore_files(OMEGA_URL+non_critical_dir, OMEGA_PATH+non_critical_dir, sha1_checksums=None, replace=False):
                non_critical_updated = True

    if (integrity_error or non_critical_updated) and repair:
        xbmcgui.Dialog().notification('OMEGA', '¡Canal OMEGA actualizado/reparado!', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)
    elif not integrity_error and not non_critical_updated and notify:
        xbmcgui.Dialog().notification('OMEGA', 'La casa está limpia y aseada', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), 5000)



#First run after OMEGA install
if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed')):
    xbmc.executebuiltin('RunAddon(plugin.video.omega)')



# MONITORS OMEGA PROTECTED FILES
monitor = xbmc.Monitor()

i=0

while not monitor.abortRequested():
    
    pbar=None 

    try:
        if i==0:
            pbar = xbmcgui.DialogProgressBG()    
            pbar.create('OMEGA', 'Verificando integridad...')
            
        check_integrity(repair=REPAIR_OMEGA_ALFA_STUFF_INTEGRITY, notify=(i==0))
        
        i+=1
    except:
        pass

    if pbar:
        pbar.update(100)
        pbar.close()

    monitor.waitForAbort(MONITOR_TIME)