# Room Night Light

Nachtlicht, Automatik-Licht und gemerkter Normalzustand für Räume in Home Assistant, als ein Eintrag pro Licht statt kopierter Automationen.

## Was es macht

Jedes Licht hat einen **Modus**:

| Modus | Wann | Was passiert |
|---|---|---|
| **Aus** | Licht ist aus | Bewegung kann es einschalten |
| **Nachtlicht** | Bewegung nachts (nach Sonnenuntergang oder solange der Nacht-Schalter an ist) | z. B. 10 % / 2000 K; aus nach 1 Min ohne Bewegung |
| **Automatik** | Bewegung bei Dunkelheit, wenn nicht Nacht ist (Helligkeitssensor unter Schwelle oder Sonne unter dem Horizont) | z. B. 40 % / 2700 K; aus nach 2 Min ohne Bewegung |
| **Manuell** | Taste, App, Sprache, Szene | Normalzustand; wird **nie** automatisch ausgeschaltet |

- **Taste** (ZHA, z. B. Hue-Dimmschalter): Nachtlicht/Automatik → Manuell, Manuell → Nachtlicht (wenn nachts und jemand da) bzw. Aus, Aus → Manuell.
- **Von außen geschaltet:** Wird das Licht ausgeschaltet, wechselt der Modus auf Aus. Wird es aus dem Aus eingeschaltet, wechselt er auf Manuell.
- **Von außen gedimmt:** Wird Helligkeit oder Farbtemperatur im Nachtlicht/Automatik geändert (Dimmschalter, App, Sprache), wechselt der Modus auf Manuell und das Licht bleibt an. Meldungen bis 5 s nach einer eigenen Schaltung zählen nicht.
- **Normalzustand:** Änderungen im Modus Manuell (Helligkeit, Farbtemperatur, RGB, WLED-Effekt) werden pro Lampe gemerkt und beim nächsten Manuell wiederhergestellt. Lampen, die dabei aus waren, bleiben aus.
- **WLED:** Lampen mit dem Effekt „Solid“ bekommen ihn beim Nachtlicht gesetzt, damit kein Effekt weiterläuft.
- **Nacht-Schalter** (optional, `input_boolean`/`binary_sensor`/`schedule`): Bestimmt statt des Sonnenuntergangs, wann Nacht ist. Abends vor der Nacht gilt dann Automatik.
- **Nachtruhe** (optional): Solange der Schalter an ist, schaltet Bewegung nichts ein. Kann derselbe Schalter wie der Nacht-Schalter sein.
- **Eigene Schaltungen** zählen nicht als „von außen“: Der Modus wird vor der Lichtaktion gesetzt, eigene Aufrufe tragen einen eigenen Kontext.

## Entitäten je Licht

- `select.<name>_mode`: Modus anzeigen und setzen. Attribute: Grund, Lampen, gespeicherter Normalzustand.
- `switch.<name>_motion`: Bewegungssteuerung an oder aus, etwa für Gäste oder eine Party.
- Event `room_nightlight_mode_changed` mit `from`, `to` und `reason`.

## Installation

HACS → Benutzerdefinierte Repositories → dieses Repo (Typ Integration) → installieren → neu starten → *Einstellungen → Geräte & Dienste → Integration hinzufügen → Room Night Light*.

## Entwicklung

Die Logik liegt in reinem Python: `engine.py` (Zustandsmaschine) und `memory.py` (Normalzustand). `controller.py` verbindet sie mit Home Assistant.

```bash
pip install -r requirements_test.txt && pytest       # alles
python3 scripts/run_pure_tests.py                    # nur Logik, ohne HA
```

Neue Version: `version` in `manifest.json` erhöhen und auf `main` pushen. Ein Workflow legt daraus Tag und Release an, und HACS zeigt das Update.
