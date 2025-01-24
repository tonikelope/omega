# -*- coding: utf-8 -*-

r"""
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
import time

REPAIR_OMEGA_ALFA_STUFF_INTEGRITY = True

INTEGRITY_AUTO_CHECK_TIME = 3600 #Al arrancar KODI y cada 60 minutos comprobamos

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/refs/heads/main/plugin.video.alfa/"

OMEGA_URL = "https://raw.githubusercontent.com/tonikelope/omega/refs/heads/main/plugin.video.omega/"

KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

OMEGA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.omega/')

CRITICAL_ALFA_DIRS = ['', '/channels', '/servers', '/lib/megaserver']

CRITICAL_OMEGA_DIRS = ['']

NON_CRITICAL_ALFA_DIRS = ['/resources/media/channels/thumb', '/resources/media/channels/banner']

NON_CRITICAL_OMEGA_DIRS = ['/resources']

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

MAX_URL_RETRIEVE_ERROR = 5



def wait_for_dir(local_dir):
    monitor = xbmc.Monitor()

    while not monitor.abortRequested() and not os.path.exists(local_dir):
        monitor.waitForAbort(1)


def omega_version():
    return xbmcaddon.Addon().getAddonInfo('version')


def url_retrieve(url, file_path):
    ok = False

    i = 0

    while not ok and i < MAX_URL_RETRIEVE_ERROR:
        i+=1

        try:
            opener = urllib.request.build_opener()
            
            opener.addheaders = [('User-Agent', USER_AGENT)]
        
            urllib.request.install_opener(opener)
            
            urllib.request.urlretrieve(url, file_path)
            
            ok = True
        except Exception as ex:
            if i==MAX_URL_RETRIEVE_ERROR:
                raise ex


def omegaNotification(msg, timeout=5000):
    xbmcgui.Dialog().notification('OMEGA', msg, os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'icon.gif'), timeout)


def restore_files(pbar, remote_dir, local_dir, sha1_checksums=None, replace=True):

    wait_for_dir(local_dir)

    if not sha1_checksums:
        pbar.update(message="Descargando checksums...")
        sha1_checksums = read_remote_checksums(remote_dir)

    updated = False

    for filename, checksum in sha1_checksums.items():
        pbar.update(message="Comprobando "+filename+"...")
        if not os.path.exists(local_dir + "/" + filename):
            url_retrieve(remote_dir+"/"+filename, local_dir+"/"+filename)
            updated = True
        elif replace:
            with open(local_dir + "/" + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:
                url_retrieve(remote_dir+"/"+filename, local_dir+"/"+filename)
                updated = True
  
    return updated


def read_remote_checksums(remote_dir):
    
    temp_path = KODI_TEMP_PATH+hashlib.sha1((remote_dir+"/checksum.sha1").encode('utf-8')).hexdigest()+"_"+str(int(time.time()*1000))

    url_retrieve(remote_dir+"/checksum.sha1?"+str(int(time.time()*1000)), temp_path)

    sha1_checksums = {}

    with open(temp_path) as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    os.remove(temp_path)

    return sha1_checksums


def check_files_integrity(pbar, remote_dir, local_dir):
    
    wait_for_dir(local_dir)

    pbar.update(message="Descargando checksums...")
    sha1_checksums = read_remote_checksums(remote_dir)

    integrity_error = False

    for filename, checksum in sha1_checksums.items():
        pbar.update(message="Comprobando "+filename+"...")
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


def check_integrity(progress_bar=None, repair=True, notify=True):

    alfa_integrity_error = False

    omega_integrity_error = False

    non_critical_updated = False

    pbar_counter = 0

    total_pbar = len(CRITICAL_ALFA_DIRS) + len(CRITICAL_OMEGA_DIRS) + ((len(NON_CRITICAL_ALFA_DIRS) + len(NON_CRITICAL_OMEGA_DIRS)) if repair else 0)

    pbar_increment = round(100/total_pbar)

    for protected_dir in CRITICAL_ALFA_DIRS:
        integrity = check_files_integrity(progress_bar, ALFA_URL+protected_dir, ALFA_PATH+protected_dir)

        if integrity[0]:

            alfa_integrity_error = True
            
            if repair:
                restore_files(progress_bar, ALFA_URL+protected_dir, ALFA_PATH+protected_dir, sha1_checksums=integrity[1])
                
                if progress_bar:
                    pbar_counter+=min(pbar_increment, 100-pbar_counter)
                    progress_bar.update(pbar_counter)
            elif notify:
                omegaNotification('¡OMEGA ALTERADO! (NO SE REPARARÁ)')
                break

    for protected_dir in CRITICAL_OMEGA_DIRS:
        integrity = check_files_integrity(progress_bar, OMEGA_URL+protected_dir, OMEGA_PATH+protected_dir)

        if integrity[0]:

            omega_integrity_error = True
            
            if repair:
                restore_files(progress_bar, OMEGA_URL+protected_dir, OMEGA_PATH+protected_dir, sha1_checksums=integrity[1])

                if progress_bar:
                    pbar_counter+=min(pbar_increment, 100-pbar_counter)
                    progress_bar.update(pbar_counter)
            elif notify:
                omegaNotification('¡OMEGA ALTERADO! (NO SE REPARARÁ)')
                break

    if repair:
        for non_critical_dir in NON_CRITICAL_ALFA_DIRS:
            if restore_files(progress_bar, ALFA_URL+non_critical_dir, ALFA_PATH+non_critical_dir, sha1_checksums=None, replace=False):
                if progress_bar:
                    pbar_counter+=min(pbar_increment, 100-pbar_counter)
                    progress_bar.update(pbar_counter)
                
                non_critical_updated = True

        for non_critical_dir in NON_CRITICAL_OMEGA_DIRS:
            if restore_files(progress_bar, OMEGA_URL+non_critical_dir, OMEGA_PATH+non_critical_dir, sha1_checksums=None, replace=False):
                if progress_bar:
                    pbar_counter+=min(pbar_increment, 100-pbar_counter)
                    progress_bar.update(pbar_counter)

                non_critical_updated = True

    if (alfa_integrity_error or omega_integrity_error or non_critical_updated) and repair:
        omegaNotification('¡OMEGA actualizado/reparado!')
    elif not alfa_integrity_error and not omega_integrity_error and not non_critical_updated and notify:
        omegaNotification('La casa está limpia y aseada')

    if REPAIR_OMEGA_ALFA_STUFF_INTEGRITY and omega_integrity_error and xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), "ES NECESARIO [COLOR yellow][B]REINICIAR[/B][/COLOR] KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres [COLOR yellow][B]REINICIAR[/B][/COLOR] KODI ahora mismo?"):
        xbmc.executebuiltin('RestartApp')
        

#First run after OMEGA install
if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.omega/installed')):
    xbmc.executebuiltin('RunAddon(plugin.video.omega)')



# MONITORS ALFA/OMEGA
monitor = xbmc.Monitor()

auto_checked = False
t=0

while not monitor.abortRequested():

    verify_now = (not os.path.exists(ALFA_PATH+"/channels/omega.py") or t==INTEGRITY_AUTO_CHECK_TIME or not auto_checked)

    if verify_now:
        pbar=None

        try:
            if not auto_checked or t!=INTEGRITY_AUTO_CHECK_TIME:
                pbar = xbmcgui.DialogProgressBG()    
                pbar.create('[B]OMEGA WATCHDOG[/B]', '[B]VERIFICANDO INTEGRIDAD...[/B]')
                auto_checked = True
               
            check_integrity(progress_bar=pbar, repair=REPAIR_OMEGA_ALFA_STUFF_INTEGRITY, notify=(pbar!=None))
            
        except Exception as ex:
            omegaNotification("¡ERROR AL VERIFICAR INTEGRIDAD!")
            pass

        if pbar:
            pbar.update(100)
            pbar.close()

        t=0

    else:
        t+=1

    monitor.waitForAbort(1)