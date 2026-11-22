# Moment

Lille web-app til at styre en BeoSound Moment via B&O's BeoLink/ASE-API (port 8080).

## Start

    python3 server.py [moment-ip] [port]

Standard er `192.168.1.76` og port `8765`. Åbn http://localhost:8765 – eller fra telefonen på samme netværk: `http://<computerens-ip>:8765`.

Kun Python 3's standardbibliotek bruges.

## Sådan virker det

- `server.py` leverer `index.html`, viderestiller `/api/*` til Moment (browseren må ikke kalde den direkte pga. CORS) og omsætter Moment's notifikationsstrøm (`/BeoNotify/Notifications`) til Server-Sent Events på `/events`.
- `index.html` er brugerfladen: nu-spiller, afspil/pause/næste/forrige, lydstyrke og lyd fra, kildevalg, Deezer-kø og standby.

## Brugte endpoints

| Funktion | Kald |
|---|---|
| Enhedsinfo | `GET /BeoDevice` |
| Lydstyrke | `GET /BeoZone/Zone/Sound/Volume`, `PUT .../Speaker/Level {"level": n}` |
| Lyd fra | `PUT /BeoZone/Zone/Sound/Volume/Speaker/Muted {"muted": true}` |
| Afspil m.m. | `POST /BeoZone/Zone/Stream/{Play,Pause,Forward,Backward}` + `.../Release` |
| Kilder | `GET /BeoZone/Zone/Sources/`, `POST /BeoZone/Zone/ActiveSources {"primaryExperience":{"source":{"id": ...}}}` |
| Kø | `GET /BeoZone/Zone/PlayQueue/` |
| Standby | `PUT /BeoDevice/powerManagement/standby {"standby":{"powerState":"standby"}}` |
| Hændelser | `GET /BeoNotify/Notifications` (lang strøm af JSON) |

API'et er ikke officielt dokumenteret; endpoints er fundet ved at udforske enheden og fra fællesskabsprojektet [giachello/beoplay](https://github.com/giachello/beoplay).
