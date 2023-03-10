# -*- coding: utf-8 -*-
# https://github.com/tonikelope/omega

import base64
import hashlib
import json
import math
import os
import pickle
import random
import re
import socket
import xml.etree.ElementTree as ET
import urllib.request, urllib.error, urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import html
import time
import shutil
from core.item import Item
from core import httptools, scrapertools, tmdb
from platformcode import config, logger, platformtools, updater
from collections import OrderedDict
from datetime import datetime

CHECK_STUFF_INTEGRITY = True

OMEGA_VERSION = "3.63"

config.set_setting("unify", "false")

OMEGA_LOGIN = config.get_setting("omega_user", "omega")

OMEGA_PASSWORD = config.get_setting("omega_password", "omega")

USE_MEGA_PREMIUM = config.get_setting("omega_mega_premium", "omega")

MEGA_EMAIL = config.get_setting("omega_mega_email", "omega")

MEGA_PASSWORD = config.get_setting("omega_mega_password", "omega")

USE_MC_REVERSE = config.get_setting("omega_use_mc_reverse", "omega")

KODI_TEMP_PATH = xbmcvfs.translatePath('special://temp/')

KODI_USERDATA_PATH = xbmcvfs.translatePath('special://userdata/')

KODI_NEI_HISTORY_PATH = KODI_USERDATA_PATH + 'kodi_nei_history'

KODI_NEI_BLACKLIST_ITEM_PATH = KODI_USERDATA_PATH + 'kodi_nei_item_blacklist'

KODI_NEI_CUSTOM_TITLES_PATH = KODI_USERDATA_PATH + 'kodi_nei_custom_titles'

BIBLIOTAKU_TOPIC_ID='35243'

BIBLIOTAKU_URL='https://noestasinvitado.com/recopilatorios/la-bibliotaku/'

BIBLIOTAKU_PELIS_URL=['https://noestasinvitado.com/msg.php?m=114128']

BIBLIOTAKU_SERIES_URL=['https://noestasinvitado.com/msg.php?m=114127']

BIBLIOTAKU_ANIME_URL=['https://noestasinvitado.com/msg.php?m=113529', 'https://noestasinvitado.com/msg.php?m=123119', 'https://noestasinvitado.com/msg.php?m=123120', 'https://noestasinvitado.com/msg.php?m=123121']

BIBLIOTAKU_DONGHUA_URL=['https://noestasinvitado.com/msg.php?m=113531']

OMEGA_RESOURCES_URL = "https://noestasinvitado.com/omega_resources/"

OMEGA_MENSAJES_FORO_URL = 'https://noestasinvitado.com/omega_foro.php?idtopic='

GITHUB_BASE_URL = "https://raw.githubusercontent.com/tonikelope/omega/master/"

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/omega/main/plugin.video.alfa/"

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

OMEGA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.omega/')

DEFAULT_HTTP_TIMEOUT = 120 #Para no pillarnos los dedos al generar enlaces Megacrypter

ADVANCED_SETTINGS_TIMEOUT = 120

FORO_ITEMS_RETRY = 3

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36"}

FOROS_FINALES_NEI = ["ultrahd", "alta-definicion-(hd)", "definicion-estandar-(sd)", "ultra-definicion-(ultra-hd)", "alta-definicion-(hd)-52", "definicion-estandar-(sd)-51"]

try:
    HISTORY = [line.rstrip('\n') for line in open(KODI_NEI_HISTORY_PATH)]
except:
    HISTORY = []

try:
    ITEM_BLACKLIST = [line.rstrip('\n') for line in open(KODI_NEI_BLACKLIST_ITEM_PATH)]
except:
    ITEM_BLACKLIST = []

try:
    lines = [line.rstrip('\n') for line in open(KODI_NEI_CUSTOM_TITLES_PATH)]

    CUSTOM_TITLES = {}

    for l in lines:
        parts = l.split('#')
        if len(parts) == 2:
            CUSTOM_TITLES[parts[0]] = base64.b64decode(parts[1]).decode('utf-8')
except:
    CUSTOM_TITLES = {}

if USE_MC_REVERSE:

    try:

        MC_REVERSE_PORT = int(config.get_setting("omega_mc_reverse_port", "omega"))

        if 1024 <= MC_REVERSE_PORT <= 65535:
            MC_REVERSE_PASS = hashlib.sha1(OMEGA_LOGIN.encode('utf-8')).hexdigest()

            MC_REVERSE_DATA = str(MC_REVERSE_PORT) + ":" + base64.b64encode(
                ("omega:" + MC_REVERSE_PASS).encode('utf-8')).decode('utf-8')

    except ValueError:
        pass

else:
    MC_REVERSE_DATA = ''
    MC_REVERSE_PORT = None
    MC_REVERSE_PASS = None

UPLOADERS_BLACKLIST = [
    x.strip() for x in config.get_setting(
        "omega_blacklist_uploaders",
        "omega").split(',')] if config.get_setting(
    "omega_blacklist_uploaders",
    "omega") else []

TITLES_BLACKLIST = [
    x.strip() for x in config.get_setting(
        "omega_blacklist_titles",
        "omega").split(',')] if config.get_setting(
    "omega_blacklist_titles",
    "omega") else []


def forceView(mode):
    skin = xbmc.getSkinDir()

    logger.info("channels.omega "+skin)

    if mode in VIEW_MODES and skin in VIEW_MODES[mode]:
        xbmc.executebuiltin('Container.SetViewMode('+str(VIEW_MODES[mode][skin])+')')
        logger.info("channels.omega FORCE VIEW"+str(VIEW_MODES[mode][skin]))



def get_omega_resource_path(resource):

    if os.path.exists(xbmcvfs.translatePath("special://home/addons/plugin.video.omega/resources/"+resource)):
        return "special://home/addons/plugin.video.omega/resources/"+resource
    else:
        return OMEGA_RESOURCES_URL+resource

def login():
    logger.info("channels.omega login")

    httptools.downloadpage("https://noestasinvitado.com/login/", timeout=DEFAULT_HTTP_TIMEOUT)

    if OMEGA_LOGIN and OMEGA_PASSWORD:

        post = "user=" + OMEGA_LOGIN + "&passwrd=" + \
               OMEGA_PASSWORD + "&cookielength=-1"

        data = httptools.downloadpage(
            "https://noestasinvitado.com/login2/", post=post, timeout=DEFAULT_HTTP_TIMEOUT).data

        return data.find(OMEGA_LOGIN) != -1

    else:

        return false

def mega_login(verbose):
    mega_sid = ''

    if USE_MEGA_PREMIUM and MEGA_EMAIL and MEGA_PASSWORD:

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_mega_' + hashlib.sha1((MEGA_EMAIL + MEGA_PASSWORD).encode('utf-8')).hexdigest()

        login_ok = False

        pro_account = False

        if os.path.isfile(filename_hash):

            try:

                with open(filename_hash, "rb") as file:

                    mega = pickle.load(file)

                    pro_account = mega.is_pro_account()

                    login_ok = True

            except Exception as ex:
                logger.info("OMEGA MEGA LOGIN EXCEPTION")
                logger.info(ex)
                if os.path.isfile(filename_hash):
                    os.remove(filename_hash)

        if not login_ok:

            mega = Mega()

            try:

                with open(filename_hash, "wb") as file:

                    mega.login(MEGA_EMAIL, MEGA_PASSWORD)

                    pro_account = mega.is_pro_account()

                    pickle.dump(mega, file)

                    login_ok = True

            except Exception as ex:
                logger.info("OMEGA MEGA LOGIN EXCEPTION")
                logger.info(ex)
                if os.path.isfile(filename_hash):
                    os.remove(filename_hash)

        if login_ok:

            mega_sid = mega.sid

            login_msg = "LOGIN EN MEGA (free) OK!" if not pro_account else "LOGIN EN MEGA (PRO) OK!"

            logger.info("channels.omega "+login_msg+" "+MEGA_EMAIL)

            if verbose:
                xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', login_msg,
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'omega.gif'), 5000)
        else:

            logger.info("channels.omega ERROR AL HACER LOGIN EN MEGA: " + MEGA_EMAIL)

            if verbose:
                xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "ERROR AL HACER LOGIN EN MEGA",
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'omega.gif'), 5000)
    return mega_sid


def mainlist(item):
    logger.info("channels.omega mainlist")

    itemlist = []

    if not OMEGA_LOGIN:
        xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "ERROR AL HACER LOGIN EN NEI",
                                      os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                   'channels', 'thumb', 'omega.gif'), 5000)
        itemlist.append(
            Item(channel=item.channel,
                 title="[COLOR darkorange][B]Habilita tu cuenta de NEI en preferencias.[/B][/COLOR]",
                 action="settings_nei"))
    else:
        if login():
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "¡Bienvenido " + OMEGA_LOGIN + "!",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'omega.gif'), 5000)
            
            mega_login(True)
            load_mega_proxy('', MC_REVERSE_PORT, MC_REVERSE_PASS)
            itemlist.append(Item(channel=item.channel, title="[B]PELÍCULAS[/B]", viewcontent="movies", viewmode="list", section="PELÍCULAS", mode="movie", action="foro",
                                 url="https://noestasinvitado.com/peliculas/", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"))
            itemlist.append(Item(channel=item.channel, title="[B]SERIES[/B]", viewcontent="movies", viewmode="list",section="SERIES", mode="tvshow", action="foro",
                                 url="https://noestasinvitado.com/series/", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_tvshow.png"))
            itemlist.append(Item(channel=item.channel, title="Documetales", viewcontent="movies", viewmode="list", section="Documentales", mode="movie", action="foro",
                                 url="https://noestasinvitado.com/documentales/", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_documentary.png"))
            itemlist.append(Item(channel=item.channel, title="Vídeos deportivos", viewcontent="movies", viewmode="list", section="Vídeos deportivos", mode="movie", action="foro",
                                 url="https://noestasinvitado.com/deportes/", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_sport.png"))
            itemlist.append(Item(channel=item.channel, title="Anime", viewcontent="movies", viewmode="list", action="foro", section="Anime",
                                 url="https://noestasinvitado.com/anime/", mode="movie", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_anime.png"))
            itemlist.append(Item(channel=item.channel, title="Bibliotaku (Akantor)", viewcontent="movies", viewmode="list", action="bibliotaku", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.omega/resources/akantor.gif"))
            if not os.path.exists(KODI_USERDATA_PATH + 'omega_xxx'):
                itemlist.append(Item(channel=item.channel, title="\"Guarreridas\"", viewcontent="movies", viewmode="list", mode="movie", section="Guarreridas", action="foro",
                                     url="https://noestasinvitado.com/18-15/", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_adult.png", xxx=True))
            itemlist.append(Item(channel=item.channel, title="Listados alfabéticos", viewcontent="movies", viewmode="list", mode="movie", section="Listados", action="indices",
                                 url="https://noestasinvitado.com/indices/", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_movie_az.png"))
            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR darkorange][B]Buscar en OMEGA[/B][/COLOR]",
                    action="search", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", viewcontent="movies", viewmode="poster", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_search.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]Preferencias de OMEGA[/B]",
                    action="settings_nei", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]Borrar caché[/B]",
                    action="clean_cache", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR red][B]Borrar historial[/B][/COLOR]",
                    action="clean_history", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR red][B]Gestionar aportes ignorados[/B][/COLOR]", viewcontent="movies", viewmode="list",
                    action="clean_ignored_items", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Preferencias de ALFA",
                    action="settings_alfa", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Comprobar actualización de ALFA",
                    action="check_alfa_update", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_update.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Regenerar icono de FAVORITOS",
                    action="update_favourites", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_update.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Regenerar fichero de ajustes avanzados",
                    action="improve_streaming", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_update.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Regenerar miniaturas (todo KODI)",
                    action="thumbnail_refresh", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_update.png"))


            if not os.path.exists(KODI_USERDATA_PATH + 'omega_xxx'):
                itemlist.append(
                    Item(
                        channel=item.channel,
                        title="Desactivar contenido adulto",
                        action="xxx_off", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))
            else:
                itemlist.append(
                    Item(
                        channel=item.channel,
                        title="Reactivar contenido adulto",
                        action="xxx_on", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))
        else:
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "ERROR AL HACER LOGIN EN NEI",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'omega.gif'), 5000)
            itemlist.append(
                Item(channel=item.channel,
                     title="[COLOR red][B]ERROR: Usuario y/o password de NEI incorrectos (revisa las preferencias)[/B][/COLOR]",
                     action="", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

            itemlist.append(
                Item(channel=item.channel,
                     title="[COLOR darkorange][B]Habilita tu cuenta de NEI en preferencias.[/B][/COLOR]",
                     action="settings_nei", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

    return itemlist


def update_favourites(item):

    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), '¿SEGURO?')

    if ret:

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
            omega = ET.Element('favourite', {'name': 'OMEGA', 'thumb': xbmcvfs.translatePath(
                'special://home/addons/plugin.video.alfa/resources/media/channels/thumb/omega.gif')})
            omega.text = 'ActivateWindow(10025,"plugin://plugin.video.alfa/?' + urllib.parse.quote(base64.b64encode(json.dumps(favourite).encode('utf-8')))  + '",return)'
            favourites_xml.getroot().append(omega)
            favourites_xml.write(xbmcvfs.translatePath('special://userdata/favourites.xml'))

            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', 'Icono de favoritos regenerado', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

            ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), 'ES NECESARIO REINICIAR KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres reiniciar KODI ahora mismo?')

            if ret:
                xbmc.executebuiltin('RestartApp')

        except Exception as e:
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', 'ERROR al intentar regenerar el icono de favoritos', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)


def thumbnail_refresh(item):

    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), '¿SEGURO?')

    if ret:

        try:
            os.remove(xbmcvfs.translatePath('special://userdata/Database/Textures13.db'))

            shutil.rmtree(xbmcvfs.translatePath('special://userdata/Thumbnails'))

            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', 'Miniaturas regeneradas', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

            ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), 'ES NECESARIO REINICIAR KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres reiniciar KODI ahora mismo?')

            if ret:
                xbmc.executebuiltin('RestartApp')

        except Exception as e:
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', 'ERROR al intentar regenerar miniaturas', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

def improve_streaming(item):

    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), '¿SEGURO?')

    if ret:
    
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
        curlclienttimeout.text = str(ADVANCED_SETTINGS_TIMEOUT)
        network.append(curlclienttimeout)
        curllowspeedtime = ET.Element('curllowspeedtime')
        curllowspeedtime.text = str(ADVANCED_SETTINGS_TIMEOUT)
        network.append(curllowspeedtime)
        settings_xml.getroot().append(network)

        playlisttimeout = settings_xml.findall('playlisttimeout')
        playlisttimeout = ET.Element('playlisttimeout')
        playlisttimeout.text = str(ADVANCED_SETTINGS_TIMEOUT)
        settings_xml.getroot().append(playlisttimeout)

        settings_xml.write(xbmcvfs.translatePath('special://userdata/advancedsettings.xml'))

        xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "Ajustes avanzados regenerados", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

        ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), 'ES NECESARIO REINICIAR KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres reiniciar KODI ahora mismo?')

        if ret:
            xbmc.executebuiltin('RestartApp')


def settings_nei(item):
    platformtools.show_channel_settings()
    xbmc.executebuiltin('Container.Refresh')


def settings_alfa(item):
    config.open_settings()
    xbmc.executebuiltin('Container.Refresh')


def check_alfa_update(item):
    updater.check_addon_updates(True)


def xxx_off(item):
    if not os.path.exists(KODI_USERDATA_PATH + 'omega_xxx'):

        pass_hash = xbmcgui.Dialog().input(
            'Introduce una contraseña por si quieres reactivar el contenido adulto más tarde',
            type=xbmcgui.INPUT_PASSWORD)

        if pass_hash:
            f = open(KODI_USERDATA_PATH + 'omega_xxx', "w+")
            f.write(pass_hash)
            f.close()
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "Porno desactivado",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'omega.gif'), 5000)
            xbmc.executebuiltin('Container.Refresh')
    else:
        xbmc.executebuiltin('Container.Refresh')


def xxx_on(item):
    if os.path.exists(KODI_USERDATA_PATH + 'omega_xxx'):
        password = xbmcgui.Dialog().input('Introduce la contraseña', type=xbmcgui.INPUT_ALPHANUM,
                                          option=xbmcgui.ALPHANUM_HIDE_INPUT)

        if password:
            with open(KODI_USERDATA_PATH + 'omega_xxx', 'r') as f:
                file_pass = f.read()

            if hashlib.md5(password.encode('utf-8')).hexdigest() == file_pass:
                os.remove(KODI_USERDATA_PATH + 'omega_xxx')
                xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "Porno reactivado", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)
                xbmc.executebuiltin('Container.Refresh')
            else:
                xbmcgui.Dialog().ok('OMEGA: reactivar contenido adulto', 'Contraseña incorrecta')
    else:
        xbmc.executebuiltin('Container.Refresh')


def clean_cache(item):
    conta_files = 0

    for file in os.listdir(KODI_TEMP_PATH):
        if file.startswith("kodi_nei_"):
            os.remove(KODI_TEMP_PATH + file)
            conta_files = conta_files + 1

    xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')',
                                  "¡Caché borrada! (" + str(conta_files) + " archivos eliminados)",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'omega.gif'), 5000)
    platformtools.itemlist_refresh()


def clean_history(item):
    if xbmcgui.Dialog().yesno('OMEGA (' + OMEGA_VERSION + ')',
                              '¿Estás seguro de que quieres borrar tu historial de vídeos visionados?'):

        try:
            os.remove(KODI_NEI_HISTORY_PATH)
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "¡Historial borrado!",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'omega.gif'), 5000)
        except:
            pass


def clean_ignored_items(item):
    
    itemlist=[]

    for ignore in ITEM_BLACKLIST:
        itemlist.append(Item(channel=item.channel, ignore_title=ignore, title="[COLOR red][B]"+ignore.replace("https://noestasinvitado.com/", "")+"[/B][/COLOR]", action="remove_ignored_item"))

    return itemlist


def remove_ignored_item(item):
    if xbmcgui.Dialog().yesno('OMEGA (' + OMEGA_VERSION + ')', '¿Estás seguro de que quieres sacar este aporte de tus ignorados?'):

        try:
            if item.ignore_title in ITEM_BLACKLIST:
                ITEM_BLACKLIST.remove(item.ignore_title)

            os.remove(KODI_NEI_BLACKLIST_ITEM_PATH)
            
            with open(KODI_NEI_BLACKLIST_ITEM_PATH, "w+") as file:
                for ignore in ITEM_BLACKLIST:
                    file.write((ignore + "\n"))

            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "APORTE RESTAURADO",os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)
        except:
            pass


def isVideoFilename(filename):
    return re.compile(r'\.(mp4|mkv|wmv|m4v|mov|avi|flv|webm|flac|mka|m4a|aac|ogg)(\.part[0-9]+-[0-9]+)?$', re.IGNORECASE).search(filename.strip())


def bibliotaku_buscar(item, text):
    itemlist = []

    itemlist.extend(bibliotaku_pelis(Item(channel=item.channel, letter="TODO", viewcontent="movies", viewmode="poster", url_orig=BIBLIOTAKU_URL, id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (PELÍCULAS)", section="PELÍCULAS", mode="movie", action="bibliotaku_pelis",
                                 url='#'.join(BIBLIOTAKU_PELIS_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_peliculas.png")))

    itemlist.extend(bibliotaku_series(Item(channel=item.channel, letter="TODO", viewcontent="movies", viewmode="poster", url_orig=BIBLIOTAKU_URL, id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (SERIES)", section="SERIES", mode="tvshow", action="bibliotaku_series",
                         url='#'.join(BIBLIOTAKU_SERIES_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", tthumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_peliculas.png")))

    itemlist.extend(bibliotaku_series(Item(channel=item.channel, letter="TODO", viewcontent="movies", viewmode="poster", url_orig=BIBLIOTAKU_URL, id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (ANIME)", section="ANIME", mode="tvshow", action="bibliotaku_series",
                         url='#'.join(BIBLIOTAKU_ANIME_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_anime.png")))

    itemlist.extend(bibliotaku_series(Item(channel=item.channel, letter="TODO", viewcontent="movies", viewmode="poster", url_orig=BIBLIOTAKU_URL, id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (DONGHUA)", section="DONGHUA", mode="tvshow", action="bibliotaku_series",
                         url='#'.join(BIBLIOTAKU_DONGHUA_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_donghua.png")))

    search_itemlist = []

    for item in itemlist:
        if text.lower() in item.contentTitle.lower():
            item.title='[Bibliotaku] '+item.title
            search_itemlist.append(item)

    return search_itemlist
    

def bibliotaku(item):

    itemlist = []

    itemlist.append(Item(channel=item.channel, url_orig=BIBLIOTAKU_URL, viewcontent="movies", viewmode="poster", id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (PELÍCULAS)", section="PELÍCULAS", mode="movie", action="bibliotaku_index", real_action="bibliotaku_pelis",
                                 url='#'.join(BIBLIOTAKU_PELIS_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_peliculas.png"))
    itemlist.append(Item(channel=item.channel, url_orig=BIBLIOTAKU_URL, viewcontent="movies", viewmode="poster", id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (SERIES)", section="SERIES", mode="tvshow", action="bibliotaku_index", real_action="bibliotaku_series",
                         url='#'.join(BIBLIOTAKU_SERIES_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_series.png"))

    itemlist.append(Item(channel=item.channel, url_orig=BIBLIOTAKU_URL, viewcontent="movies", viewmode="poster", id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (ANIME)", section="ANIME", mode="tvshow", action="bibliotaku_index", real_action="bibliotaku_series",
                         url='#'.join(BIBLIOTAKU_ANIME_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_anime.png"))

    itemlist.append(Item(channel=item.channel, url_orig=BIBLIOTAKU_URL, viewcontent="movies", viewmode="poster", id_topic=BIBLIOTAKU_TOPIC_ID, title="Bibliotaku (DONGHUA)", section="DONGHUA", mode="tvshow", action="bibliotaku_index", real_action="bibliotaku_series",
                         url='#'.join(BIBLIOTAKU_DONGHUA_URL), fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="https://noestasinvitado.com/bibliotaku/bibliotaku_donghua.png"))

    itemlist.append(
                Item(
                    channel=item.channel,
                    search_section="bibliotaku",
                    viewcontent="movies", viewmode="poster",
                    title="[COLOR darkorange][B]Buscar en la Bibliotaku[/B][/COLOR]",
                    action="search", fanart="special://home/addons/plugin.video.omega/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_search.png"))

    return itemlist


def bibliotaku_index(item):
    
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
               'U', 'V', 'W', 'X', 'Y', 'Z', '0-9', 'TODO']

    itemlist = []

    start = 1

    for letter in letters:
        itemlist.append(Item(channel=item.channel, id_topic=item.id_topic, letter=letter, thumbnail="https://noestasinvitado.com/bibliotaku/letras/"+letter.lower()+".png" if item.letter !="TODO" else "", viewcontent=item.viewcontent, viewmode=item.viewmode, content_type=item.content_type, cat=item.cat, mode=item.mode, title="%s [B]([COLOR darkorange]%s[/COLOR])[/B]" % (item.title, letter), action=item.real_action, url=item.url))
        start = start + 1

    return itemlist


def bibliotaku_series(item):
    
    data = ""

    for u in item.url.split('#'):

        json_response = json.loads(httptools.downloadpage(u, timeout=DEFAULT_HTTP_TIMEOUT).data.encode().decode('utf-8-sig'))

        if 'error' in json_response or not 'body' in json_response:
            return None

        data+=json_response['body']

    data = re.sub('[–—]', '-', html.unescape(data))

    data = re.sub('[- ]*?(T|S) *?[0-9U]+[- ]*', ' ', data)
    
    data = re.sub(' *?-+ *?[Tt]emporadas?[^-]+-+ *?', ' ', data)

    data = re.sub(' AC3', ' ', data)

    patron = r'\[b\](.*?)\[\/b\].*?LINKS\[.*?\[url_mc\]([0-9]+)'

    itemlist = []

    matches = re.compile(patron, re.DOTALL|re.IGNORECASE).findall(data)

    series = {}

    letter_pattern=re.compile('^['+item.letter+']') if item.letter!="TODO" else None

    for rawscrapedtitle, mc_id in matches:

        scrapedtitle = parseScrapedTitle(rawscrapedtitle)

        parsed_title = parse_title(scrapedtitle)

        if not letter_pattern or re.search(letter_pattern, parsed_title['title']):

            if parsed_title['title'] in series:
                series[parsed_title['title']].append(mc_id)
            else:
                series[parsed_title['title']]=[mc_id]

                thumbnail = item.thumbnail

                content_serie_name = ""

                content_title = cleanContentTitle(parsed_title['title'])

                content_type = "movie" if scrapedtitle.endswith("*") else "tvshow"

                content_serie_name = "" if content_type=="movie" else content_title

                info_labels = {'year': parsed_title['year']}

                quality = parsed_title['quality']

                title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "") + (" [" + quality + "]" if quality else "")+" ##*NOTA*## (Akantor)"

                ignore_title = item.url+parsed_title['title']+("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "")+("[" + quality + "]" if quality else "")+"bibliotaku_series"

                if ignore_title not in ITEM_BLACKLIST:
                    itemlist.append(Item(channel=item.channel, parsed_title=parsed_title['title'], scraped_title=rawscrapedtitle, ignore_title=ignore_title, url_orig=item.url_orig, viewcontent="movies", viewmode="list", id_topic=item.id_topic, parent_title=item.parent_title, mode=item.mode, thumbnail=thumbnail, section=item.section, action="bibliotaku_series_temporadas", title=title, url=item.url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader="Akantor"))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:

        i.mc_group_id = series[i.parsed_title]

        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def bibliotaku_series_temporadas(item):

    itemlist = []

    if len(item.mc_group_id) == 1:
        item.infoLabels['season']=1

        item.mc_group_id = item.mc_group_id[0]

        itemlist = bibliotaku_series_megacrypter(item)

        itemlist.append(Item(channel=item.channel, title="PERSONALIZAR TÍTULO", action="customize_title", url="", scraped_title=item.scraped_title, ignore_title=item.ignore_title, thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

        itemlist.append(Item(channel=item.channel, title="[COLOR red][B]IGNORAR ESTE APORTE[/B][/COLOR]", action="ignore_item", ignore_confirmation=True, ignore_title=item.ignore_title, url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

    else:
        
        i = 1
        
        for mc_id in item.mc_group_id:
            infoLabels=item.infoLabels

            infoLabels['season']=i
            
            itemlist.append(Item(channel=item.channel, url_orig=item.url_orig, viewcontent="movies", viewmode="list", id_topic=item.id_topic, action="bibliotaku_series_megacrypter",
                                 title='[' + str(i) + '/' + str(len(item.mc_group_id)) + '] ' + item.title, url=item.url,
                                 mc_group_id=mc_id, infoLabels=infoLabels, mode=item.mode))

            i = i + 1

        if len(itemlist)>0:
            itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", viewcontent="movies", viewmode="list", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))

            if item.id_topic:
                itemlist.append(Item(channel=item.channel, scraped_title=item.scraped_title, ignore_title=item.ignore_title, url_orig=item.url_orig, id_topic=item.id_topic, url=item.url, viewcontent="movies", viewmode="list", title="[B][COLOR lightgrey]MENSAJES DEL FORO[/COLOR][/B]", contentPlot="[I]Mensajes sobre: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leerMensajesHiloForo", thumbnail='https://noestasinvitado.com/logonegro2.png'))   

            itemlist.append(Item(channel=item.channel, title="PERSONALIZAR TÍTULO", action="customize_title", url="", scraped_title=item.scraped_title, ignore_title=item.ignore_title, thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(Item(channel=item.channel, title="[COLOR red][B]IGNORAR ESTE APORTE[/B][/COLOR]", action="ignore_item", ignore_confirmation=True, ignore_title=item.ignore_title, url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def bibliotaku_series_megacrypter(item):

    itemlist = get_video_mega_links_group(Item(channel=item.channel, scraped_title=item.scraped_title, ignore_title=item.ignore_title, url_orig=item.url_orig, viewcontent="movies", viewmode="list", id_topic=item.id_topic, mode=item.mode, action='', title='', url=item.url, mc_group_id=item.mc_group_id, infoLabels=item.infoLabels))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def bibliotaku_pelis(item):

    data = ""

    for u in item.url.split('#'):

        json_response = json.loads(httptools.downloadpage(u, timeout=DEFAULT_HTTP_TIMEOUT).data.encode().decode('utf-8-sig'))

        if 'error' in json_response or not 'body' in json_response:
            return None

        data+=json_response['body']

    patron = r'\[b\](.*?)\[\/b\].*?LINKS\[.*?\[url_mc\]([0-9]+)'

    itemlist = []

    matches = re.compile(patron, re.DOTALL|re.IGNORECASE).findall(data)

    letter_pattern=re.compile('^['+item.letter+']') if item.letter!="TODO" else None

    for rawscrapedtitle, mc_id in matches:

        scrapedtitle = parseScrapedTitle(rawscrapedtitle)

        parsed_title = parse_title(scrapedtitle)

        if not letter_pattern or re.search(letter_pattern, parsed_title['title']):

            thumbnail = item.thumbnail

            content_serie_name = ""

            content_title = cleanContentTitle(parsed_title['title'])

            content_type = "tvshow" if scrapedtitle.endswith("#") else "movie"

            content_serie_name = content_title if content_type=="tvshow" else ""

            info_labels = {'year': parsed_title['year']}

            quality = parsed_title['quality']

            title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "") + (" [" + quality + "]" if quality else "")+" ##*NOTA*## (Akantor)"

            ignore_title = item.url+parsed_title['title']+("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "")+("[" + quality + "]" if quality else "")+"bibliotak_pelis"

            if ignore_title not in ITEM_BLACKLIST:
                itemlist.append(Item(channel=item.channel, scraped_title=rawscrapedtitle, ignore_title=ignore_title, url_orig=item.url_orig, viewcontent="movies", viewmode="list", id_topic=item.id_topic, mc_group_id=mc_id, parent_title=item.parent_title, mode=item.mode, thumbnail=thumbnail, section=item.section, action="bibliotaku_pelis_megacrypter", title=title, url=item.url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader="Akantor"))
            
    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:
        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def bibliotaku_pelis_megacrypter(item):
    infoLabels=item.infoLabels
            
    itemlist = get_video_mega_links_group(Item(channel=item.channel, scraped_title=item.scraped_title, ignore_title=item.ignore_title, url_orig=item.url_orig, viewcontent="movies", viewmode="list", id_topic=item.id_topic, mode=item.mode, action='', title='', url=item.url, mc_group_id=item.mc_group_id, infoLabels=infoLabels))

    itemlist.append(Item(channel=item.channel, title="PERSONALIZAR TÍTULO", action="customize_title", url="", scraped_title=item.scraped_title, ignore_title=item.ignore_title, thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

    itemlist.append(Item(channel=item.channel, title="[COLOR red][B]IGNORAR ESTE APORTE[/B][/COLOR]", action="ignore_item", ignore_confirmation=True, ignore_title=item.ignore_title, url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def escribirMensajeHiloForo(item):

    mensaje = xbmcgui.Dialog().input(item.contentPlot)

    if mensaje:

        url = item.url_orig if item.url_orig else item.url

        asunto = ('RESPUESTA OMEGA ('+cleanContentTitle(item.contentPlot)+')') if item.id_topic != BIBLIOTAKU_TOPIC_ID else ('RESPUESTA OMEGA BIBLIOTAKU ('+cleanContentTitle(item.contentPlot)+')')

        data = httptools.downloadpage(url, timeout=DEFAULT_HTTP_TIMEOUT).data

        m = re.compile(r'action="(http[^"]+action=post2)".*?input.*?"topic".*?"(.*?)".*?"last_msg".*?"(.*?)".*?name.*?"(.*?)".*?"(.*?)".*?"seqnum".*?"(.*?)"', re.DOTALL).search(data)

        res_post_url = m.group(1)

        res_post_data="topic="+m.group(2)+"&subject="+urllib.parse.quote(asunto)+"&icon=xx&from_qr=1&notify=0&not_approved=&goback=1&last_msg="+m.group(3)+"&"+m.group(4)+"="+m.group(5)+"&seqnum="+m.group(6)+"&message="+urllib.parse.quote(mensaje)+"&post=Publicar"

        httptools.downloadpage(res_post_url, post=res_post_data, timeout=DEFAULT_HTTP_TIMEOUT)

        xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', '¡MENSAJE ENVIADO! (es posible que tengas que refrescar la lista para verlo)', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

        xbmc.executebuiltin('Container.Refresh')


def darGraciasMensajeForo(item):
    httptools.downloadpage(re.sub(r'/msg.*?$','/',item.url)+ '?action=thankyou;msg='+item.msg['id_msg'], timeout=DEFAULT_HTTP_TIMEOUT)

    xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', 'HAS DADO LAS GRACIAS A: '+item.msg['nick'], os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)

    xbmc.executebuiltin('Container.Refresh')


def leerMensajesHiloForo(item):
    
    json_response = json.loads(httptools.downloadpage(OMEGA_MENSAJES_FORO_URL+str(item.id_topic), timeout=DEFAULT_HTTP_TIMEOUT).data.encode().decode('utf-8-sig'))

    logger.info(OMEGA_MENSAJES_FORO_URL+str(item.id_topic))

    logger.info(json_response)

    itemlist = []
    
    i=0
    
    for msg in json_response:
        if i>0:
            itemlist.append(Item(channel=item.channel, url=item.url, context=[{"title":"AGRADECER MENSAJE", "action": "darGraciasMensajeForo", "channel":"omega"}] if (OMEGA_LOGIN != msg['nick'] and not msg['thanks']) else None, contentPlot=item.contentPlot, fanart='https://noestasinvitado.com/logonegro2.png', thumbnail='https://noestasinvitado.com/logonegro2.png', action='cargarMensajeForo', msg=msg, title='[B][COLOR '+('lightgreen' if OMEGA_LOGIN == msg['nick'] else 'darkorange')+'][I]'+msg['nick']+':[/I][/COLOR][/B] '+html.unescape(clean_html_tags(msg['body'].replace('\n', ' ')))))

        i+=1

    itemlist.append(Item(channel=item.channel, url_orig=(item.url_orig if 'url_orig' in item else None), id_topic=item.id_topic, fanart='https://noestasinvitado.com/logonegro2.png', contentPlot=item.contentPlot, url=item.url, thumbnail='https://noestasinvitado.com/logonegro2.png', action='escribirMensajeHiloForo', title='[B]ESCRIBIR UN MENSAJE[/B]'))

    return itemlist


def cargarMensajeForo(item):
    fecha_mensaje = datetime.fromtimestamp(int(item.msg['time'])).strftime('%d/%m/%y %H:%M')
    xbmcgui.Dialog().textviewer('[B][I]'+item.msg['nick']+'[/I][/B]   ('+fecha_mensaje+')'+(' (Has dado las gracias por este mensaje)' if item.msg['thanks'] else ''), html.unescape(clean_html_tags(item.msg['body'].replace('<br>', "\n"))))


def sinEnlaces(item):
    xbmcgui.Dialog().ok('NO HAY ENLACES VÁLIDOS', 'NO SE HAN ENCONTRADO ENLACES VÁLIDOS DE MEGA/MEGACRYPTER/GDRIVE (o están comprimidos en ZIP, RAR, etc.)\n\nEscribe un mensaje al uploader en el foro para que lo revise cuando pueda.')


def parseScrapedTitle(scrapedtitle):

    sha1 = hashlib.sha1(scrapedtitle.encode('utf-8')).hexdigest()

    if sha1 in CUSTOM_TITLES.keys():
        logger.info("CUSTOM TITLE -> "+ CUSTOM_TITLES[sha1])
        return CUSTOM_TITLES[sha1]

    return scrapertools.htmlclean(scrapedtitle)


def foro(item):
    logger.info("channels.omega foro")

    if item.xxx and os.path.exists(KODI_USERDATA_PATH + 'omega_xxx'):
        return mainlist(item)

    itemlist = []

    data = httptools.downloadpage(item.url, timeout=DEFAULT_HTTP_TIMEOUT).data

    video_links = False

    final_item = False

    action=""

    if '<h3 class="catbg">Subforos</h3>' in data:
        # HAY SUBFOROS
        patron = r'< *?a +class *?= *?"subje(.*?)t" +href *?= *?"([^"]+)" +name *?= *?"[^"]+" *?>([^<]+)< *?/ *?a *?(>)'
        action = "foro"
    elif '"subject windowbg4"' in data:
        patron = r'< *?td +class *?= *?"subject windowbg4" *?>.*?< *?div *?>.*?< *?span +id *?= *?"([^"]+)" ?>.*?< *?a +href *?= *?"([^"]+)" *?>([^<]+)< *?/ *?a *?> *?< *?/ *?span *?>.*?"Ver +perfil +de +([^"]+)"'
        final_item = True
        action = "foro"
    else:
        video_links = True

        m = re.compile(r'action="http[^"]+action=post2".*?input.*?"topic".*?"(.*?)"', re.DOTALL).search(data)

        id_topic = m.group(1)

        item.id_topic = id_topic

        retry = 0

        while len(itemlist) == 0 and retry < FORO_ITEMS_RETRY:
            itemlist = find_video_mega_links(item, data) + find_video_gvideo_links(item, data)
            retry+=1

        if len(itemlist) == 0:

            itemlist.append(Item(channel=item.channel, fanart=item.fanart, title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES[/B][/COLOR]", action="sinEnlaces", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

            itemlist.append(Item(channel=item.channel, fanart=item.fanart, url_orig=item.url_orig, viewcontent="movies", viewmode="list", url=item.url, id_topic=item.id_topic, title="[B][COLOR lightgrey]MENSAJES DEL FORO[/COLOR][/B]", contentPlot="[I]Mensajes sobre: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leerMensajesHiloForo", thumbnail='https://noestasinvitado.com/logonegro2.png'))

            itemlist.append(Item(channel=item.channel, fanart=item.fanart, title="[COLOR red][B]IGNORAR ESTE APORTE[/B][/COLOR]", action="ignore_item", ignore_confirmation=False, ignore_title=item.ignore_title, url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

            if item.uploader:
                itemlist.append(Item(channel=item.channel, fanart=item.fanart, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
        else:
            itemlist.append(Item(channel=item.channel, fanart=item.fanart, title="PERSONALIZAR TÍTULO", action="customize_title", url="", scraped_title=item.scraped_title, ignore_title=item.ignore_title, thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(Item(channel=item.channel, fanart=item.fanart, title="[COLOR red][B]IGNORAR ESTE APORTE[/B][/COLOR]", action="ignore_item", ignore_confirmation=True, ignore_title=item.ignore_title, url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

    
    if not video_links:

        matches = re.compile(patron, re.DOTALL|re.IGNORECASE).findall(data)

        for scrapedmsg, scrapedurl, rawscrapedtitle, uploader in matches:

            url = urllib.parse.urljoin(item.url, scrapedurl)

            scrapedtitle = parseScrapedTitle(rawscrapedtitle)

            if uploader not in UPLOADERS_BLACKLIST and not any(word in scrapedtitle for word in TITLES_BLACKLIST) and not ("Filmografías" in scrapedtitle and action == "foro"):

                if uploader != '>':
                    title = scrapedtitle + " (" + uploader + ")"
                else:
                    title = scrapedtitle
                    uploader=""

                thumbnail = item.thumbnail

                content_serie_name = ""

                if final_item:

                    parsed_title = parse_title(scrapedtitle)

                    content_title = cleanContentTitle(parsed_title['title'])

                    if item.mode == "tvshow":
                        content_type = "movie" if scrapedtitle.endswith("*") else "tvshow"
                        content_serie_name = "" if content_type=="movie" else content_title
                    else:
                        content_type = "tvshow" if scrapedtitle.endswith("#") else "movie"
                        content_serie_name = content_title if content_type=="tvshow" else ""

                    info_labels = {'year': parsed_title['year']}

                    if 'Ultra HD ' in item.parent_title:
                        quality = 'UHD'
                    elif 'HD ' in item.parent_title:
                        quality = 'HD'
                    elif 'SD ' in item.parent_title:
                        quality = 'SD'
                    else:
                        quality = parsed_title['quality']

                    title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "") + ("[" + quality + "]" if quality else "")+" ##*NOTA*## (" + uploader + ")"
                    
                    ignore_title = url+parsed_title['title']+("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "")+("[" + quality + "]" if quality else "")+uploader

                    if ignore_title not in ITEM_BLACKLIST:
                        itemlist.append(Item(channel=item.channel, ignore_title=ignore_title, scraped_title=rawscrapedtitle, parent_title=item.parent_title, viewcontent="movies", viewmode="list", mode=item.mode, thumbnail=thumbnail, section=item.section, action=action, title=title, url=url, contentTitle=content_title, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

                else:
                    
                    if '(Ultra HD)' in item.title or '(Ultra HD)' in title:
                        if 'Español' in item.title or 'Español' in title:
                            thumbnail = get_omega_resource_path("series_uhd_es.png" if item.mode == "tvshow" else "pelis_uhd_es.png")
                        else:
                            thumbnail = get_omega_resource_path("series_uhd.png" if item.mode == "tvshow" else "pelis_uhd.png")
                    elif '(HD)' in item.title or '(HD)' in title:
                        if 'Español' in item.title or 'Español' in title:
                            thumbnail = get_omega_resource_path("series_hd_es.png" if item.mode == "tvshow" else "pelis_hd_es.png")
                        else:
                            thumbnail = get_omega_resource_path("series_hd.png" if item.mode == "tvshow" else "pelis_hd.png")

                    title = "["+ item.section + "] " + title
                    
                    item.parent_title = title.strip()

                    content_title = ""

                    content_type = ""

                    info_labels = []
                    
                    matches = re.compile(r"([^/]+)/$", re.DOTALL).search(url)

                    if matches.group(1) not in ('hd-espanol-59', 'hd-v-o-v-o-s-61', 'hd-animacion-62', 'sd-espanol-53', 'sd-v-o-v-o-s-54', 'sd-animacion', 'seriesovas-anime-espanol', 'seriesovas-anime-v-o-v-o-s'):
                        url = url + "?sort=first_post;desc"

                    logger.info("URL_FORO "+item.url)

                    id_foro = re.search("([^/]+)/*(?:\?[^/]+)?$", item.url).group(1)

                    logger.info("ID_FORO "+id_foro)

                    itemlist.append(Item(channel=item.channel, fanart=item.fanart, parent_title=item.parent_title, viewcontent="movies", viewmode=("poster" if id_foro in FOROS_FINALES_NEI else "list"), mode=item.mode, thumbnail=thumbnail, section=item.section, action=action, title=title, url=url, contentTitle=content_title, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

        patron = r'\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

        matches = re.compile(patron, re.DOTALL).search(data)

        if matches:
            url = matches.group(1)
            title = "[B]>> PÁGINA SIGUIENTE[/B]"
            itemlist.append(Item(channel=item.channel, fanart=item.fanart, parent_title=item.parent_title, viewcontent="movies", viewmode="poster", mode=item.mode, section=item.section, action="foro", title=title, url=url))

        tmdb.set_infoLabels_itemlist(itemlist, True)

        for i in itemlist:
            if i.infoLabels and 'rating' in i.infoLabels:

                if i.infoLabels['rating'] >= 7.0:
                    rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
                elif i.infoLabels['rating'] < 5.0:
                    rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
                else:
                    rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

                i.title = i.title.replace('##*NOTA*##', rating_text)
            else:
                i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def search(item, texto):

    if 'search_section' in item and item.search_section.lower()=='bibliotaku':
        return bibliotaku_buscar(item, texto)
    
    if texto != "":
        texto = texto.replace(" ", "+")

    post = "advanced=1&search=" + texto + "&searchtype=1&userspec=*&sort=relevance%7Cdesc&subject_only=1&" \
                                          "minage=0&maxage=9999&brd%5B6%5D=6&brd%5B227%5D=227&brd%5B229%5D" \
                                          "=229&brd%5B230%5D=230&brd%5B41%5D=41&brd%5B47%5D=47&brd%5B48%5D" \
                                          "=48&brd%5B42%5D=42&brd%5B44%5D=44&brd%5B46%5D=46&brd%5B218%5D=2" \
                                          "18&brd%5B225%5D=225&brd%5B7%5D=7&brd%5B52%5D=52&brd%5B59%5D=59&b" \
                                          "rd%5B61%5D=61&brd%5B62%5D=62&brd%5B51%5D=51&brd%5B53%5D=53&brd%5" \
                                          "B54%5D=54&brd%5B55%5D=55&brd%5B63%5D=63&brd%5B64%5D=64&brd%5B66%" \
                                          "5D=66&brd%5B67%5D=67&brd%5B65%5D=65&brd%5B68%5D=68&brd%5B69%5D=69" \
                                          "&brd%5B14%5D=14&brd%5B87%5D=87&brd%5B86%5D=86&brd%5B93%5D=93&brd" \
                                          "%5B83%5D=83&brd%5B89%5D=89&brd%5B85%5D=85&brd%5B82%5D=82&brd%5B9" \
                                          "1%5D=91&brd%5B90%5D=90&brd%5B92%5D=92&brd%5B88%5D=88&brd%5B84%5D" \
                                          "=84&brd%5B212%5D=212&brd%5B94%5D=94&brd%5B23%5D=23&submit=Buscar"

    data = httptools.downloadpage("https://noestasinvitado.com/search2/", post=post, timeout=DEFAULT_HTTP_TIMEOUT).data

    return search_parse(data, item)


def search_pag(item):
    data = httptools.downloadpage(item.url, timeout=DEFAULT_HTTP_TIMEOUT).data

    return search_parse(data, item)


def search_parse(data, item):
    itemlist=[]

    patron = r'<h5>[^<>]*<a[^<>]+>.*?</a>[^<>]*?<a +href="([^"]+)">(.*?)</a>[^<>]*</h5>[^<>]*<sp' \
             'an[^<>]*>.*?<a[^<>]*"Ver +perfil +de +([^"]+)"'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, rawscrapedtitle, uploader in matches:
        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = parseScrapedTitle(rawscrapedtitle)

        if uploader != '>':
            title = scrapedtitle + " (" + uploader + ")"
        else:
            title = scrapedtitle

        thumbnail = ""

        content_serie_name = ""

        parsed_title = parse_title(scrapedtitle)

        content_title = cleanContentTitle(parsed_title['title'])

        quality = ""

        section = ""

        if "/hd-espanol-235/" in url or "/hd-v-o-v-o-s-236/" in url or "/uhd-animacion/" in url:
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "UHD"
            section = "SERIES"
        elif "/hd-espanol-59/" in url or "/hd-v-o-v-o-s-61/" in url or "/hd-animacion-62/" in url:
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "HD"
            section = "SERIES"
        elif "/sd-espanol-53/" in url or "/sd-v-o-v-o-s-54/" in url or "/sd-animacion/" in url:
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "SD"
            section = "SERIES"

        if "/ultrahd-espanol/" in url or "/ultrahd-vo/" in url:
            content_type = "movie"
            quality = "UHD"
            section = "PELÍCULAS"
        elif "/hd-espanol/" in url or "/hd-v-o-v-o-s/" in url:
            content_type = "movie"
            quality = "HD"
            section = "PELÍCULAS"
        elif "/sd-espanol/" in url or "/sd-v-o-v-o-s/" in url or "/sd-animacion/" in url or "/3d-/" in url or "/cine-clasico-/" in url :
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "SD"
            section = "PELÍCULAS"
        elif not quality:
            content_type = "movie"
            quality = parsed_title['quality']

        info_labels = {'year': parsed_title['year']}

        title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "") +  (" [" + quality + "]" if quality else "")+" ##*NOTA*## (" + uploader + ")"

        ignore_title = url+("["+section+"] " if section else "")+parsed_title['title']+("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "")+("[" + quality + "]" if quality else "")+uploader

        if ignore_title not in ITEM_BLACKLIST:
            itemlist.append(Item(channel=item.channel, scraped_title=rawscrapedtitle, ignore_title=ignore_title, mode=content_type, viewcontent="movies", viewmode="list", thumbnail=thumbnail, section=item.section, action="foro", title=title, url=url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

    patron = r'\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

    matches = re.compile(patron, re.DOTALL).search(data)

    if matches:
        url = matches.group(1)
        title = "[B]>> PÁGINA SIGUIENTE[/B]"
        thumbnail = ""
        plot = ""
        itemlist.append(Item(channel=item.channel, action="search_pag", viewcontent="movies", viewmode="poster", title=title, url=url, thumbnail=item.thumbnail))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:
        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist



def indices(item):
    itemlist = []

    categories = ['Películas Ultra HD Español', 'Películas Ultra HD VO', 'Películas HD Español', 'Películas HD VO', 'Películas SD Español', 'Películas SD VO',
                  'Series Ultra HD Español', 'Series Ultra HD VO', 'Series HD Español', 'Series HD VO', 'Series SD Español', 'Series SD VO', 'Películas Anime Español',
                  'Películas Anime VO', 'Series Anime Español', 'Series Anime VO', 'Películas clásicas', 'Deportes',
                  'Películas XXX HD', 'Películas XXX SD', 'Vídeos XXX HD', 'Vídeos XXX SD']

    for cat in categories:

        thumbnail = ""

        if 'Ultra HD' in cat:
            if 'Español' in cat:
                thumbnail = get_omega_resource_path("series_uhd_es.png" if 'Series' in cat else "pelis_uhd_es.png")
            else:
                thumbnail = get_omega_resource_path("series_uhd.png" if 'Series' in cat else "pelis_uhd.png")
        elif 'HD' in cat:
            if 'Español' in cat:
                thumbnail = get_omega_resource_path("series_hd_es.png" if 'Series' in cat else "pelis_hd_es.png")
            else:
                thumbnail = get_omega_resource_path("series_hd.png" if 'Series' in cat else "pelis_hd.png")
        elif 'Series' in cat:
            thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_tvshow.png"
        else:
            thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"

        mode=""

        if 'Películas' in cat:
            mode = "movie"
        elif 'Series' in cat:
            mode="tvshow"
        else:
            thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"

        itemlist.append(Item(channel=item.channel, viewcontent="movies", viewmode="list", cat=cat, title=cat, mode=mode, action="gen_index", url="https://noestasinvitado.com/indices/", thumbnail=thumbnail))

    return itemlist


def gen_index(item):
    categories = {'Películas Ultra HD Español':229, 'Películas Ultra HD VO': 230, 'Películas HD Español': 47, 'Películas HD VO': 48, 'Películas SD Español': 44, 'Películas SD VO': 42,
                  'Series Ultra HD Español': 235, 'Series Ultra HD VO': 236, 'Series HD Español': 59, 'Series HD VO': 61, 'Series SD Español': 53, 'Series SD VO': 54,
                  'Películas Anime Español': 66, 'Películas Anime VO': 67, 'Series Anime Español': 68,
                  'Series Anime VO': 69, 'Películas clásicas': 218, 'Deportes': 23, 'Películas XXX HD': 182,
                  'Películas XXX SD': 183, 'Vídeos XXX HD': 185, 'Vídeos XXX SD': 186}

    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'Ñ', 'O', 'P', 'Q', 'R', 'S', 'T',
               'U', 'V', 'W', 'X', 'Y', 'Z', '0-9']

    itemlist = []

    content_type="tvshow" if "Series" in item.title else "movies"

    start = 1

    for letter in letters:
        itemlist.append(Item(channel=item.channel, viewcontent="movies", viewmode="poster", content_type = content_type, cat=item.cat, mode=item.mode, thumbnail=item.thumbnail, title="%s (Letra %s)" % (item.title, letter), action="indice_links",url="https://noestasinvitado.com/indices/?id=%d;start=%d" % (categories[item.title], start)))
        start = start + 1

    return itemlist


def romanToInt(s):
    roman = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000,'IV':4,'IX':9,'XL':40,'XC':90,'CD':400,'CM':900}
    i = 0
    num = 0
    
    while i < len(s):
        if i+1<len(s) and s[i:i+2] in roman:
            num+=roman[s[i:i+2]]
            i+=2
        else:
            num+=roman[s[i]]
            i+=1
    
    return num


def intToRoman(num):
  
    # Storing roman values of digits from 0-9
    # when placed at different places
    m = ["", "M", "MM", "MMM"]
    c = ["", "C", "CC", "CCC", "CD", "D",
         "DC", "DCC", "DCCC", "CM "]
    x = ["", "X", "XX", "XXX", "XL", "L",
         "LX", "LXX", "LXXX", "XC"]
    i = ["", "I", "II", "III", "IV", "V",
         "VI", "VII", "VIII", "IX"]
  
    # Converting to roman
    thousands = m[num // 1000]
    hundreds = c[(num % 1000) // 100]
    tens = x[(num % 100) // 10]
    ones = i[num % 10]
  
    ans = (thousands + hundreds + tens + ones)
  
    return ans


def replaceRomansToIntegers(s):
    matches = re.findall(r'(?=\b(?<![.:])[MDCLXVI]+(?![.:])\b)M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})', s)

    if matches:
        
        for roman in matches:
            s=s.replace(roman, str(romanToInt(roman)))

    return s


def replaceIntegersToRomans(s):
    matches = re.findall(r'\d+', s)

    if matches:
        
        for entero in matches:
            s=s.replace(entero, intToRoman(int(entero)))

    return s


def cleanContentTitle(s):
    s = re.sub(r'  *', ' ', s)
    s = s.replace('-', ' ')
    s = re.sub(r'[\(\[][^\)\]]+[\)\]]', '', s)
    s = re.sub(r'\.[^.]+$', '', s)
    s = cleanEpisodeNumber(s)
    s = re.sub('^(Saga|Trilog.a|Duolog*a) ' , '', s)
    #s = replaceRomansToIntegers(s) ESTO HAY QUE REVISARLO ¿Qué hacemos con las i latinas mayúsculas?

    return s.strip()


def cleanEpisodeNumber(s):
    return re.sub(r'([0-9]+) +([xXeE]) +([0-9]+)', '\\1\\2\\3', s)


def find_video_gvideo_links(item, data):

    msg_id = re.compile(r'subject_([0-9]+)', re.IGNORECASE).search(data)

    if msg_id:

        thanks_match = re.compile(
            r'/\?action=thankyou;msg=' +
            msg_id.group(1),
            re.IGNORECASE).search(data)

        if thanks_match:
            httptools.downloadpage(item.url + thanks_match.group(0), timeout=DEFAULT_HTTP_TIMEOUT)

        data=httptools.downloadpage("https://noestasinvitado.com/msg.php?m="+msg_id.group(1), timeout=DEFAULT_HTTP_TIMEOUT).data
        json_response = json.loads(data.encode().decode('utf-8-sig'))
        data=json_response['body']

    itemlist = []

    patron = r"(?:https|http)://(?:docs|drive).google.com/file/d/[^/]+/(?:preview|edit|view)"  # Hay más variantes de enlaces

    matches = re.compile(patron, re.DOTALL).findall(data)

    if matches:

        title = '[GVIDEO] ' + item.title

        if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
            title = "[COLOR lightgreen][B](VISTO)[/B][/COLOR] " + title

        if len(matches) > 1:

            for url in list(OrderedDict.fromkeys(matches)):
                itemlist.append(
                    Item(channel=item.channel, visto_title=title, context=[{"title":"MARCAR VISTO (OMEGA)", "action": "marcar_item_visto", "channel":"omega"}], action="play", server='gvideo', title=title, url=url,
                         mode=item.mode))
        else:
            itemlist.append(Item(channel=item.channel, visto_title=title, context=[{"title":"MARCAR VISTO (OMEGA)", "action": "marcar_item_visto", "channel":"omega"}], action="play", server='gvideo', title=title,
                                 url=matches[0], mode=item.mode))

        if item.id_topic:
            itemlist.append(Item(channel=item.channel, url_orig=item.url_orig, viewcontent="movies", viewmode="list", url=item.url, id_topic=item.id_topic, title="[B][COLOR lightgrey]MENSAJES DEL FORO[/COLOR][/B]", contentPlot="[I]Mensajes sobre: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leerMensajesHiloForo", thumbnail='https://noestasinvitado.com/logonegro2.png'))   

    return itemlist


def ignore_uploader(item):
    
    ret = xbmcgui.Dialog().yesno('IGNORAR TODO EL CONTENIDO DE '+item.uploader, '¿SEGURO?')

    if ret:

        if item.uploader in UPLOADERS_BLACKLIST:
            UPLOADERS_BLACKLIST.remove(item.uploader)

        UPLOADERS_BLACKLIST.append(item.uploader)

        config.set_setting("omega_blacklist_uploaders", ",".join(UPLOADERS_BLACKLIST), "omega")

        xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', item.uploader+ " añadid@ a IGNORADOS",
                                      os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                                   'thumb', 'omega.gif'), 5000)
        xbmc.executebuiltin('Container.Refresh')


def getMegacrypterFilename(url):
    url_split = url.split('/!')

    mc_api_url = url_split[0] + '/api'

    mc_api_r = {'m': 'info', 'link': url}

    if USE_MC_REVERSE:
        mc_api_r['reverse'] = MC_REVERSE_DATA

    mc_info_res = mc_api_req(mc_api_url, mc_api_r)

    name = mc_info_res['name'].replace('#', '')

    return name


def getMegaFilename(url):
    url = re.sub(r"(\.nz/file/)([^#]+)#", r".nz/#!\2!", url)

    if len(url.split("!")) == 3:
        file_id = url.split("!")[1]
        file_key = url.split("!")[2]
        file = mega_api_req({'a': 'g', 'g': 1, 'p': file_id})
        
        key = crypto.base64_to_a32(file_key)
        k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
        attributes = crypto.base64_url_decode(file['at'])
        attributes = crypto.decrypt_attr(attributes, k)

        return attributes['n']


def find_video_mega_links(item, data):
    
    msg_id = re.compile(r'subject_([0-9]+)', re.IGNORECASE).search(data)

    if msg_id:

        thanks_match = re.compile(
            r'/\?action=thankyou;msg=' +
            msg_id.group(1),
            re.IGNORECASE).search(data)

        if thanks_match:
            httptools.downloadpage(item.url + thanks_match.group(0), timeout=DEFAULT_HTTP_TIMEOUT)
        
        data=httptools.downloadpage("https://noestasinvitado.com/msg.php?m="+msg_id.group(1), timeout=DEFAULT_HTTP_TIMEOUT).data
        json_response = json.loads(data.encode().decode('utf-8-sig'))
        data=json_response['body']

    itemlist = []

    patron = r'(?:\[ *url_mc *\] *([0-9]+) *\[ */ *url_mc *\])|(https://megacrypter\.noestasinvitado\.com/[!0-9a-zA-Z_/-]+)|(https://mega(?:\.co)?\.nz/#[!0-9a-zA-Z_-]+|https://mega(?:\.co)?\.nz/file/[^#]+#[0-9a-zA-Z_-]+)'

    matches = re.compile(patron, re.DOTALL).findall(data)

    mega_sid = mega_login(False)

    saga_pelis = False

    if matches:

        if type(matches) is list:
            
            patron_years = r"[^\w]AÑO.*?([0-9]{4})"

            matches_years = re.compile(patron_years, re.DOTALL).findall(data)

            if len(matches) > 1:

                i = 1

                for id in matches:

                    infoLabels=item.infoLabels

                    title = '[' + str(i) + '/' + str(len(matches)) + '] ' + item.title

                    content_title=item.contentTitle

                    if item.mode == "tvshow":
                        infoLabels['season']=i
                        itemlist.append(Item(channel=item.channel, id_topic=item.id_topic, viewcontent="movies", viewmode="list", action="get_video_mega_links_group",
                                             title=title, url=item.url,
                                             mc_group_id=id[0], infoLabels=infoLabels, contentTitle=content_title, mode=item.mode))
                    else:
                        saga_pelis = True

                        if id[0]:
                            d = httptools.downloadpage("https://noestasinvitado.com/gen_mc.php?id=" + id[0] + "&raw=1", timeout=DEFAULT_HTTP_TIMEOUT).data
                            
                            m = re.search(r'(.*?) *?\[[0-9.]+ *?.*?\] *?(https://megacrypter\.noestasinvitado\.com/.+)', d)
                            
                            filename = m[1] if m else "LINK ERROR"
                        elif id[1]:
                            filename = getMegacrypterFilename(id[1])
                        elif id[2]:
                            filename = getMegaFilename(id[2])

                        if len(matches)==len(matches_years):
                            year = matches_years[i-1]
                        else:
                            year = extract_year(filename)

                        if len(matches)==len(matches_years):
                            year = matches_years[i-1]
                        else:
                            year = extract_year(filename)

                        infoLabels={'year':year}

                        mc_url=None
                        mc_group_id=None

                        if id[0]:
                            mc_group_id=id[0]
                        elif id[1]:
                            mc_url=id[1]
                        elif id[2]:
                            mc_url=id[2]

                        content_title=cleanContentTitle(filename)

                        title="[COLOR orange][B]"+content_title+"[/B][/COLOR] ("+item.uploader+")"

                        itemlist.append(Item(channel=item.channel, id_topic=item.id_topic, viewcontent="movies", viewmode="list", action="get_video_mega_links_group",
                                         title=title, url=item.url, mc_url=mc_url,
                                         mc_group_id=mc_group_id, infoLabels=infoLabels, contentTitle=content_title, mode=item.mode))

                    i = i + 1

                if len(itemlist)>0:
                    if not saga_pelis:
                        itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", viewcontent="movies", viewmode="list", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))
                    
                    if item.id_topic:
                        itemlist.append(Item(channel=item.channel, url_orig=item.url_orig, url=item.url, id_topic=item.id_topic, viewcontent="movies", viewmode="list", title="[B][COLOR lightgrey]MENSAJES DEL FORO[/COLOR][/B]", contentPlot="[I]Mensajes sobre: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leerMensajesHiloForo", thumbnail='https://noestasinvitado.com/logonegro2.png'))
            else:
                id = matches[0]

                mc_url=None
                mc_group_id=None

                if id[0]:
                    mc_group_id=id[0]
                elif id[1]:
                    mc_url=id[1]
                elif id[2]:
                    mc_url=id[2]

                infoLabels=item.infoLabels
            
                if item.mode == "tvshow":
                    infoLabels['season'] = 1
                
                itemlist = get_video_mega_links_group(Item(channel=item.channel, mode=item.mode, id_topic=item.id_topic, viewcontent="movies", viewmode="list", action='', title='', url=item.url, mc_group_id=mc_group_id, mc_url=mc_url, infoLabels=infoLabels))
                
    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def get_video_mega_links_group(item):

    mega_sid = mega_login(False)

    itemlist = []

    id = item.mc_group_id

    if id:
        conta_error = 0

        matches = False

        while not matches and conta_error < FORO_ITEMS_RETRY:
            data = httptools.downloadpage("https://noestasinvitado.com/gen_mc.php?id=" + id + "&raw=1", timeout=DEFAULT_HTTP_TIMEOUT).data
            matches = re.compile(r'(.*? *?\[[0-9.]+ *?.*?\]) *?(https://megacrypter\.noestasinvitado\.com/.+)').findall(data)

            if not matches:
                conta_error+=1
    else:
        matches = [('', item.mc_url)]

    compress_pattern = re.compile(r'\.(zip|rar|rev)$', re.IGNORECASE)

    part_pattern = re.compile(r'\.part([0-9]+)-([0-9]+)$', re.DOTALL)

    episode_pattern = re.compile(r'^.*?(([0-9]+) *?[xXeE] *?0*([0-9]+))')

    sha1_file = False

    if matches:

        multi_url=[]

        multi_url_name = None

        tot_multi_url = 0

        conta_error = 0

        i = 0

        while i < len(matches) and conta_error<FORO_ITEMS_RETRY:
            
            try:

                url = matches[i][1]

                url_split = url.split('/!')

                mc_api_url = url_split[0] + '/api'

                mc_api_r = {'m': 'info', 'link': url}

                if USE_MC_REVERSE:
                    mc_api_r['reverse'] = MC_REVERSE_DATA

                mc_info_res = mc_api_req(mc_api_url, mc_api_r)

                name = mc_info_res['name'].replace('#', '')

                if isVideoFilename(name):

                    size = mc_info_res['size']

                    key = mc_info_res['key']

                    noexpire = mc_info_res['expire'].split('#')[1] if mc_info_res['expire'] else ''

                    compress = compress_pattern.search(name)

                    if compress:

                        conta_error+=1
                        time.sleep(1)

                    else:

                        m = part_pattern.search(name)

                        if m:

                            multi_url_name = name.replace(m.group(0), '')

                            if tot_multi_url == 0:
                                tot_multi_url = int(m.group(2))

                            url = url + '#' + multi_url_name + '#' + str(size) + '#' + key + '#' + noexpire

                            multi_url.append((url + '#' + MC_REVERSE_DATA + '#' + mega_sid, size))

                        else:
                            title = "[B]" + cleanContentTitle(name) + " [COLOR cyan]["+ str(format_bytes(size))+ "][/COLOR][/B]"

                            url = url + '#' + name + '#' + str(size) + '#' + key + '#' + noexpire

                            infoLabels=item.infoLabels

                            if item.mode == "tvshow":
                                episode = episode_pattern.search(title)
                                
                                if episode:
                                    infoLabels['episode'] = int(episode.group(3))
                                    infoLabels['season'] = int(episode.group(2))
                                    title=title.replace(episode.group(1), '[COLOR yellow]'+episode.group(1)+'[/COLOR]')
                                else:
                                    infoLabels['episode'] = i+(0 if sha1_file else 1)

                            if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
                                title = "[COLOR lightgreen][B](VISTO)[/B][/COLOR] " + title

                            if item.mode == "tvshow":
                                infoLabels['playcount']=1 if '(VISTO)' in title else 0

                            itemlist.append(
                                Item(channel=item.channel, visto_title=title, context=[{"title":"MARCAR VISTO (OMEGA)", "action": "marcar_item_visto", "channel":"omega"}], action="play", server='nei', title=title, url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid, thumbnail=get_omega_resource_path("megacrypter.png"), mode=item.mode, infoLabels=infoLabels))

                    i=i+1

                    conta_error=0

                elif name.lower().endswith(".sha1"):
                    sha1_file=True
                    i=i+1
                else:
                    conta_error+=1
                    time.sleep(1)
            except:
                conta_error+=1
                time.sleep(1)

        if len(multi_url)>0 and len(multi_url) == tot_multi_url:

            murl = "*"

            size=0

            #OJO AQUI->SUPONEMOS QUE MEGACRYPTER DEVUELVE LA LISTA DE PARTES ORDENADA CON NATSORT
            for url in multi_url:
                murl+='#'+base64.b64encode(url[0].encode('utf-8')).decode('utf-8')
                size+=url[1]

            title = "[B]" + cleanContentTitle(multi_url_name) + " [COLOR cyan][M("+str(len(multi_url))+") "+str(format_bytes(size))+ "][/COLOR][/B]"

            if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
                title = "[COLOR lightgreen][B](VISTO)[/B][/COLOR] " + title

            infoLabels=item.infoLabels

            itemlist.append(Item(channel=item.channel, visto_title=title, context=[{"title":"MARCAR VISTO (OMEGA)", "action": "marcar_item_visto", "channel":"omega"}], action="play", server='nei', title=title, url=murl, thumbnail=get_omega_resource_path("megacrypter.png"), mode=item.mode, infoLabels=infoLabels))
        
        elif len(multi_url)>0 and len(multi_url) != tot_multi_url:
            itemlist.append(Item(channel=item.channel,title="[COLOR white][B]ERROR AL GENERAR EL ENLACE MULTI (¿TODAS LAS PARTES DISPONIBLES?)[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

    if len(itemlist)>0:
        itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", viewcontent="movies", viewmode="list", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))
        
        if item.id_topic:
            itemlist.append(Item(channel=item.channel, url_orig=item.url_orig, url=item.url, id_topic=item.id_topic, viewcontent="movies", viewmode="list", title="[B][COLOR lightgrey]MENSAJES DEL FORO[/COLOR][/B]", contentPlot="[I]Mensajes sobre: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leerMensajesHiloForo", thumbnail='https://noestasinvitado.com/logonegro2.png'))
     
    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def leer_criticas_fa(item):

    fa_data = None

    if 'fa_data' in item:
        fa_data = item.fa_data

    if not fa_data:
        fa_data = get_filmaffinity_data_advanced(item.contentTitle, str(item.year), "TV_SE" if item.mode=="tvshow" else "")

    logger.info(fa_data)

    if isinstance(fa_data, list) and len(fa_data)>1:

        itemlist = []

        for item_fa_data in fa_data:
            itemlist.append(Item(channel=item.channel, fa_data=item_fa_data, viewcontent="movies", viewmode="list", contentTitle=item_fa_data['fa_title'], contentPlot="[I]Críticas de: "+item_fa_data['fa_title']+"[/I]", title=item_fa_data['fa_title'], action="leer_criticas_fa", thumbnail=item.thumbnail))

        return itemlist

    else:
        
        if isinstance(fa_data, list):

            if len(fa_data) > 0:
                fa_data = fa_data[0]
            else:

                if re.search('\d+', item.contentTitle.lower()):
                    item.contentTitle = replaceIntegersToRomans(item.contentTitle)
                    return leer_criticas_fa(item)

                return []

        film_id = fa_data['film_id']

        criticas_url = "https://www.filmaffinity.com/es/reviews2/1/"+film_id+".html"

        headers = DEFAULT_HEADERS

        headers["Referer"] = criticas_url

        data = httptools.downloadpage(criticas_url, ignore_response_code=True, headers=headers, timeout=DEFAULT_HTTP_TIMEOUT).data

        criticas_pattern = r"revrat\" *?> *?([0-9]+).*?\"rwtitle\".*?href=\"([^\"]+)\" *?>([^<>]+).*?\"revuser\".*?href=\"[^\"]+\" *?>([^<>]+)"

        res = re.compile(criticas_pattern, re.DOTALL).findall(data)
            
        criticas = []

        for critica_nota, critica_url, critica_title, critica_nick in res:
            criticas.append({'nota': critica_nota, 'url': critica_url, 'title': html.unescape(critica_title), 'nick': critica_nick})

        itemlist = []

        if float(fa_data['rate']) >= 7.0:
            rating_text = "[B][COLOR lightgreen]NOTA MEDIA: [" + str(fa_data['rate']) + "][/COLOR][/B]"
        elif float(fa_data['rate']) < 5.0:
            rating_text = "[B][COLOR red]NOTA MEDIA: [" + str(fa_data['rate']) + "][/COLOR][/B]"
        else:
            rating_text = "[B]NOTA MEDIA: [" + str(fa_data['rate']) + "][/B]"

        itemlist.append(Item(channel=item.channel, contentPlot="[I]Críticas de: "+item.contentTitle+"[/I]", title=rating_text, action="", thumbnail=item.thumbnail))

        for critica in criticas:
            if float(critica['nota']) >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(critica['nota']) + "][/COLOR][/B]"
                thumbnail = get_omega_resource_path("buena.png")
            elif float(critica['nota']) < 5.0:
                rating_text = "[B][COLOR red][" + str(critica['nota']) + "][/COLOR][/B]"
                thumbnail = get_omega_resource_path("mala.png")
            else:
                rating_text = "[B][" + str(critica['nota']) + "][/B]"
                thumbnail = get_omega_resource_path("neutral.png")

            itemlist.append(Item(channel=item.channel, nota_fa=fa_data['rate'], contentPlot="[I]Crítica de: "+item.contentTitle+"[/I]", thumbnail=thumbnail, title=rating_text+" "+critica['title']+" ("+critica['nick']+")", action="cargar_critica", url=critica['url']))

        return itemlist

def clean_html_tags(data):
    tag_re = re.compile(r'(<!--.*?-->|<[^>]*>)')

    # Remove well-formed tags, fixing mistakes by legitimate users
    no_tags = tag_re.sub('', data)

    return no_tags

def cargar_critica(item):
    
    headers = DEFAULT_HEADERS

    headers["Referer"] = item.url

    data = httptools.downloadpage(item.url, ignore_response_code=True, headers=headers, timeout=DEFAULT_HTTP_TIMEOUT).data

    critica_pattern = r"\"review-text1\" *?>(.*?)< *?/ *?div"

    res = re.compile(critica_pattern, re.DOTALL).search(data)

    if res:
        xbmcgui.Dialog().textviewer(item.title, html.unescape(clean_html_tags(res.group(1).replace('<br>', "\n"))))

def indice_links(item):
    itemlist = []

    data = httptools.downloadpage(item.url, timeout=DEFAULT_HTTP_TIMEOUT).data

    patron = r'<tr class="windowbg2">[^<>]*<td[^<>]*>[^<>]*<img[^<>]*>[^<>]' \
             '*</td>[^<>]*<td>[^<>]*<a href="([^"]+)">(.*?)</a>[^<>]*</td>[^<>]*<td[^<>]*>[^<>]*<a[^<>]*>([^<>]+)'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, rawscrapedtitle, uploader in matches:

        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = parseScrapedTitle(rawscrapedtitle)

        if uploader != '>':
            title = scrapedtitle + " (" + uploader + ")"
        else:
            title = scrapedtitle

        thumbnail = ""

        content_serie_name = ""

        parsed_title = parse_title(scrapedtitle)

        content_title = re.sub('^(Saga|Trilog.a|Duolog*a) ' , '', parsed_title['title'])

        if item.mode == "tvshow":
            content_type = "tvshow"
            content_serie_name = content_title
        else:
            content_type = "movie"

        info_labels = {'year': parsed_title['year']}

        if 'Ultra HD' in item.cat:
            quality = 'UHD'
        elif 'HD' in item.cat:
            quality = 'HD'
        else:
            quality = 'SD'

        title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "") + " [" + quality + "] ##*NOTA*## (" + uploader + ")"

        ignore_title = url+parsed_title['title']+("[COLOR magenta][B][SERIE][/B][/COLOR] " if content_type == "tvshow" else "")+("[" + quality + "]" if quality else "")+uploader

        if ignore_title not in ITEM_BLACKLIST:
            itemlist.append(Item(channel=item.channel, scraped_title=rawscrapedtitle, ignore_title=ignore_title, mode=item.mode, viewcontent="movies", viewmode="list", thumbnail=thumbnail, section=item.section, action="foro", title=title, url=url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:
        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def load_mega_proxy(host, port, password):
    if USE_MC_REVERSE:
        try:
            mega_proxy = MegaProxyServer(host, port, password)
            mega_proxy.daemon = True
            mega_proxy.start()
        except socket.error:
            pass


def mc_api_req(api_url, req):
    load_mega_proxy('', MC_REVERSE_PORT, MC_REVERSE_PASS)

    request = urllib.request.Request(api_url, data=json.dumps(req).encode("utf-8"), headers=DEFAULT_HEADERS)

    response = urllib.request.urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT).read()

    return json.loads(response.decode('utf-8-sig'))


def mega_api_req(req, get=""):
    seqno = random.randint(0, 0xFFFFFFFF)
    
    api_url = 'https://g.api.mega.co.nz/cs?id=%d%s' % (seqno, get)
    
    request = urllib.request.Request(api_url, data=json.dumps([req]).encode("utf-8"), headers=DEFAULT_HEADERS)

    response = urllib.request.urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT).read()

    return json.loads(response)[0]


def format_bytes(bytes, precision=2):
    units = ['B', 'KB', 'MB', 'GB', 'TB']

    if bytes:
        bytes = max(bytes, 0)

        pow = min(
            math.floor(
                math.log(
                    bytes if bytes else 0,
                    1024)),
            len(units) -
            1)

        bytes = float(bytes) / (1 << int(10 * pow))

        return str(round(bytes, precision)) + ' ' + units[int(pow)]
    else:
        return "SIZE-ERROR"


def extract_title(title):
    pattern = re.compile(r'^[^\[\]()]+', re.IGNORECASE)

    res = pattern.search(title)

    if res:

        return res.group(0).strip()

    else:

        return ""

def extract_quality(title):
    patterns = [{'p': r'\[[^\[\]()]*(UHD|2160)', 'q': 'UHD'}, {'p': r'\[[^\[\]()]*(microHD|720|1080)', 'q': 'HD'}, {'p': r'\[[^\[\]()]*(HDrip|DVD)', 'q': 'SD'}]
    
    for p in patterns:
        pattern = re.compile(p['p'], re.IGNORECASE)

        res = pattern.search(title)

        if res:

            return p['q']

    return None


def play(item):
    itemlist = []

    marcar_item_visto(item, False)

    itemlist.append(item)

    return itemlist


def marcar_item_visto(item, notify=True):

    title = item.visto_title if "visto_title" in item else item.title
    
    checksum = hashlib.sha1(title.replace("[COLOR lightgreen][B](VISTO)[/B][/COLOR] ", '').encode('utf-8')).hexdigest()

    if checksum not in HISTORY:
        HISTORY.append(checksum)

        with open(KODI_NEI_HISTORY_PATH, "a+") as file:
            file.write((checksum + "\n"))

        if notify:
            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "MARCADO COMO VISTO (puede que tengas que refrescar la página)", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)


def customize_title(item):

    logger.info("CUSTOMIZE TITLE -> "+item.scraped_title)

    sha1 = hashlib.sha1(item.scraped_title.encode('utf-8')).hexdigest()

    logger.info(sha1)
    
    custom_title = CUSTOM_TITLES[sha1] if sha1 in CUSTOM_TITLES.keys() else item.scraped_title

    mensaje = xbmcgui.Dialog().input("TERMINAR con '*' para forzar PELI ó '#' para SERIE", custom_title)

    if mensaje and mensaje!=custom_title:
        CUSTOM_TITLES[sha1] = mensaje

        with open(KODI_NEI_CUSTOM_TITLES_PATH, "w+") as file:

            for k in CUSTOM_TITLES.keys():
                file.write((k + "#" + base64.b64encode(CUSTOM_TITLES[k].encode('utf-8')).decode('utf-8') + "\n"))

        xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "TÍTULO PERSONALIZADO", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)


def ignore_item(item):

    ret = xbmcgui.Dialog().yesno('IGNORAR ESTE APORTE', '¿SEGURO?') if item.ignore_confirmation else True

    if ret:

        if item.ignore_title not in ITEM_BLACKLIST:
            ITEM_BLACKLIST.append(item.ignore_title)

            with open(KODI_NEI_BLACKLIST_ITEM_PATH, "a+") as file:
                file.write((item.ignore_title + "\n"))

            xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "APORTE IGNORADO (puede que tengas que refrescar la página actual para que desaparezca)", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'omega.gif'), 5000)


def extract_year(title):
    pattern = re.compile(r'[\(\[][^\]\)\w]*([0-9]{4})[^p]', re.IGNORECASE)

    res = pattern.search(title)

    if res:

        return res.group(1)

    else:

        return ""


def parse_title(title):
    return {'title': extract_title(title), 'year': extract_year(title), 'quality': extract_quality(title)}


def get_filmaffinity_data_advanced(title, year, genre):

    title = re.sub('^Saga ' , '', title)
    
    fa_data_filename = KODI_TEMP_PATH + 'kodi_nei_fa_' + hashlib.sha1((title+year+genre).encode('utf-8')).hexdigest()

    if os.path.isfile(fa_data_filename):
        with open(fa_data_filename, "rb") as f:
            return pickle.load(f)

    url = "https://www.filmaffinity.com/es/advsearch.php?stext=" + title.replace(' ',
                                                                                 '+').replace('?', '') + "&stype%5B%5D" \
                                                                                                         "=title&country=" \
                                                                                                         "&genre=" + genre + \
          "&fromyear=" + year + "&toyear=" + year

    logger.info(url)

    headers = DEFAULT_HEADERS

    data = httptools.downloadpage(url, ignore_response_code=True, headers=headers, timeout=DEFAULT_HTTP_TIMEOUT).data

    res = re.compile(r"title=\"([^\"]+)\"[^<>]+href=\"https://www.filmaffinity.com/es/film([0-9]+)\.html\".*?(https://pics\.filmaffinity\.com/[^\"]+-msmall\.jpg).*?\"avgrat-box\" *?> *?([0-9,]+).*?", re.DOTALL).findall(data)

    fa_data=[]

    for fa_title, film_id, thumb_url, rate in res:

        rate = rate.replace(',', '.')

        fa_data.append({'rate': rate, 'film_id': film_id, 'fa_title': fa_title, 'thumb_url': thumb_url})

    with open(fa_data_filename, 'wb') as f:
        pickle.dump(fa_data, f)

    return fa_data


# OMEGA uses a modified version of Alfa's MEGA LIB with support for MEGACRYPTER and multi thread
def check_mega_lib_integrity():
    update_url = ALFA_URL + 'lib/megaserver/'

    megaserver_lib_path = ALFA_PATH + 'lib/megaserver/'

    urllib.request.urlretrieve(update_url + 'checksum.sha1', megaserver_lib_path + 'checksum.sha1')

    sha1_checksums = {}

    with open(megaserver_lib_path + 'checksum.sha1') as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    modified = False

    if not os.path.exists(megaserver_lib_path):
        os.mkdir(megaserver_lib_path)

    for filename, checksum in sha1_checksums.items():

        if not os.path.exists(megaserver_lib_path + filename):

            urllib.request.urlretrieve(
                update_url + filename,
                megaserver_lib_path + filename)

            modified = True

        else:

            with open(megaserver_lib_path + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:

                os.rename(
                    megaserver_lib_path +
                    filename,
                    megaserver_lib_path +
                    filename +
                    ".bak")

                if os.path.isfile(megaserver_lib_path + filename + "o"):
                    os.remove(megaserver_lib_path + filename + "o")

                urllib.request.urlretrieve(
                    update_url + filename,
                    megaserver_lib_path + filename)

                modified = True

    return modified


# OMEGA uses a modified version of Alfa's MEGA connector with support for MEGACRYPTER and multi thread
def check_nei_connector_integrity():
    update_url = ALFA_URL + 'servers/'

    connectors_path = ALFA_PATH + 'servers/'

    urllib.request.urlretrieve(update_url + 'checksum.sha1', connectors_path + 'checksum.sha1')

    sha1_checksums = {}

    with open(connectors_path + 'checksum.sha1') as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    modified = False

    for filename, checksum in sha1_checksums.items():

        if not os.path.exists(connectors_path + filename):

            urllib.request.urlretrieve(
                update_url + filename,
                connectors_path + filename)

            modified = True

        else:

            with open(connectors_path + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:

                if os.path.isfile(connectors_path + filename + "o"):
                    os.remove(connectors_path + filename + "o")

                urllib.request.urlretrieve(
                    update_url + filename,
                    connectors_path + filename)

                modified = True

    return modified

if CHECK_STUFF_INTEGRITY and check_mega_lib_integrity():
    xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')',
                                  "Librería de MEGA/MegaCrypter reparada/actualizada",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'omega.gif'), 5000)

if CHECK_STUFF_INTEGRITY and check_nei_connector_integrity():
    xbmcgui.Dialog().notification('OMEGA (' + OMEGA_VERSION + ')', "Conector de NEI reparado/actualizado",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'omega.gif'), 5000)

from megaserver import Mega, MegaProxyServer, RequestError, crypto #AL FINAL PORQUE SI HEMOS REPARADO LA LIBRERÍA DE MEGA QUEREMOS IMPORTAR LA VERSIÓN BUENA
