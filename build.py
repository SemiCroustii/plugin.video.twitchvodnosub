# Construit le zip installable dans Kodi : dist/plugin.video.twitchvodnosub-<version>.zip
import os
import re
import sys
import zipfile

ADDON_ID = 'plugin.video.twitchvodnosub'
ROOT = os.path.dirname(os.path.abspath(__file__))


def addon_version():
    with open(os.path.join(ROOT, ADDON_ID, 'addon.xml'), encoding='utf-8') as f:
        return re.search(r'<addon\b[^>]*\bversion="([^"]+)"', f.read()).group(1)


def build():
    version = addon_version()
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    path = os.path.join(ROOT, 'dist', '%s-%s.zip' % (ADDON_ID, version))
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for folder, dirs, files in os.walk(os.path.join(ROOT, ADDON_ID)):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for name in files:
                full = os.path.join(folder, name)
                # Chemins avec « / » : Kodi sous Linux/Android rejette les zips avec « \ »
                z.write(full, os.path.relpath(full, ROOT).replace(os.sep, '/'))
    return path


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--version':
        print(addon_version())
    else:
        print(build())
