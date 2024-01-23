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
import urllib.request
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

REPAIR_OMEGA_ALFA_STUFF_INTEGRITY = True

MONITOR_TIME = 1800 #Al arrancar KODI y cada 30 minutos comprobamos

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.alfa/"

OMEGA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.omega/"

KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

OMEGA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.omega/')

PROTECTED_ALFA_DIRS = ['', '/channels', '/servers', '/lib/megaserver']

PROTECTED_OMEGA_DIRS = ['']

ALFA_NON_CRITICAL_DIRS = ['/resources/media/channels/thumb', '/resources/media/channels/banner']

OMEGA_NON_CRITICAL_DIRS = ['/resources']


def omega_version():
    return xbmcaddon.Addon().getAddonInfo('version')


def url_retrieve(url, file_path, cache=False):

    if not cache:
        urllib.request.urlcleanup()
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0'), ('Cache-Control', 'no-cache, no-store, must-revalidate'), ('Pragma', 'no-cache'), ('Expires', '0')]
        urllib.request.install_opener(opener)
    
    urllib.request.urlretrieve(url, file_path)


def omegaNotification(msg, timeout=5000):
    xbmcgui.Dialog().notification('OMEGA '+str(omega_version()), msg, os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), timeout)


def restore_files(remote_dir, local_dir, sha1_checksums=None, replace=True):
    
    if not sha1_checksums:
        sha1_checksums = read_remote_checksums(remote_dir)

    updated = False

    for filename, checksum in sha1_checksums.items():
        if replace or not os.path.exists(local_dir + "/" + filename):
            url_retrieve(remote_dir+"/"+filename, local_dir+"/"+filename)
            updated = True        
  
    return updated



def read_remote_checksums(remote_dir):
    temp_path = KODI_TEMP_PATH+hashlib.sha1((remote_dir+"/checksum.sha1").encode('utf-8')).hexdigest()

    url_retrieve(remote_dir+"/checksum.sha1", temp_path)

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
                restore_files(ALFA_URL+protected_dir, ALFA_PATH+protected_dir, sha1_checksums=integrity[1])
            elif notify:
                omegaNotification('¡Canal OMEGA ALTERADO! (NO se reparará)')
                break

    for protected_dir in PROTECTED_OMEGA_DIRS:
        integrity = check_files_integrity(OMEGA_URL+protected_dir, OMEGA_PATH+protected_dir)

        if integrity[0]:

            integrity_error = True
            
            if repair:
                restore_files(OMEGA_URL+protected_dir, OMEGA_PATH+protected_dir, sha1_checksums=integrity[1])
            elif notify:
                omegaNotification('¡Canal OMEGA ALTERADO! (NO se reparará)')
                break

    if repair:
        for non_critical_dir in ALFA_NON_CRITICAL_DIRS:
            if restore_files(ALFA_URL+non_critical_dir, ALFA_PATH+non_critical_dir, sha1_checksums=None, replace=False):
                non_critical_updated = True

        for non_critical_dir in OMEGA_NON_CRITICAL_DIRS:
            if restore_files(OMEGA_URL+non_critical_dir, OMEGA_PATH+non_critical_dir, sha1_checksums=None, replace=False):
                non_critical_updated = True

    if (integrity_error or non_critical_updated) and repair:
        omegaNotification('¡Canal OMEGA actualizado/reparado!')
    elif not integrity_error and not non_critical_updated and notify:
        omegaNotification('La casa está limpia y aseada')



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