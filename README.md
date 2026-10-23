# TwitchVODNoSub — add-on Kodi

Add-on Kodi pour regarder les VODs Twitch, **y compris celles réservées aux abonnés**, directement depuis le CDN de Twitch.

## Fonctionnalités

- **Ouvrir une VOD** à partir de son lien (`https://www.twitch.tv/videos/…`) ou de son ID
- **Rechercher une chaîne** et parcourir ses VODs (les 100 dernières), avec miniatures, dates et durées
- **Chaînes enregistrées** sur l'écran d'accueil de l'add-on
- **Choix de la qualité** : Source, 1080p, 720p, … ou « Toujours demander » ; menu contextuel « Choisir la qualité » sur chaque VOD
- Lecture via **InputStream Adaptive** : navigation dans la timeline, décodage matériel (HEVC 1440p compris, testé sur Nvidia Shield Pro)

## Installation

1. Téléchargez le zip de la dernière version depuis la page [Releases](../../releases).
2. Dans Kodi : **Paramètres → Système → Add-ons**, activez **Sources inconnues**.
3. **Add-ons → Installer depuis un fichier zip**, puis choisissez le zip.
4. **Redémarrez Kodi** (le service local de l'add-on démarre avec Kodi).

Au premier lancement d'une vidéo, l'add-on propose d'installer InputStream Adaptive s'il est absent.

> N'utilisez pas le bouton « Download ZIP » de GitHub : le dossier qu'il contient n'a pas le nom attendu par Kodi.

Compatible Kodi 19 (Matrix) et suivants ; testé sur Kodi 21 (Windows et Android TV).

## Fonctionnement

1. Les métadonnées des VODs sont récupérées via l'API GQL de Twitch.
2. L'adresse de la playlist HLS est reconstruite à partir de l'URL des aperçus (`seekPreviewsURL`), comme le fait l'extension navigateur TwitchNoSub. Aucune connexion ni jeton n'est nécessaire.
3. Twitch ne fournit pas de playlist maîtresse pour ces VODs. Un petit serveur HTTP local (`service.py`, accessible uniquement sur `127.0.0.1`) en génère une pour InputStream Adaptive, avec :
   - le codec et la résolution réels, lus dans le segment d'initialisation (sans résolution, Kodi sur Android ne peut pas utiliser le décodage matériel) ;
   - la playlist `audio_only` comme piste audio séparée (InputStream Adaptive ne lit qu'une piste dans les segments MP4 où l'audio est mélangé à la vidéo).

## Limites

- **100 VODs maximum par chaîne** : Twitch refuse les requêtes paginées sans jeton d'intégrité.
- Une VOD dont le live est encore en cours est lue comme un direct.
- L'add-on dépend d'API non officielles de Twitch, qui peuvent changer à tout moment.

## Développement

```
plugin.video.twitchvodnosub/
├── addon.xml              # manifeste Kodi
├── main.py                # menus et lecture
├── service.py             # serveur local de playlists maîtresses
└── resources/
    ├── settings.xml       # réglages
    └── lib/twitch.py      # API Twitch et playlists (indépendant de Kodi)
```

Construire le zip installable :

```
python build.py
```

Publier une version : augmentez `version` dans `addon.xml`, puis poussez un tag correspondant (`git tag v1.0.8 && git push --tags`). Le workflow GitHub Actions crée la release avec le zip.

## Avertissement

Projet non officiel, sans lien avec Twitch. À utiliser dans le respect des conditions d'utilisation de Twitch et des droits des créateurs.

## Licence

[MIT](LICENSE)
