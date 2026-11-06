# Add-on Kodi : parcourt les VODs Twitch et les lit directement, même celles réservées aux abonnés.
import json
import os
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
import twitch  # noqa: E402

ADDON = xbmcaddon.Addon()
NAME = ADDON.getAddonInfo('name')
BASE_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
PARAMS = dict(parse_qsl(sys.argv[2][1:]))
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
CHANNELS_FILE = os.path.join(PROFILE, 'channels.json')

# Index du réglage « Qualité » -> hauteur max (None = source), 'ask' pour demander à chaque fois
QUALITY_SETTING = ['ask', None, 1080, 720, 480, 360, 'audio']

# Codes d'erreur de twitch.TwitchError -> chaîne traduite
ERROR_STRINGS = {'vod_not_found': 30200, 'vod_unresolved': 30201, 'channel_not_found': 30202, 'no_playlist': 30203}


def L(string_id):
    """Texte traduit (resources/language/*/strings.po) selon la langue de Kodi."""
    return ADDON.getLocalizedString(string_id)


def error_message(err):
    if isinstance(err, twitch.TwitchError) and err.code in ERROR_STRINGS:
        return L(ERROR_STRINGS[err.code]) % err.details
    return str(err)


def quality_label(q):
    return {'chunked': L(30114), 'audio_only': L(30008)}.get(q, q)


def date_format():
    # Format de date court de la région configurée dans Kodi
    return xbmc.getRegion('dateshort') or '%d/%m/%Y'


def url_for(**params):
    return BASE_URL + '?' + urlencode(params)


def setting_int(key, default):
    try:
        return int(ADDON.getSetting(key))
    except ValueError:
        return default


# --- Chaînes enregistrées -------------------------------------------------

def load_channels():
    try:
        with open(CHANNELS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_channels(channels):
    os.makedirs(PROFILE, exist_ok=True)
    with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)


# --- Éléments de liste ----------------------------------------------------

def set_video_info(li, info):
    # InfoTagVideo à partir de Kodi 20, setInfo pour Kodi 19
    if hasattr(li, 'getVideoInfoTag'):
        tag = li.getVideoInfoTag()
        tag.setMediaType('video')
        tag.setTitle(info['title'])
        tag.setPlot(info['plot'])
        tag.setDuration(info['duration'])
        tag.setPremiered(info['date'])
        tag.setStudios([info['channel']])
    else:
        li.setInfo('video', {
            'mediatype': 'video', 'title': info['title'], 'plot': info['plot'],
            'duration': info['duration'], 'premiered': info['date'], 'studio': info['channel'],
        })


def video_item(video):
    date = twitch.created_at(video).astimezone()
    channel = video['owner']['displayName']
    kind = {'HIGHLIGHT': L(30112), 'UPLOAD': L(30113)}.get(video['broadcastType'])
    label = '%s  %s' % (date.strftime(date_format()), video['title'])
    if kind:
        label += '  [COLOR grey](%s)[/COLOR]' % kind
    li = xbmcgui.ListItem(label)
    thumb = video.get('previewThumbnailURL')
    if thumb and '404_processing' in thumb:  # image de remplacement inaccessible (403)
        thumb = None
    li.setArt({'thumb': thumb, 'icon': thumb, 'fanart': thumb})
    set_video_info(li, {
        'title': video['title'],
        'plot': '%s\n%s - %s' % (video['title'], channel, date.strftime(date_format() + ' %H:%M')),
        'duration': video.get('lengthSeconds') or 0,
        'date': date.strftime('%Y-%m-%d'),
        'channel': channel,
    })
    li.setProperty('IsPlayable', 'true')
    li.addContextMenuItems([
        (L(30111), 'PlayMedia(%s)' % url_for(action='play', id=video['id'], ask='1')),
    ])
    return li


def folder(label, url, icon='DefaultFolder.png', context=None, is_folder=True):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': icon, 'thumb': icon})
    if context:
        li.addContextMenuItems(context)
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)


# --- Vues -----------------------------------------------------------------

def root():
    # Actions (pas des dossiers) : elles demandent une saisie puis ouvrent la page correspondante
    folder(L(30100), url_for(action='open'), 'DefaultAddSource.png', is_folder=False)
    folder(L(30101), url_for(action='search'), 'DefaultAddonsSearch.png', is_folder=False)
    for ch in load_channels():
        folder(ch['name'], url_for(action='channel', login=ch['login']), ch.get('icon') or 'DefaultFolder.png',
               context=[(L(30102), 'RunPlugin(%s)' % url_for(action='remove', login=ch['login']))])
    xbmcplugin.endOfDirectory(HANDLE)


def open_vod():
    text = xbmcgui.Dialog().input(L(30103))
    vod_id = twitch.parse_vod_id(text)
    if text and not vod_id:
        xbmcgui.Dialog().notification(NAME, L(30104), xbmcgui.NOTIFICATION_ERROR)
    # Ouvre une URL stable pour ne pas redemander la saisie au retour ou au rafraîchissement
    if vod_id:
        xbmc.executebuiltin('Container.Update(%s)' % url_for(action='vod', id=vod_id))


def vod(vod_id):
    video = twitch.get_video(vod_id)
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addDirectoryItem(HANDLE, url_for(action='play', id=vod_id), video_item(video))
    xbmcplugin.endOfDirectory(HANDLE)


def search():
    text = xbmcgui.Dialog().input(L(30105))
    login = twitch.parse_login(text)
    if text and not login:
        xbmcgui.Dialog().notification(NAME, L(30106), xbmcgui.NOTIFICATION_ERROR)
    if login:
        xbmc.executebuiltin('Container.Update(%s)' % url_for(action='channel', login=login))


def channel(login, page):
    user, videos = twitch.get_channel_videos(login)
    page_size = setting_int('page_size', 30)
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.setPluginCategory(HANDLE, user['displayName'])

    if page == 0 and not any(ch['login'] == user['login'] for ch in load_channels()):
        li = xbmcgui.ListItem('[B]%s[/B]' % (L(30107) % user['displayName']))
        li.setArt({'icon': 'DefaultAddSource.png'})
        xbmcplugin.addDirectoryItem(HANDLE, url_for(action='add', login=user['login']), li)

    if not videos:
        xbmcgui.Dialog().notification(NAME, L(30109))
    start = page * page_size
    for video in videos[start:start + page_size]:
        xbmcplugin.addDirectoryItem(HANDLE, url_for(action='play', id=video['id']), video_item(video))
    if start + page_size < len(videos):
        folder(L(30110) % (page + 2, -(-len(videos) // page_size)),
               url_for(action='channel', login=login, page=page + 1), 'DefaultFolder.png')
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def add_channel(login):
    user, _ = twitch.get_channel_videos(login)
    channels = [ch for ch in load_channels() if ch['login'] != user['login']]
    channels.append({'login': user['login'], 'name': user['displayName'], 'icon': user.get('profileImageURL')})
    save_channels(sorted(channels, key=lambda ch: ch['name'].lower()))
    xbmcgui.Dialog().notification(NAME, L(30108) % user['displayName'])
    xbmc.executebuiltin('Container.Refresh')


def remove_channel(login):
    save_channels([ch for ch in load_channels() if ch['login'] != login])
    xbmc.executebuiltin('Container.Refresh')


def play(vod_id, ask):
    video = twitch.get_video(vod_id)
    available = twitch.available_qualities(video)
    if not available:
        raise twitch.TwitchError('no_playlist')

    pref = QUALITY_SETTING[min(setting_int('quality', 1), len(QUALITY_SETTING) - 1)]
    if ask or pref == 'ask':
        choice = xbmcgui.Dialog().select(L(30001), [quality_label(q) for q in available])
        if choice < 0:
            return xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        quality = available[choice]
    elif pref == 'audio':
        quality = 'audio_only' if 'audio_only' in available else available[-1]
    else:
        quality = twitch.pick_quality(available, pref)

    url = twitch.playlist_url(video, quality)
    li = video_item(video)
    li.setPath(url)
    li.setMimeType('application/vnd.apple.mpegurl')
    li.setContentLookup(False)
    # Le lecteur interne de Kodi gère mal les sauts dans les VODs Twitch (HLS en MP4 fragmenté)
    if ADDON.getSetting('inputstream') == 'true' and inputstream_ready():
        port = xbmcgui.Window(10000).getProperty('twitchvodnosub.port')
        if port:
            # Playlist maîtresse servie par service.py : sans elle, InputStream Adaptive ignore l'audio
            params = {'media': url, 'quality': quality}
            if 'audio_only' in available:
                params['audio'] = twitch.playlist_url(video, 'audio_only')
            li.setPath('http://127.0.0.1:%s/master.m3u8?%s' % (port, urlencode(params)))
            li.setProperty('inputstream', 'inputstream.adaptive')
            if kodi_version() < 21:
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        else:
            xbmc.log('[%s] service local non démarré, lecture sans InputStream Adaptive' % NAME, xbmc.LOGWARNING)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def kodi_version():
    try:
        return int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    except ValueError:
        return 0


def inputstream_ready():
    """Vérifie qu'InputStream Adaptive est installé et activé, propose de l'installer sinon."""
    if not xbmc.getCondVisibility('System.HasAddon(inputstream.adaptive)'):
        if not xbmcgui.Dialog().yesno(NAME, L(30115)):
            ADDON.setSetting('inputstream', 'false')
            return False
        xbmc.executebuiltin('InstallAddon(inputstream.adaptive)', True)
        if not xbmc.getCondVisibility('System.HasAddon(inputstream.adaptive)'):
            return False
    if not xbmc.getCondVisibility('System.AddonIsEnabled(inputstream.adaptive)'):
        xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled',
                                        'params': {'addonid': 'inputstream.adaptive', 'enabled': True}}))
    return bool(xbmc.getCondVisibility('System.AddonIsEnabled(inputstream.adaptive)'))


def router():
    action = PARAMS.get('action')
    try:
        if action is None:
            root()
        elif action == 'open':
            open_vod()
        elif action == 'vod':
            vod(PARAMS['id'])
        elif action == 'search':
            search()
        elif action == 'channel':
            channel(PARAMS['login'], int(PARAMS.get('page', 0)))
        elif action == 'add':
            add_channel(PARAMS['login'])
        elif action == 'remove':
            remove_channel(PARAMS['login'])
        elif action == 'play':
            play(PARAMS['id'], PARAMS.get('ask') == '1')
    except Exception as err:
        xbmc.log('[%s] %r' % (NAME, err), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(NAME, error_message(err), xbmcgui.NOTIFICATION_ERROR)
        if action == 'play':
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        elif action in (None, 'vod', 'channel'):
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


router()
