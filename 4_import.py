#!/usr/bin/env python3
"""
4_import - die Portalhistorie nach Home Assistant einspielen
=============================================================

Version         : 1.12.0
Letzte Aenderung: 2026-09-02

Beschreibung
------------
Stufe 4 der Kette und die einzige, die etwas VERAENDERT. Sie schreibt die in
Stufe 3 erzeugten Stundenreihen als EXTERNE STATISTIKEN in die Langzeitdaten
von Home Assistant.

Warum externe Statistiken
-------------------------
Home Assistant kennt zwei Namensraeume. Entitaeten heissen sensor.name, mit
einem PUNKT; externe Statistiken heissen quelle:name, mit einem DOPPELPUNKT.
Sie koennen sich deshalb nicht in die Quere kommen. Alles, was dieses Skript
schreibt, traegt die Kennung

    sunnyportal2ha:<reihe>

und gehoert damit ausschliesslich diesem Projekt. Keine vorhandene Statistik
wird angefasst, keine Entitaet veraendert, keine Automatisierung beruehrt.
Das ist keine Nebensache, sondern der Grund fuer diesen Weg: Ein Import, der
sich nicht vollstaendig zuruecknehmen laesst, waere in einer produktiven
Installation nicht zu verantworten - und die meisten Leute haben keine
Testinstanz.

Zuruecknehmen laesst er sich mit  --entfernen.

Sicherungen
-----------
1. Ohne  --los  passiert NICHTS. Der Probelauf zeigt genau, was geschrieben
   wuerde, samt dem, was zu diesen Kennungen schon vorhanden ist.
2. Mit  --los  wird vor dem ersten Schreiben nachgefragt. Wer das in einem
   Skript nicht brauchen kann, nimmt  --ohne-rueckfrage.
3. Fremde Kennungen werden verweigert. Was nicht mit  sunnyportal2ha:
   anfaengt, schreibt dieses Skript nicht - auch dann nicht, wenn es so in
   einer Datei steht.

Trotzdem: **Vorher ein Backup von Home Assistant anlegen.** Nicht wegen dieses
Skripts, sondern weil man an der Statistikdatenbank generell nicht ohne
Rueckweg arbeiten sollte.

Voraussetzungen
---------------
    pip install requests websocket-client
    zugangsdaten.ini mit dem Abschnitt [homeassistant]
    3_transform.py muss gelaufen sein (Dateien in  import/ )

Aufruf
------
    python 4_import.py                    Probelauf, schreibt nichts
    python 4_import.py --los              wirklich schreiben
    python 4_import.py --nur pv_gesamt    nur eine Reihe
    python 4_import.py --entfernen        Probelauf des Loeschens
    python 4_import.py --entfernen --los  eigene Statistiken loeschen
    python 4_import.py --entfernen --nur pv_leistung --los
                                          eine einzelne Kennung loeschen
    python 4_import.py --suche net_power  Statistiken in HA suchen
    python 4_import.py --vergleich        HA und Portal gegenueberstellen
    python 4_import.py --bis 2026-08-28 --los    nur bis dahin importieren
    python 4_import.py --pruefen          nach dem Import gegenrechnen

Ablage
------
    import/sunnyportal2ha_*.json   die Eingangsdateien aus Stufe 3
    import/_import-log.txt         was wann geschrieben wurde, als Fliesstext
    import/_import-protokoll.json  dasselbe maschinenlesbar: Kennung, erste
                                   und letzte Stunde, Anzahl, Summenstand.
                                   Grundlage fuer spaetere Korrekturen.

Aenderungen
-----------
1.12.0 2026-09-02  Die Gegenprobe kennt jetzt auch die umgeleiteten Reihen.
                   Eine mit --ziel woandershin geschriebene Reihe fehlte unter
                   ihrer eigenen Kennung und wurde als vermisst gemeldet -
                   obwohl sie genau dort liegt, wo sie hin sollte. Das
                   Protokoll vermerkt dafuer jetzt die Herkunft.
1.11.1 2026-09-02  Bei --ziel auf eine Entitaet bleibt der Name leer - den
                   fuehrt Home Assistant selbst, und die vorhandenen Helfer
                   haben dort None stehen.
1.11.0 2026-09-02  Neu --ziel: schreibt EINE Reihe unter eine fremde
                   Kennung. Gedacht fuer die Helfer, die Home Assistant im
                   Energie-Dashboard selbst anlegt - sie sind Entitaeten,
                   haben keine Vorgeschichte und lassen sich nur so mit
                   Historie fuellen. Eigene Rueckfrage, eigener Vermerk im
                   Protokoll, und der ausdrueckliche Hinweis, dass
                   --entfernen das nicht zuruecknimmt. --suche zeigt jetzt
                   alle Felder einer Statistik, damit sich vorhandene
                   Metadaten nachbilden lassen statt sie zu raten.
1.10.0 2026-09-02  Neu --suche: zeigt zu einer Statistik in Home Assistant
                   Quelle, Einheit, Art und Zeitraum. Vor jedem Schreiben
                   unter einer fremden Kennung will man das wissen - der Name
                   allein sagt nicht, ob es eine externe Statistik ist oder
                   eine Entitaet, und davon haengt ab, ob man sie ueberhaupt
                   beschreiben darf.
1.9.0  2026-09-02  Der Import wartet am Ende, bis Home Assistant die Reihen
                   auch zeigt. import_statistics quittiert sofort, geschrieben
                   wird im Hintergrund - wer gleich danach nachliest, sieht
                   Reihen, die noch nicht bis ans Ende reichen oder noch gar
                   nicht in der Liste stehen. Das sah nach einem misslungenen
                   Import aus und war keiner: Beim ersten scharfen Lauf hat es
                   drei Anlaeufe gekostet, obwohl schon der erste vollstaendig
                   war.
1.8.0  2026-09-02  --entfernen --nur benennt die Kennungen unmittelbar.
                   Eine verwaiste Reihe hat keine Datei mehr; bisher fiel das
                   Loeschen dann auf "alle eigenen Kennungen" zurueck - genau
                   das Falsche.
1.7.0  2026-09-02  Die Gegenprobe beruecksichtigt den Schnitt. Sie verglich
                   die volle Datei gegen einen bewusst abgeschnittenen Import
                   und meldete als Fehlbetrag genau den Zeitraum, in dem die
                   eigenen Sensoren uebernehmen. Jetzt wird gegen den
                   Summenstand zu der Stunde verglichen, die im
                   Importprotokoll steht. Ausserdem nennt sie Reihen, die noch
                   fehlen, und die Zeitraeume kommen aus Tages- statt
                   Monatstoepfen - die Monatstoepfe zeigten irrefuehrende
                   Randdaten.
1.6.0  2026-09-02  Das Schreiben haelt jetzt einen Verbindungsabriss aus.
                   Home Assistant rechnet bei jedem Block die Statistik neu;
                   bei 5000 Werten am Stueck ist der Recorder so lange
                   beschaeftigt, dass die WebSocket-Verbindung wegfaellt.
                   Jetzt 1000er Bloecke mit Verschnaufpause, und bei einem
                   Abriss baut sich die Verbindung neu auf und der Block wird
                   wiederholt - was harmlos ist, weil gleiche Startzeitpunkte
                   ersetzt und nicht verdoppelt werden.
1.5.1  2026-09-02  Zwei Fehler beim ersten scharfen Lauf: Die
                   Protokollzeile griff auf die Summe zu, die eine
                   Leistungsreihe nicht hat - und weil der Abbruch mitten in
                   der Schleife kam, wurde das maschinenlesbare Protokoll gar
                   nicht geschrieben. Es entsteht jetzt auch dann, wenn der
                   Lauf scheitert; sonst steht etwas in Home Assistant, von
                   dem niemand mehr weiss, was und bis wohin.
1.5.0  2026-09-02  Kommt mit Leistungsreihen zurecht. Die tragen keine
                   Summe, sondern Stundenmittel mit Minimum und Maximum -
                   Vergleich und Gegenprobe lassen sie deshalb aus, die
                   Uebersicht zeigt statt der Summe die Spitzenleistung.
1.4.0  2026-09-02  Maschinenlesbares Importprotokoll. Haelt je Lauf fest,
                   welche Kennung von welcher bis zu welcher Stunde
                   geschrieben wurde, mit Anzahl und Summenstand - die
                   Grundlage dafuer, spaeter gezielt zu korrigieren, statt
                   sich auf das Gedaechtnis zu verlassen.
1.3.0  2026-09-02  Der Vergleich deckt jetzt auch die Geraetereihen ab. Das
                   Dashboard sagt nur, DASS zwei Solarsensoren eingetragen
                   sind, nicht welcher zu welchem Wechselrichter gehoert -
                   also wird jede Reihe gegen jeden Sensor gehalten und die
                   Zuordnung aus den Zahlen abgeleitet statt aus den Namen.
                   Dazu die Warnung, Summenreihe und Geraetereihen nicht
                   gleichzeitig ins Dashboard zu nehmen.
1.2.0  2026-09-02  Der Vergleich rechnet die Einheiten um und laesst die
                   angebrochenen Randtage weg. Home Assistant fuehrt Energie
                   je nach Geraet in Wh, kWh oder MWh - im selben Dashboard
                   nebeneinander; stumpf addiert ergab die PV-Erzeugung das
                   660-fache. Und in Ortszeit fallen die letzten Exportstunden
                   in den Folgetag, der dadurch fast leer aussieht.
1.1.0  2026-09-02  Vergleichsmodus: stellt HA und Portal im
                   Ueberschneidungszeitraum Tag fuer Tag gegenueber und
                   schlaegt den Tag vor, ab dem beide uebereinstimmen. Mit
                   --bis laesst sich der Import dort abschneiden, sodass
                   Portalhistorie und eigene Sensoren luecken- und
                   ueberschneidungsfrei aneinander anschliessen.
1.0.0  2026-09-02  Erste Fassung
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime, timedelta

import ha

__version__ = "1.12.0"
__stand__ = "2026-09-02"

HIER = os.path.dirname(os.path.abspath(__file__))
QUELLE = os.path.join(HIER, "import")
LOG_DATEI = os.path.join(QUELLE, "_import-log.txt")

# Maschinenlesbares Gedaechtnis der Importe. Wer spaeter gezielt korrigieren
# will - Werte ausnullen, einen Zeitraum ueberschreiben, einen Lauf
# zuruecknehmen -, braucht genau diese Angaben: welche Kennung, welche erste
# und letzte Stunde, wie viele Werte, welcher Summenstand am Ende. Aus dem
# Fliesstext eines Logs laesst sich das nicht zuverlaessig herauslesen.
PROTOKOLL = os.path.join(QUELLE, "_import-protokoll.json")

# Die eigene Kennung. Alles, was nicht so anfaengt, wird nicht geschrieben.
PRAEFIX = "sunnyportal2ha:"

# Wie viele Stundenwerte in einer Nachricht. Klein halten: Home Assistant
# schreibt jeden Block in die Datenbank und rechnet dabei die Statistik neu.
# Bei grossen Bloecken ist der Recorder so lange beschaeftigt, dass die
# WebSocket-Verbindung abreisst - und dann steht man mit halb geschriebenen
# Reihen da. Lieber viele kleine Nachrichten mit Verschnaufpause.
BLOCK = 1_000
PAUSE = 0.3         # Sekunden zwischen zwei Bloecken
VERSUCHE = 4        # Versuche je Block, bevor aufgegeben wird


class Sitzung:
    """
    Eine HA-Verbindung, die sich nach einem Abriss selbst neu aufbaut.

    Der Import dauert Minuten, und in dieser Zeit kann die Verbindung
    wegfallen - besonders wenn der Recorder gerade eine grosse Reihe
    verarbeitet. Weil recorder/import_statistics Zeilen mit gleichem
    Startzeitpunkt ersetzt statt sie zu verdoppeln, ist ein wiederholter
    Block harmlos.
    """

    def __init__(self, timeout=180):
        self.timeout = timeout
        self.v = None

    def __enter__(self):
        self.neu()
        return self

    def neu(self):
        self.schliessen()
        self.v = ha.Verbindung(timeout=self.timeout).__enter__()
        return self.v

    def schliessen(self):
        if self.v is not None:
            try:
                self.v.__exit__()
            except Exception:
                pass
            self.v = None

    def __exit__(self, *_):
        self.schliessen()

    def befehl(self, typ, **felder):
        return self.v.befehl(typ, **felder)


# Welche Reihe von uns welcher Rolle im Energie-Dashboard entspricht. Die
# Sensoren dazu stehen nicht hier, sondern werden aus der HA-Konfiguration
# gelesen - jede Anlage hat andere.
ROLLEN = {
    "pv_gesamt":   [("solar", "stat_energy_from")],
    "netzbezug":   [("grid", "stat_energy_from")],
    "einspeisung": [("grid", "stat_energy_to")],
}


def dashboard_sensoren(v):
    """{Reihe: [Sensor, ...]} aus der Energie-Konfiguration von Home Assistant."""
    prefs = v.befehl("energy/get_prefs") or {}
    zuordnung = {}
    for reihe, muster in ROLLEN.items():
        for eintrag in prefs.get("energy_sources") or []:
            for typ, feld in muster:
                if eintrag.get("type") == typ and eintrag.get(feld):
                    zuordnung.setdefault(reihe, []).append(eintrag[feld])
    return zuordnung


# Auf kWh umrechnen. Home Assistant fuehrt Energie je nach Geraet in Wh, kWh
# oder MWh - im selben Dashboard nebeneinander. Wer das uebersieht, addiert
# Wh zu kWh und bekommt Abweichungen im Faktor Hundert bis Tausend, die nach
# einem Datenfehler aussehen und keiner sind.
NACH_KWH = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}


def einheiten(v):
    """{Statistik: Faktor auf kWh}."""
    faktoren = {}
    for e in ha.statistik_kennungen(v):
        einheit = (e.get("display_unit_of_measurement")
                   or e.get("unit_of_measurement") or "")
        faktoren[e["statistic_id"]] = NACH_KWH.get(einheit)
    return faktoren


def tageswerte_ha(v, sensoren, von, bis, faktoren):
    """{Tag: kWh} - die Summe mehrerer Sensoren je Tag, auf kWh gebracht."""
    if not sensoren:
        return {}, []
    roh = ha.statistiken(v, sensoren, von, bis, "day", ["change"])
    tage, unklar = {}, []
    for kennung, eintraege in roh.items():
        faktor = faktoren.get(kennung)
        if faktor is None:
            unklar.append(kennung)
            continue
        for e in eintraege:
            zeit = ha.zeitstempel(e)
            wert = e.get("change")
            if zeit is None or wert is None:
                continue
            tag = zeit.astimezone().date()
            tage[tag] = tage.get(tag, 0.0) + wert * faktor
    return tage, unklar


def tageswerte_datei(werte):
    """
    {Tag: (kWh, Stundenzahl)} aus einer Importdatei.

    Die Stundenzahl wird mitgefuehrt, weil der erste und der letzte Tag
    angebrochen sind: In Ortszeit fallen die letzten Exportstunden schon in
    den Folgetag. Ein angebrochener Tag darf den Vergleich nicht entscheiden.
    """
    tage, vorher = {}, None
    for e in werte:
        zeit = datetime.fromisoformat(e["start"]).astimezone()
        summe = e["sum"]
        if vorher is not None:
            menge, anzahl = tage.get(zeit.date(), (0.0, 0))
            tage[zeit.date()] = (menge + summe - vorher, anzahl + 1)
        vorher = summe
    return tage


def geraete_zuordnen(v, dateien, sensoren, faktoren):
    """
    Welche unserer Geraetereihen zu welchem Sensor gehoert.

    Das Energie-Dashboard sagt nur, DASS zwei Solarsensoren eingetragen sind,
    nicht welcher zu welchem Wechselrichter gehoert. Ueber Namen zu raten
    waere brechreif - der eine heisst 'STP10.0-3SE-40 681', der andere
    'sn_3015596681'. Also wird gerechnet: Jede unserer Reihen wird gegen jeden
    Sensor gehalten, und es gewinnt die kleinste mittlere Abweichung. Wenn die
    Zahlen zusammenpassen, gehoeren sie zusammen.
    """
    kandidaten = sensoren.get("pv_gesamt") or []
    geraete = [(meta, werte) for _, meta, werte in dateien
               if meta["statistic_id"].split(":", 1)[1] not in ROLLEN
               and meta.get("has_sum")]
    if len(kandidaten) < 2 or not geraete:
        return {}

    werte_ha = {}
    for kennung in kandidaten:
        tage, _ = tageswerte_ha(v, [kennung], datetime(2000, 1, 1),
                                datetime.now() + timedelta(days=1), faktoren)
        werte_ha[kennung] = tage

    print("\n" + "-" * 96)
    print("Geraetereihen: welche gehoert zu welchem Sensor?")
    print("-" * 96)
    print(f"   {'unsere Reihe':<32}" +
          "".join(f"{k.split('.')[-1][:26]:>28}" for k in kandidaten))

    zuordnung, belegt = {}, set()
    for meta, werte in geraete:
        unsere = tageswerte_datei(werte)
        zeile, bewertung = [], {}
        for kennung in kandidaten:
            erster_ha = min(werte_ha[kennung]) if werte_ha[kennung] else None
            gemeinsam = [t for t in set(werte_ha[kennung]) & set(unsere)
                         if t != erster_ha and unsere[t][1] >= 24]
            if not gemeinsam:
                zeile.append("-"); continue
            abw = [abs(werte_ha[kennung][t] - unsere[t][0]) /
                   max(unsere[t][0], 0.001) for t in gemeinsam]
            mittel = 100 * sum(abw) / len(abw)
            bewertung[kennung] = mittel
            zeile.append(f"{mittel:.1f} %")
        print(f"   {meta['statistic_id'].split(':', 1)[1]:<32}" +
              "".join(f"{z:>28}" for z in zeile))
        if bewertung:
            beste = min(bewertung, key=bewertung.get)
            if bewertung[beste] < 10 and beste not in belegt:
                zuordnung[meta["statistic_id"]] = beste
                belegt.add(beste)

    if zuordnung:
        print("\n   Zuordnung nach den Zahlen:")
        for unsere_reihe, kennung in zuordnung.items():
            print(f"      {unsere_reihe}  ->  {kennung}")
    else:
        print("\n   Keine eindeutige Zuordnung - die Abweichungen sind zu gross.")
    return zuordnung


def schnitt_vorschlagen(vergleich, mindest_kwh=0.5, anteil=0.03):
    """
    Der erste Tag, ab dem HA und Portal uebereinstimmen - und ab dem sie es
    auch bleiben. Ein einzelner zufaellig passender Tag genuegt nicht.
    """
    tage = sorted(vergleich)
    for nr, tag in enumerate(tage):
        if all(abs(vergleich[t][2]) <= max(mindest_kwh, anteil * abs(vergleich[t][1]))
               for t in tage[nr:]):
            return tag
    return None


def log(zeile=""):
    try:
        os.makedirs(QUELLE, exist_ok=True)
        with open(LOG_DATEI, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {zeile}\n")
    except OSError:
        pass


def protokoll_ergaenzen(eintrag):
    """Einen Lauf an das maschinenlesbare Protokoll anhaengen."""
    laeufe = []
    if os.path.exists(PROTOKOLL):
        try:
            with open(PROTOKOLL, encoding="utf-8") as f:
                laeufe = json.load(f).get("laeufe") or []
        except (ValueError, OSError):
            laeufe = []
    laeufe.append(eintrag)
    os.makedirs(QUELLE, exist_ok=True)
    with open(PROTOKOLL, "w", encoding="utf-8") as f:
        json.dump({"laeufe": laeufe}, f, indent=1, ensure_ascii=False)


def umgeleitete():
    """{unsere Reihe: fremde Kennung} - was per --ziel woandershin ging."""
    if not os.path.exists(PROTOKOLL):
        return {}
    try:
        with open(PROTOKOLL, encoding="utf-8") as f:
            laeufe = json.load(f).get("laeufe") or []
    except (ValueError, OSError):
        return {}
    ziele = {}
    for lauf in laeufe:
        for r in lauf.get("reihen") or []:
            if r.get("fremde_kennung") and r.get("herkunft"):
                ziele[r["herkunft"]] = r["statistic_id"]
    return ziele


def letzte_importe():
    """
    {Kennung: letzte geschriebene Stunde} aus dem Importprotokoll.

    Ohne das vergleicht die Gegenprobe die volle Datei gegen einen bewusst
    abgeschnittenen Import - und meldet als Fehlbetrag genau den Zeitraum, in
    dem die eigenen Sensoren uebernehmen sollen.
    """
    if not os.path.exists(PROTOKOLL):
        return {}
    try:
        with open(PROTOKOLL, encoding="utf-8") as f:
            laeufe = json.load(f).get("laeufe") or []
    except (ValueError, OSError):
        return {}
    stand = {}
    for lauf in laeufe:
        if lauf.get("aktion") == "entfernt":
            for r in lauf.get("reihen") or []:
                stand.pop(r.get("statistic_id"), None)
            continue
        for r in lauf.get("reihen") or []:
            if r.get("letzte_stunde"):
                stand[r["statistic_id"]] = r["letzte_stunde"]
    return stand


def summe_bis(werte, letzte_stunde):
    """Summenstand der Datei zu genau dem Zeitpunkt, bis zu dem importiert wurde."""
    if not letzte_stunde:
        return werte[-1].get("sum")
    for e in werte:
        if e["start"] == letzte_stunde:
            return e.get("sum")
    return werte[-1].get("sum")


def dateien_lesen(nur=None):
    """Die Eingangsdateien aus Stufe 3, geprueft."""
    ergebnis = []
    for pfad in sorted(glob.glob(os.path.join(QUELLE, "sunnyportal2ha_*.json"))):
        with open(pfad, encoding="utf-8") as f:
            inhalt = json.load(f)
        meta = inhalt.get("metadata") or {}
        werte = inhalt.get("stats") or []
        kennung = meta.get("statistic_id", "")
        if not kennung.startswith(PRAEFIX):
            print(f"   UEBERSPRUNGEN: {os.path.basename(pfad)} - Kennung "
                  f"'{kennung}' gehoert nicht zu diesem Projekt.")
            continue
        if nur and kennung.split(":", 1)[1] not in nur:
            continue
        if not werte:
            print(f"   UEBERSPRUNGEN: {os.path.basename(pfad)} - keine Werte.")
            continue
        ergebnis.append((pfad, meta, werte))
    return ergebnis


def vorhandenes(v, kennungen):
    """Was HA zu diesen Kennungen schon hat: (erster, letzter, Summe)."""
    bekannt = {e["statistic_id"] for e in ha.statistik_kennungen(v)}
    gefunden = {}
    for kennung in kennungen:
        if kennung not in bekannt:
            continue
        werte = ha.statistiken(v, [kennung], datetime(2000, 1, 1),
                               datetime.now() + timedelta(days=1),
                               "day", ["sum"]).get(kennung) or []
        if werte:
            gefunden[kennung] = (ha.zeitstempel(werte[0]),
                                 ha.zeitstempel(werte[-1]),
                                 werte[-1].get("sum"))
        else:
            gefunden[kennung] = (None, None, None)
    return gefunden


def schreiben(sitzung, meta, werte, trocken, fremd_erlaubt=False):
    """Eine Reihe in Bloecken schreiben. trocken=True sendet nichts."""
    if not meta["statistic_id"].startswith(PRAEFIX) and not fremd_erlaubt:
        raise ValueError(f"Fremde Kennung: {meta['statistic_id']}")
    geschrieben = 0
    for anfang in range(0, len(werte), BLOCK):
        block = werte[anfang:anfang + BLOCK]
        if not trocken:
            for versuch in range(1, VERSUCHE + 1):
                try:
                    sitzung.befehl(
                        "recorder/import_statistics",
                        metadata={k: w for k, w in meta.items()
                                  if not k.startswith("_")},
                        stats=block)
                    break
                except Exception as e:
                    if versuch == VERSUCHE:
                        raise
                    print(f"\n      Verbindung verloren ({type(e).__name__}), "
                          f"neuer Anlauf {versuch + 1}/{VERSUCHE} ...")
                    time.sleep(3 * versuch)
                    sitzung.neu()
            time.sleep(PAUSE)
        geschrieben += len(block)
        print(f"      {geschrieben:>6} von {len(werte)}", end="\r", flush=True)
    print(" " * 40, end="\r")
    return geschrieben


def sichtbarer_stand(v, erwartet):
    """{Kennung: sichtbar?} - reicht die Reihe in HA schon bis zur letzten Stunde?"""
    bekannt = {e["statistic_id"] for e in ha.statistik_kennungen(v)}
    stand = {}
    for kennung, letzte in erwartet.items():
        if kennung not in bekannt:
            stand[kennung] = False
            continue
        werte = ha.statistiken(v, [kennung], datetime(2000, 1, 1),
                               datetime.now() + timedelta(days=1),
                               "day").get(kennung) or []
        if not werte:
            stand[kennung] = False
            continue
        gesehen = ha.zeitstempel(werte[-1])
        ziel = datetime.fromisoformat(letzte)
        stand[kennung] = (gesehen is not None
                          and gesehen.astimezone().date() >= ziel.astimezone().date())
    return stand


def warten_bis_sichtbar(sitzung, erwartet, sekunden=300):
    """
    Nach dem Schreiben nachfassen, bis Home Assistant es auch zeigt.

    recorder/import_statistics quittiert sofort; geschrieben wird im
    Hintergrund vom Recorder. Wer gleich danach nachliest, sieht eine Reihe,
    die noch nicht bis ans Ende reicht - oder die noch gar nicht in der Liste
    steht. Das sieht aus wie ein misslungener Import und ist keiner; wer dann
    erneut importiert, wartet nur auf andere Weise.
    """
    begonnen = time.monotonic()
    while True:
        try:
            stand = sichtbarer_stand(sitzung, erwartet)
        except Exception:
            sitzung.neu()
            stand = {k: False for k in erwartet}
        fehlen = sorted(k for k, sichtbar in stand.items() if not sichtbar)
        if not fehlen:
            print(" " * 78, end="\r")
            return []
        if time.monotonic() - begonnen > sekunden:
            print(" " * 78, end="\r")
            return fehlen
        print(f"   Home Assistant schreibt noch - {len(fehlen)} von "
              f"{len(erwartet)} Reihen ausstehend, seit "
              f"{int(time.monotonic() - begonnen)} s ...", end="\r", flush=True)
        time.sleep(5)


def bestaetigung_einholen(anzahl, punkte):
    print("\n" + "!" * 96)
    print(f"Es werden {anzahl} Reihen mit zusammen {punkte} Stundenwerten in die")
    print("Langzeitstatistik von Home Assistant geschrieben.")
    print("")
    print("Geschrieben wird ausschliesslich unter eigenen Kennungen "
          f"({PRAEFIX}...).")
    print("Vorhandene Entitaeten und Statistiken bleiben unberuehrt, und der")
    print("Import laesst sich mit  --entfernen  vollstaendig zuruecknehmen.")
    print("")
    print("Trotzdem: Gibt es ein aktuelles Backup dieser HA-Installation?")
    print("!" * 96)
    try:
        antwort = input("Weiter? Bitte 'ja' eingeben: ").strip().lower()
    except EOFError:
        antwort = ""
    return antwort == "ja"


def vergleich_zeigen(v, dateien):
    """
    HA gegen Portal im Ueberschneidungszeitraum, Tag fuer Tag.

    Verglichen werden nicht einzelne Kennungen, sondern ROLLEN: Was das
    Energie-Dashboard als PV-Erzeugung fuehrt, sind hier zwei Sensoren, bei
    uns eine Reihe. Erst ihre Summe ist vergleichbar.
    """
    sensoren = dashboard_sensoren(v)
    if not sensoren:
        print("\nIm Energie-Dashboard ist nichts eingetragen - kein Vergleich "
              "moeglich.")
        return 1
    faktoren = einheiten(v)

    vorschlaege = {}
    for _, meta, werte in dateien:
        reihe = meta["statistic_id"].split(":", 1)[1]
        # Leistungsreihen tragen keine Summe und lassen sich nicht als
        # Tagesenergie gegenrechnen.
        if reihe not in sensoren or not meta.get("has_sum"):
            continue
        unsere = tageswerte_datei(werte)
        ha_alle, unklar = tageswerte_ha(v, sensoren[reihe], datetime(2000, 1, 1),
                                        datetime.now() + timedelta(days=1),
                                        faktoren)
        print(f"\n{reihe}   <-  " + ", ".join(sensoren[reihe]))
        for kennung in unklar:
            print(f"   UNKLARE EINHEIT, nicht mitgerechnet: {kennung}")

        # Angebrochene Raender aussen vor: der erste Tag, an dem HA ueberhaupt
        # etwas hat, und jeder Tag, fuer den uns nicht 24 Stunden vorliegen.
        erster_ha = min(ha_alle) if ha_alle else None
        gemeinsam = sorted(tag for tag in set(ha_alle) & set(unsere)
                           if tag != erster_ha and unsere[tag][1] >= 24)
        if not gemeinsam:
            print("   keine vollstaendigen gemeinsamen Tage.")
            continue

        print(f"   {'Tag':<12}{'Home Assistant':>16}{'Portal':>12}"
              f"{'Abweichung':>13}{'':>7}%")
        vergleich = {}
        for tag in gemeinsam:
            a, b = ha_alle[tag], unsere[tag][0]
            vergleich[tag] = (a, b, a - b)
            anteil = 100 * (a - b) / b if b else 0
            print(f"   {str(tag):<12}{a:>16.2f}{b:>12.2f}{a - b:>13.2f}"
                  f"{anteil:>8.1f}")
        schnitt = schnitt_vorschlagen(vergleich)
        vorschlaege[reihe] = schnitt
        if schnitt:
            print(f"   -> ab {schnitt} stimmen beide ueberein und bleiben es")
        else:
            print("   -> keine Uebereinstimmung; hier waere ein Schnitt geraten")

    geraete_zuordnen(v, dateien, sensoren, faktoren)

    gueltig = [s for s in vorschlaege.values() if s]
    print("\n" + "=" * 96)
    if gueltig:
        schnitt = max(gueltig)
        print(f"VORSCHLAG: Schnitt zum {schnitt}")
        print("Alle Reihen stimmen ab diesem Tag ueberein. Davor traegt das")
        print("Portal die Geschichte, ab da die eigenen Sensoren.")
        print("")
        print(f"   python 4_import.py --bis {schnitt} --los")
        print("")
        print("Danach beide Reihen im Energie-Dashboard derselben Rolle")
        print("zuordnen: Home Assistant addiert sie, und weil sie sich nicht")
        print("ueberschneiden, entsteht ein durchgehender Verlauf.")
        print("")
        print("ACHTUNG bei der Erzeugung: ENTWEDER die Summenreihe pv_gesamt")
        print("ODER die beiden Geraetereihen eintragen, niemals beides - sonst")
        print("zaehlt das Dashboard die Erzeugung doppelt.")
    else:
        print("Kein Schnitt gefunden. Die Zahlen weichen ueberall voneinander ab -")
        print("bitte die Tabelle oben ansehen, bevor irgendetwas geschrieben wird.")
    print("=" * 96)
    return 0


def main():
    p = argparse.ArgumentParser(
        description="Die Portalhistorie als externe Statistiken nach HA schreiben",
        epilog="Ohne --los passiert nichts.")
    p.add_argument("--los", action="store_true",
                   help="wirklich schreiben (ohne diesen Schalter nur Probelauf)")
    p.add_argument("--nur", nargs="+", metavar="REIHE",
                   help="nur diese Reihen, z. B. pv_gesamt einspeisung")
    p.add_argument("--entfernen", action="store_true",
                   help="die eigenen externen Statistiken wieder loeschen")
    p.add_argument("--pruefen", action="store_true",
                   help="nur gegenrechnen, was in HA steht")
    p.add_argument("--suche", metavar="TEXT",
                   help="Statistiken in HA suchen und ihre Eckdaten zeigen - "
                        "liest nur, schreibt nichts")
    p.add_argument("--vergleich", action="store_true",
                   help="HA und Portal im Ueberschneidungszeitraum vergleichen "
                        "und einen Schnitt vorschlagen")
    p.add_argument("--bis", metavar="JJJJ-MM-TT",
                   help="nur bis zu diesem Tag importieren (ausschliesslich) - "
                        "der Schnitt aus --vergleich")
    p.add_argument("--ziel", metavar="STATISTIC_ID",
                   help="AUSNAHME: die mit --nur gewaehlte Reihe unter DIESER "
                        "fremden Kennung schreiben. Nur mit genau einer Reihe, "
                        "und mit eigener Rueckfrage - --entfernen nimmt das "
                        "nicht zurueck.")
    p.add_argument("--ohne-rueckfrage", action="store_true",
                   help="die Sicherheitsabfrage ueberspringen")
    args = p.parse_args()

    print("=" * 96)
    print(f"Schritt 4 - Import  (Version {__version__}, {__stand__})")
    if not args.los:
        print("PROBELAUF - es wird nichts geschrieben. Mit --los wird es ernst.")
    print("=" * 96)

    dateien = dateien_lesen(set(args.nur) if args.nur else None)
    if not dateien and not (args.entfernen or args.pruefen):
        print(f"\nKeine Dateien in {QUELLE}. Erst  python 3_transform.py  laufen "
              f"lassen.")
        return 1

    try:
        with Sitzung() as v:
            # ---- Suchen -----------------------------------------------------
            # Vor jedem Schreiben unter einer fremden Kennung will man wissen,
            # was dort ueberhaupt liegt: Quelle, Einheit, Zeitraum. Der Name
            # allein sagt es nicht - eine Kennung mit Doppelpunkt kann eine
            # externe Statistik sein oder eine Entitaet mit ungluecklichem
            # Namen, und davon haengt ab, ob man sie beschreiben darf.
            if args.suche:
                treffer = [e for e in ha.statistik_kennungen(v)
                           if args.suche.lower() in e["statistic_id"].lower()]
                print(f"\n{len(treffer)} Statistiken enthalten "
                      f"'{args.suche}':\n")
                for e in sorted(treffer, key=lambda e: e["statistic_id"]):
                    print(f"   {e['statistic_id']}")
                    # Vollstaendig, nicht ausgewaehlt: Wer die Metadaten einer
                    # vorhandenen Statistik nachbilden will, braucht alle
                    # Felder - welche das sind, aendert sich mit HA-Versionen.
                    for feld, wert in sorted(e.items()):
                        if feld != "statistic_id":
                            print(f"      {feld:<32}{wert!r}")
                    werte = ha.statistiken(
                        v, [e["statistic_id"]], datetime(2000, 1, 1),
                        datetime.now() + timedelta(days=1),
                        "day").get(e["statistic_id"]) or []
                    if werte:
                        print(f"      Daten von {str(ha.zeitstempel(werte[0]))[:10]}"
                              f" bis {str(ha.zeitstempel(werte[-1]))[:10]}, "
                              f"{len(werte)} Tage")
                    else:
                        print("      noch keine Daten")
                if not treffer:
                    print("   (nichts gefunden)")
                return 0

            kennungen = [meta["statistic_id"] for _, meta, _ in dateien]
            if args.entfernen and args.nur:
                # Beim Loeschen benennt --nur die Kennungen unmittelbar, ohne
                # Umweg ueber die Dateien. Sonst liesse sich eine verwaiste
                # Reihe nicht entfernen - zu ihr gibt es ja keine Datei mehr,
                # und der Rueckfall auf "alle eigenen Kennungen" waere hier
                # genau das Falsche.
                kennungen = [PRAEFIX + n for n in args.nur]
            elif args.entfernen or args.pruefen:
                kennungen = kennungen or [
                    e["statistic_id"] for e in ha.statistik_kennungen(v)
                    if e["statistic_id"].startswith(PRAEFIX)]

            da = vorhandenes(v, kennungen)
            print(f"\nIn Home Assistant vorhanden: {len(da)} von "
                  f"{len(kennungen)} Kennungen")
            for kennung, (erster, letzter, summe) in sorted(da.items()):
                print(f"   {kennung:<46}{str(erster)[:10]} bis "
                      f"{str(letzter)[:10]}   Summe {summe}")
            if not da:
                print("   (keine - der Import legt sie neu an)")

            # ---- Loeschen ---------------------------------------------------
            if args.entfernen:
                if not da:
                    print("\nNichts zu loeschen.")
                    return 0
                print(f"\nZu loeschen: {len(da)} Statistiken")
                if not args.los:
                    print("\nProbelauf - es wurde nichts geloescht.")
                    return 0
                v.befehl("recorder/clear_statistics",
                         statistic_ids=sorted(da))
                log(f"geloescht: {', '.join(sorted(da))}")
                protokoll_ergaenzen({
                    "zeitpunkt": datetime.now().astimezone().isoformat(),
                    "version": __version__, "aktion": "entfernt",
                    "reihen": [{"statistic_id": k} for k in sorted(da)]})
                print("Geloescht. Die Entitaeten von Home Assistant sind "
                      "unberuehrt geblieben.")
                return 0

            # ---- Vergleich ---------------------------------------------------
            if args.vergleich:
                return vergleich_zeigen(v, dateien)

            # ---- Gegenrechnen -----------------------------------------------
            if args.pruefen:
                stand = letzte_importe()
                print(f"\n{'Reihe':<40}{'bis':<12}{'aus Datei':>12}{'in HA':>12}"
                      f"{'Abweichung':>12}")
                print("-" * 96)
                alles_gut = True
                for _, meta, werte in dateien:
                    if not meta.get("has_sum"):
                        continue
                    kennung = meta["statistic_id"]
                    grenze = stand.get(kennung)
                    soll = summe_bis(werte, grenze)
                    ist = (da.get(kennung) or (None, None, None))[2]
                    bis_text = (grenze or werte[-1]["start"])[:10]
                    if ist is None:
                        print(f"{kennung:<40}{bis_text:<12}{soll:>12.1f}"
                              f"{'fehlt':>12}")
                        alles_gut = False
                        continue
                    abw = ist - soll
                    if abs(abw) > 0.5:
                        alles_gut = False
                    print(f"{kennung:<40}{bis_text:<12}{soll:>12.1f}{ist:>12.1f}"
                          f"{abw:>12.1f}")
                ziele = umgeleitete()
                umgezogen = [(meta["statistic_id"], ziele[meta["statistic_id"]])
                             for _, meta, _ in dateien
                             if meta["statistic_id"] in ziele]
                if umgezogen:
                    print("\nUnter fremder Kennung geschrieben (--ziel):")
                    for herkunft, ziel in umgezogen:
                        print(f"   {herkunft}")
                        print(f"      -> {ziel}")
                fehlend = [meta["statistic_id"] for _, meta, _ in dateien
                           if meta["statistic_id"] not in da
                           and meta["statistic_id"] not in ziele]
                if fehlend:
                    print("\nNoch nicht in Home Assistant:")
                    for k in fehlend:
                        print(f"   {k}")
                    print("Ein erneuter Lauf holt sie nach.")
                elif alles_gut:
                    print("\nAlles angekommen - Datei und Home Assistant stimmen "
                          "ueberein.")
                if not stand:
                    print("\nHinweis: Kein Importprotokoll gefunden. Verglichen "
                          "wurde deshalb gegen das Dateiende;")
                    print("bei einem abgeschnittenen Import ist die Abweichung "
                          "dann genau der weggelassene Teil.")
                return 0

            # ---- Schreiben ---------------------------------------------------
            if args.ziel:
                if len(dateien) != 1:
                    print("\n--ziel schreibt unter eine fremde Kennung und "
                          "verlangt deshalb genau EINE Reihe.")
                    print("Bitte zusaetzlich  --nur <reihe>  angeben. Zur "
                          "Auswahl stehen:")
                    for _, meta, _ in dateien:
                        print(f"   {meta['statistic_id'].split(':', 1)[1]}")
                    return 1
                pfad, meta, werte = dateien[0]
                meta = dict(meta)
                herkunft = meta["statistic_id"]
                meta["_herkunft"] = herkunft
                meta["statistic_id"] = args.ziel
                # Eine Entitaetskennung gehoert dem Recorder, nicht uns.
                meta["source"] = ("recorder" if "." in args.ziel
                                  and ":" not in args.ziel else PRAEFIX[:-1])
                if meta["source"] == "recorder":
                    # Den Namen fuehrt Home Assistant bei einer Entitaet selbst -
                    # die vorhandenen Helfer haben dort None stehen. Unseren
                    # Dateinamen daruebersetzen hiesse, ihn umzubenennen.
                    meta["name"] = None
                dateien = [(pfad, meta, werte)]
                print("\n" + "!" * 96)
                print("AUSNAHME: Es wird unter einer FREMDEN Kennung "
                      "geschrieben.")
                print(f"   Quelle : {herkunft}")
                print(f"   Ziel   : {args.ziel}")
                print(f"   Quelle im Kopf: {meta['source']!r}")
                print("")
                print("Das ist der einzige Fall, den  --entfernen  NICHT "
                      "zuruecknimmt.")
                print("Der Rueckweg fuehrt ueber Home Assistant selbst: die "
                      "Statistik dort loeschen")
                print("oder den Helfer neu anlegen. Bitte vorher pruefen, dass "
                      "die Kennung leer ist -")
                print("dafuer gibt es  --suche.")
                print("!" * 96)

            if args.bis:
                grenze = datetime.fromisoformat(args.bis).astimezone()
                gekuerzt = []
                for pfad, meta, werte in dateien:
                    behalten = [e for e in werte
                                if datetime.fromisoformat(e["start"]).astimezone()
                                < grenze]
                    if behalten:
                        gekuerzt.append((pfad, meta, behalten))
                weg = sum(len(w) for _, _, w in dateien) - \
                    sum(len(w) for _, _, w in gekuerzt)
                print(f"\nSchnitt bei {args.bis}: {weg} Stundenwerte danach "
                      f"bleiben aussen vor - dort uebernehmen die Sensoren.")
                dateien = gekuerzt

            punkte = sum(len(w) for _, _, w in dateien)
            print(f"\n{'Reihe':<46}{'Stunden':>9}  {'von':<12}{'bis':<12}"
                  f"{'kWh / Spitze W':>15}")
            print("-" * 96)
            for _, meta, werte in dateien:
                if meta.get("has_sum"):
                    kennzahl = f"{werte[-1]['sum']:.1f} kWh"
                else:
                    kennzahl = f"{max(e['max'] for e in werte):.0f} W"
                print(f"{meta['statistic_id']:<46}{len(werte):>9}  "
                      f"{werte[0]['start'][:10]:<12}{werte[-1]['start'][:10]:<12}"
                      f"{kennzahl:>15}")

            if not args.los:
                print(f"\nProbelauf. Mit  --los  werden {punkte} Stundenwerte "
                      f"geschrieben.")
                return 0

            if not args.ohne_rueckfrage and not bestaetigung_einholen(
                    len(dateien), punkte):
                print("\nAbgebrochen. Es wurde nichts geschrieben.")
                return 130

            log(f"Import beginnt - {len(dateien)} Reihen, {punkte} Werte")
            print()
            eintrag = {"zeitpunkt": datetime.now().astimezone().isoformat(),
                       "version": __version__,
                       "schnitt": args.bis,
                       "reihen": []}
            # Das Protokoll wird auf jeden Fall geschrieben - auch wenn hier
            # etwas schiefgeht. Sonst steht hinterher etwas in Home Assistant,
            # von dem niemand mehr weiss, was und bis wohin.
            try:
                for _, meta, werte in dateien:
                    print(f"   {meta['statistic_id']} ...")
                    anzahl = schreiben(v, meta, werte, trocken=False,
                                       fremd_erlaubt=bool(args.ziel))
                    ende = (f"Summe {werte[-1]['sum']}" if meta.get("has_sum")
                            else f"Spitze {max(e['max'] for e in werte)} W")
                    log(f"   {meta['statistic_id']}  {anzahl} Werte  "
                        f"{werte[0]['start']} bis {werte[-1]['start']}  {ende}")
                    eintrag["reihen"].append({
                        "statistic_id": meta["statistic_id"],
                        "fremde_kennung": bool(args.ziel),
                        "herkunft": meta.get("_herkunft"),
                        "erste_stunde": werte[0]["start"],
                        "letzte_stunde": werte[-1]["start"],
                        "anzahl": anzahl,
                        "summe_am_ende": werte[-1].get("sum"),
                        "einheit": meta.get("unit_of_measurement")})
                    print(f"   {meta['statistic_id']}  {anzahl} Werte geschrieben")
            finally:
                if eintrag["reihen"]:
                    protokoll_ergaenzen(eintrag)

            print("\nWarten, bis Home Assistant fertig geschrieben hat ...")
            offen = warten_bis_sichtbar(
                v, {r["statistic_id"]: r["letzte_stunde"]
                    for r in eintrag["reihen"]})
            if offen:
                print("   Nach der Wartezeit noch nicht vollstaendig sichtbar:")
                for k in offen:
                    print(f"      {k}")
                print("   Das heisst nicht, dass etwas fehlt - der Recorder")
                print("   arbeitet weiter. Spaeter  --pruefen  aufrufen, statt")
                print("   erneut zu importieren.")
            else:
                print("   Alle Reihen sind vollstaendig sichtbar.")

            print("\n" + "=" * 96)
            print("Fertig. Gegenrechnen mit:  python 4_import.py --pruefen")
            print("Zuruecknehmen mit       :  python 4_import.py --entfernen --los")
            print(f"Was geschrieben wurde   :  {PROTOKOLL}")
            print("=" * 96)
            log("Import beendet.")
            return 0

    except ha.HAFehler as e:
        print(f"\nABBRUCH: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
