# Service Kodi : petit serveur HTTP local qui fournit à InputStream Adaptive la playlist maîtresse des VODs
# (il refuse les fichiers locaux et Twitch n'en fournit pas pour ces VODs).
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlparse

import xbmc
import xbmcgui

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
import twitch  # noqa: E402

PORT_PROPERTY = 'twitchvodnosub.port'


def is_playlist(url):
    return url.startswith('https://') and urlparse(url).path.endswith('.m3u8')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        params = dict(parse_qsl(url.query))
        media, audio = params.get('media', ''), params.get('audio')
        if url.path != '/master.m3u8' or not all(is_playlist(u) for u in (media, audio) if u is not None):
            return self.send_error(404)
        try:
            body = twitch.master_playlist(media, params.get('quality', 'chunked'), audio).encode('utf-8')
        except Exception as err:
            xbmc.log('[TwitchVODNoSub] playlist maîtresse : %r' % err, xbmc.LOGERROR)
            return self.send_error(502)
        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)  # port libre choisi par le système
    threading.Thread(target=server.serve_forever, daemon=True).start()
    home = xbmcgui.Window(10000)
    home.setProperty(PORT_PROPERTY, str(server.server_address[1]))
    xbmc.log('[TwitchVODNoSub] serveur local sur le port %d' % server.server_address[1], xbmc.LOGINFO)
    xbmc.Monitor().waitForAbort()
    home.clearProperty(PORT_PROPERTY)
    server.shutdown()
    server.server_close()


run()
