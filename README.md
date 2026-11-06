# TwitchVODNoSub — Kodi add-on

Kodi add-on to watch Twitch VODs, **including subscriber-only ones**, straight from Twitch's CDN.

> 🇫🇷 Version française résumée [en bas de page](#en-français).

## Features

- **Open a VOD** from its link (`https://www.twitch.tv/videos/…`) or its ID
- **Search for a channel** and browse its VODs (the latest 100), with thumbnails, dates and durations
- **Saved channels** on the add-on's home screen
- **Quality selection**: Source, 1080p, 720p, … or "Always ask"; a "Choose quality" context menu entry on every VOD
- Playback through **InputStream Adaptive**: timeline seeking, hardware decoding (including 1440p HEVC, tested on Nvidia Shield Pro)

The add-on is available in **English** and **French**, following Kodi's interface language (English is used for any other language).

## Installation

1. Download the zip of the latest version from the [Releases](../../releases) page.
2. In Kodi: **Settings → System → Add-ons**, enable **Unknown sources**.
3. **Add-ons → Install from zip file**, then pick the zip.
4. **Restart Kodi** (the add-on's local service starts with Kodi).

The first time you play a video, the add-on offers to install InputStream Adaptive if it is missing.

> Don't use GitHub's "Download ZIP" button: the folder it contains doesn't have the name Kodi expects.

Compatible with Kodi 19 (Matrix) and later; tested on Kodi 21 (Windows and Android TV).

## How it works

1. VOD metadata is fetched through Twitch's GQL API.
2. The HLS playlist URL is rebuilt from the seek previews URL (`seekPreviewsURL`), as the TwitchNoSub browser extension does. No login or token is required.
3. Twitch doesn't provide a master playlist for these VODs. A small local HTTP server (`service.py`, only reachable on `127.0.0.1`) generates one for InputStream Adaptive, with:
   - the actual codec and resolution, read from the initialization segment (without a resolution, Kodi on Android can't use hardware decoding);
   - the `audio_only` playlist as a separate audio track (InputStream Adaptive only plays one track in MP4 segments where audio is muxed with video).

## Limitations

- **100 VODs max per channel**: Twitch rejects paginated requests without an integrity token.
- A VOD whose stream is still live is played as a live stream.
- The add-on relies on unofficial Twitch APIs, which may change at any time.

## Development

```
plugin.video.twitchvodnosub/
├── addon.xml              # Kodi manifest
├── main.py                # menus and playback
├── service.py             # local master playlist server
└── resources/
    ├── settings.xml       # settings
    ├── language/          # translations (resource.language.en_gb, resource.language.fr_fr)
    └── lib/twitch.py      # Twitch API and playlists (Kodi-independent)
```

Build the installable zip:

```
python build.py
```

Release a version: bump `version` in `addon.xml`, then push a matching tag (`git tag v1.0.8 && git push --tags`). The GitHub Actions workflow creates the release with the zip.

## Disclaimer

Unofficial project, not affiliated with Twitch. Use it in accordance with Twitch's terms of service and creators' rights.

## License

[MIT](LICENSE)

---

## En français

Add-on Kodi pour regarder les VODs Twitch, **y compris celles réservées aux abonnés**, directement depuis le CDN de Twitch : ouverture d'une VOD par lien ou ID, recherche de chaînes (100 dernières VODs), chaînes enregistrées, choix de la qualité, lecture via InputStream Adaptive avec décodage matériel. L'interface est en français ou en anglais selon la langue de Kodi.

**Installation** : téléchargez le zip depuis [Releases](../../releases), activez **Sources inconnues** dans Kodi, puis **Add-ons → Installer depuis un fichier zip**, et redémarrez Kodi. N'utilisez pas le bouton « Download ZIP » de GitHub.

Projet non officiel, sans lien avec Twitch.
