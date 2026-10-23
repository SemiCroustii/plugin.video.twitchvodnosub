# Accès à Twitch : métadonnées via GQL et résolution des playlists comme le fait l'extension TwitchNoSub.
import json
import re
import struct
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

GQL_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'
QUALITIES = ['chunked', '1440p60', '1080p60', '1080p30', '720p60', '720p30', '480p30', '360p30', '160p30', 'audio_only']
TIMEOUT = 15

VIDEO_FIELDS = '''
  id title broadcastType createdAt lengthSeconds seekPreviewsURL
  previewThumbnailURL(width: 640, height: 360)
  owner { login displayName }
'''


class TwitchError(Exception):
    pass


def gql(query, variables=None):
    body = json.dumps({'query': query, 'variables': variables or {}}).encode('utf-8')
    req = Request('https://gql.twitch.tv/gql', data=body, method='POST',
                  headers={'Client-Id': GQL_CLIENT_ID, 'Content-Type': 'application/json'})
    with urlopen(req, timeout=TIMEOUT) as res:
        data = json.loads(res.read().decode('utf-8'))
    if data.get('errors'):
        raise TwitchError(data['errors'][0].get('message', 'Erreur GQL'))
    return data.get('data') or {}


def parse_vod_id(text):
    s = (text or '').strip()
    m = re.search(r'videos/(\d+)', s) or re.match(r'^(\d+)$', s)
    return m.group(1) if m else None


def parse_login(text):
    s = (text or '').strip()
    m = re.search(r'twitch\.tv/([A-Za-z0-9_]+)', s)
    login = m.group(1) if m else s.lstrip('@')
    return login.lower() if re.match(r'^[A-Za-z0-9_]{2,25}$', login) else None


def get_video(vod_id):
    video = gql('query($id: ID!) { video(id: $id) { %s } }' % VIDEO_FIELDS, {'id': vod_id}).get('video')
    if not video:
        raise TwitchError('VOD introuvable (supprimée ou ID invalide)')
    if not video.get('seekPreviewsURL'):
        raise TwitchError('Impossible de résoudre le chemin de la VOD')
    return video


def get_channel_videos(login):
    """Retourne (utilisateur, 100 dernières vidéos).

    Twitch refuse les requêtes paginées (paramètre after) sans jeton d'intégrité :
    on récupère donc le maximum autorisé en une fois et on pagine côté add-on.
    """
    query = '''query($login: String!) {
      user(login: $login) {
        login displayName profileImageURL(width: 300)
        videos(first: 100, sort: TIME) { edges { node { %s } } }
      }
    }''' % VIDEO_FIELDS
    user = gql(query, {'login': login}).get('user')
    if not user:
        raise TwitchError('Chaîne introuvable : %s' % login)
    videos = user.pop('videos') or {'edges': []}
    return user, [e['node'] for e in videos['edges']]


def created_at(video):
    # Pas de datetime.strptime : sous Kodi il échoue souvent ('NoneType' object is not callable)
    parts = [int(p) for p in re.findall(r'\d+', video['createdAt'])[:6]]
    return datetime(*parts, tzinfo=timezone.utc)


def playlist_url(video, quality):
    u = urlparse(video['seekPreviewsURL'])
    parts = [p for p in u.path.split('/') if p]
    special = parts[parts.index('storyboards') - 1]
    base = 'https://%s' % u.netloc
    age_days = (datetime.now(timezone.utc) - created_at(video)).total_seconds() / 86400
    if video['broadcastType'] == 'HIGHLIGHT':
        return '%s/%s/%s/highlight-%s.m3u8' % (base, special, quality, video['id'])
    if video['broadcastType'] == 'UPLOAD' and age_days > 7:
        return '%s/%s/%s/%s/%s/index-dvr.m3u8' % (base, video['owner']['login'], video['id'], special, quality)
    return '%s/%s/%s/index-dvr.m3u8' % (base, special, quality)


def _exists(url):
    try:
        with urlopen(Request(url, method='HEAD'), timeout=TIMEOUT) as res:
            return res.status == 200
    except Exception:
        return False


def available_qualities(video):
    """Qualités dont la playlist existe, de la meilleure à la moins bonne."""
    urls = [playlist_url(video, q) for q in QUALITIES]
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        found = list(pool.map(_exists, urls))
    return [q for q, ok in zip(QUALITIES, found) if ok]


def pick_quality(available, max_height):
    """Meilleure qualité disponible ne dépassant pas max_height (None = source)."""
    if max_height is None:
        return available[0]
    for q in available:
        m = re.match(r'(\d+)p', q)
        if m and int(m.group(1)) <= max_height:
            return q
    return available[-1]


def _video_info(media_url):
    """(codec, (largeur, hauteur) ou None) lus dans le segment d'initialisation (MP4 fragmenté).

    Segments .ts : pas de segment d'initialisation, on suppose du H.264 de taille inconnue.
    """
    with urlopen(media_url, timeout=TIMEOUT) as res:
        m = re.search(r'#EXT-X-MAP:URI="([^"]+)"', res.read().decode('utf-8', 'replace'))
    if not m:
        return 'avc1.64002A', None
    with urlopen(urljoin(media_url, m.group(1)), timeout=TIMEOUT) as res:
        init = res.read()
    # Première entrée de chaque boîte stsd (une par piste) : taille(4) type(4) version(4) nombre(4) puis l'entrée
    stsd = init.find(b'stsd')
    while stsd >= 0:
        entry = stsd + 16
        fourcc = init[entry:entry + 4]
        if fourcc in (b'avc1', b'hvc1', b'hev1', b'av01'):
            # Entrée d'échantillon visuelle : largeur et hauteur sur 16 bits, 24 octets après le type
            size = struct.unpack('>HH', init[entry + 28:entry + 32])
            if fourcc == b'avc1':
                avcc = init.find(b'avcC', entry)
                codec = 'avc1.%02X%02X%02X' % tuple(init[avcc + 5:avcc + 8])
            else:
                codec = {b'hvc1': 'hvc1.1.6.L150.B0', b'hev1': 'hev1.1.6.L150.B0', b'av01': 'av01.0.08M.08'}[fourcc]
            return codec, size if all(size) else None
        stsd = init.find(b'stsd', stsd + 4)
    return 'avc1.64002A', None


def master_playlist(media_url, quality, audio_url=None):
    """Playlist maîtresse pour une qualité.

    Twitch ne fournit pas de playlist maîtresse pour ces VODs. InputStream Adaptive ne lit qu'une piste
    des segments MP4 fragmentés (où l'audio est multiplexé avec la vidéo) : on déclare donc la playlist
    audio_only comme piste audio séparée quand elle existe.
    """
    if quality == 'audio_only':
        return '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=160000,CODECS="mp4a.40.2"\n%s\n' % media_url
    lines = ['#EXTM3U']
    codec, size = _video_info(media_url)
    attrs = ['BANDWIDTH=8000000', 'CODECS="%s,mp4a.40.2"' % codec]
    m = re.match(r'(\d+)p(\d+)', quality)
    if not size and m:
        size = (int(m.group(1)) * 16 // 9, int(m.group(1)))
    # Sans résolution, Kodi sur Android n'ouvre pas le décodeur matériel et décode en logiciel
    if size:
        attrs.append('RESOLUTION=%dx%d' % size)
    if m:
        attrs.append('FRAME-RATE=%s' % m.group(2))
    if audio_url:
        lines.append('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Audio",DEFAULT=YES,AUTOSELECT=YES,URI="%s"' % audio_url)
        attrs.append('AUDIO="audio"')
    lines += ['#EXT-X-STREAM-INF:' + ','.join(attrs), media_url]
    return '\n'.join(lines) + '\n'


def quality_label(q):
    return {'chunked': 'Source', 'audio_only': 'Audio seulement'}.get(q, q)
