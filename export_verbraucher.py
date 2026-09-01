#!/usr/bin/env python3
"""
export_verbraucher - Verbrauchsdaten je Geraet aus dem Sunny Portal
====================================================================

Version         : 1.0.0
Letzte Aenderung: 2026-09-01

Beschreibung
------------
Zweites Standbein neben export_energiebilanz.py. Die Energiebilanz liefert
die Anlagensummen; dieses Skript liefert die Kurven JE VERBRAUCHER - also
was Waermepumpe, Wallbox, Heizstab und die uebrigen vom Sunny Home Manager
erfassten Geraete einzeln gezogen haben.

Grundlage ist die Verbraucherbilanz-Seite und ihr Datenendpunkt

    /Homan/ConsumerBalance/GetMeasuredValues

Der nimmt nur EINEN Tag je Anfrage an, deshalb laeuft der Export tageweise
und braucht fuer mehrere Jahre entsprechend lange. Die Antworten werden
unveraendert und gzip-gepackt abgelegt; umgerechnet wird spaeter.

Welche Aufloesung was liefert
-----------------------------
    15min   die anlagenweiten Reihen UND die Verbraucher
     5min   ausschliesslich die Verbraucher, dafuer dreimal so fein
            (und ueberraschenderweise schneller, weil es die Rohaufloesung ist)

Fuer die Anlagensummen ist export_energiebilanz.py der bessere Weg - der holt
einen ganzen Monat auf einmal und kennt zusaetzlich die Netzeinspeisung.
Dieses Skript nimmt man fuer die Geraetedetails.

Voraussetzungen
---------------
    Python 3.9 oder neuer
    pip install requests
    zugangsdaten.ini neben dem Skript (wird beim ersten Start angelegt)

Aufruf
------
    python export_verbraucher.py                    15min, alle fehlenden Tage
    python export_verbraucher.py --intervall 5min   feine Verbraucherkurven
    python export_verbraucher.py --von 2025-01-01   Zeitraum eingrenzen
    python export_verbraucher.py --neu              vorhandene Dateien neu laden

Ablage
------
    rohdaten/JJJJ/JJJJ-MM-TT_<aufloesung>.json.gz
    export_protokoll.json

Abbruch mit Strg+C ist gefahrlos: Fertige Tage werden beim naechsten Start
uebersprungen.

Aenderungen
-----------
1.0.0  2026-09-01  Erste veroeffentlichte Fassung. Prueft, ob die
                   anlagenweiten Reihen tatsaechlich gefuellt sind, statt
                   jede nicht-leere Antwort als Erfolg zu werten.
"""

__version__ = "1.0.0"
__stand__ = "2026-09-01"

import argparse
import gzip
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta

from portal import (PortalFehler, ZeitUeberschritten, anlage_ermitteln,
                        anmelden, messwerte)

HIER = os.path.dirname(os.path.abspath(__file__))
ROHDATEN = os.path.join(HIER, "rohdaten")
PROTOKOLL = os.path.join(HIER, "export_protokoll.json")
ALTES_LOG = os.path.join(HIER, "export_log.json")

TIMEOUT = 180
PAUSE = 0.4

ANLAGENREIHEN = ("PvGeneration", "TotalConsumption", "ExternalSupply",
                 "BatteryCharging", "BatteryDischarging", "BasicLoad")


# ---------------------------------------------------------------- Hilfsmittel

def ziel(tag, intervall):
    return os.path.join(ROHDATEN, str(tag.year), f"{tag.isoformat()}_{intervall}.json.gz")


def gz_schreiben(pfad, text):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with gzip.open(pfad, "wt", encoding="utf-8") as f:
        f.write(text)


def gz_lesen(pfad):
    with gzip.open(pfad, "rt", encoding="utf-8") as f:
        return json.load(f)


def json_laden(pfad, vorgabe):
    if os.path.exists(pfad):
        try:
            with open(pfad, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            pass
    return vorgabe


def protokoll_schreiben(p):
    with open(PROTOKOLL, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)


def anlagenreihen_punkte(daten):
    """Punkte der anlagenweiten Reihen. 0 bedeutet: die eigentlichen Messwerte fehlen."""
    if not isinstance(daten, dict):
        return 0
    for k in ANLAGENREIHEN:
        v = daten.get(k)
        if isinstance(v, list) and v:
            return len(v)
    return 0


def verbraucher_punkte(daten):
    if not isinstance(daten, dict):
        return 0
    for c in daten.get("Consumers") or []:
        v = c.get("Consume")
        if isinstance(v, list) and v:
            return len(v)
    return 0


def brauchbar(daten, intervall):
    """
    15min muss die anlagenweiten Reihen liefern - sonst ist der Tag wertlos.
    5min liefert konstruktionsbedingt nur Verbraucherkurven; dort genuegen die.
    """
    if intervall == "5min":
        return verbraucher_punkte(daten) > 0
    return anlagenreihen_punkte(daten) > 0


def dauer_lesbar(sekunden):
    sekunden = int(sekunden)
    if sekunden < 90:
        return f"{sekunden} s"
    if sekunden < 5400:
        return f"{sekunden // 60} min"
    return f"{sekunden / 3600:.1f} h"


# ------------------------------------------------------------------ Migration

def altbestand_umbenennen():
    """
    Dateien der ersten Fassung (JJJJ-MM-TT.json.gz, ohne Aufloesung im Namen)
    bekommen die Aufloesung angehaengt. Welche es war, steht im alten
    Protokoll; fehlt es, wird sie am Inhalt erkannt.
    """
    if not os.path.isdir(ROHDATEN):
        return 0
    altlog = json_laden(ALTES_LOG, {}).get("tage", {})
    muster = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json\.gz$")
    umbenannt = 0

    for jahr in sorted(os.listdir(ROHDATEN)):
        ordner = os.path.join(ROHDATEN, jahr)
        if not os.path.isdir(ordner):
            continue
        for name in sorted(os.listdir(ordner)):
            m = muster.match(name)
            if not m:
                continue
            tag = m.group(1)
            intervall = (altlog.get(tag) or {}).get("intervall")
            alt = os.path.join(ordner, name)
            if not intervall:
                try:
                    d = gz_lesen(alt)
                    intervall = "15min" if anlagenreihen_punkte(d) else "5min"
                except (OSError, ValueError):
                    continue
            neu = os.path.join(ordner, f"{tag}_{intervall}.json.gz")
            if os.path.exists(neu):
                continue
            os.rename(alt, neu)
            umbenannt += 1

    if umbenannt:
        print(f"   {umbenannt} Dateien der ersten Fassung umbenannt "
              f"(Aufloesung steht jetzt im Dateinamen).")
    return umbenannt


# --------------------------------------------------------------- Kernvorgang

class Exporteur:
    def __init__(self, sitzung, oid):
        self.s = sitzung
        self.oid = oid
        self.neuanmeldungen = 0

    def _abfrage(self, start, ende, intervall):
        try:
            return messwerte(self.s, self.oid, start, ende, intervall, timeout=TIMEOUT)
        except PortalFehler as e:
            if "Anmeldeseite" not in str(e):
                raise
            print("\n      Sitzung abgelaufen, melde neu an ...", end=" ")
            self.s = anmelden(leise=True)
            self.neuanmeldungen += 1
            return messwerte(self.s, self.oid, start, ende, intervall, timeout=TIMEOUT)

    def tag_holen(self, tag, intervall):
        start = tag.isoformat()
        ende = (tag + timedelta(days=1)).isoformat()
        begonnen = time.monotonic()
        try:
            daten, roh, sek = self._abfrage(start, ende, intervall)
        except ZeitUeberschritten as e:
            return {"status": "zeitlimit", "hinweis": str(e),
                    "sekunden": round(time.monotonic() - begonnen, 1)}
        except PortalFehler as e:
            return {"status": "fehler", "hinweis": str(e),
                    "sekunden": round(time.monotonic() - begonnen, 1)}

        if daten is None:
            return {"status": "kein_json", "zeichen": len(roh),
                    "anfang": roh[:200], "sekunden": round(sek, 1)}

        anlage = anlagenreihen_punkte(daten)
        verbraucher = verbraucher_punkte(daten)

        if not brauchbar(daten, intervall):
            return {"status": "leer", "anlagenreihen": anlage,
                    "verbraucher": verbraucher, "sekunden": round(sek, 1)}

        gz_schreiben(ziel(tag, intervall), roh)
        return {"status": "ok", "anlagenreihen": anlage, "verbraucher": verbraucher,
                "zeichen": len(roh), "sekunden": round(sek, 1)}

    def tageswerte(self, erster, letzter):
        alles = {}
        von = erster
        while von <= letzter:
            bis = min(von + timedelta(days=365), letzter + timedelta(days=1))
            print(f"   Tageswerte {von} bis {bis} ...", end=" ", flush=True)
            try:
                daten, roh, sek = self._abfrage(von.isoformat(), bis.isoformat(), "day")
                if daten is None:
                    print("kein JSON")
                else:
                    alles[f"{von}_{bis}"] = daten
                    print(f"ok ({sek:.1f} s)")
            except PortalFehler as e:
                print(f"Fehler: {e}")
            von = bis
        if alles:
            gz_schreiben(os.path.join(ROHDATEN, "_tageswerte.json.gz"),
                         json.dumps(alles, ensure_ascii=False))
        return len(alles)


# ---------------------------------------------------------------------- Main

def main():
    p = argparse.ArgumentParser(description="Vollexport der SMA-Historie aus dem Sunny Portal")
    p.add_argument("--intervall", default="15min", choices=("15min", "5min"),
                   help="Vorgabe 15min - nur diese Aufloesung enthaelt die Anlagenreihen")
    p.add_argument("--von", help="Startdatum JJJJ-MM-TT")
    p.add_argument("--bis", help="Enddatum JJJJ-MM-TT")
    p.add_argument("--neu", action="store_true", help="vorhandene Dateien neu laden")
    p.add_argument("--mit-tageswerten", action="store_true",
                   help="die Tageswert-Kontrollreihe erneut holen")
    args = p.parse_args()
    intervall = args.intervall

    print("=" * 74)
    print(f"SMA Sunny Portal - Vollexport ({intervall})")
    print("=" * 74)

    print("\nBestand pruefen ...")
    altbestand_umbenennen()

    try:
        s = anmelden()
        anlage = anlage_ermitteln(s)
    except PortalFehler as e:
        print(f"\nABBRUCH: {e}")
        return 1

    oid = anlage["plant_oid"]
    erster = datetime.strptime(anlage["min_date"], "%Y-%m-%d").date()
    letzter = min(datetime.strptime(anlage["max_date"], "%Y-%m-%d").date(),
                  date.today() - timedelta(days=1))
    if args.von:
        erster = max(erster, datetime.strptime(args.von, "%Y-%m-%d").date())
    if args.bis:
        letzter = min(letzter, datetime.strptime(args.bis, "%Y-%m-%d").date())
    if erster > letzter:
        print("\nDer gewaehlte Zeitraum ist leer.")
        return 1

    gesamt = (letzter - erster).days + 1
    offen = sum(1 for i in range(gesamt)
                if args.neu or not os.path.exists(ziel(erster + timedelta(days=i), intervall)))

    print(f"\nAnlage    : {oid}")
    print(f"Zeitraum  : {erster} bis {letzter}  ({gesamt} Tage)")
    print(f"Zu laden  : {offen} Tage in {intervall}")
    print(f"Ablage    : {ROHDATEN}")

    prot = json_laden(PROTOKOLL, {"anlage": None, "tage": {}})
    prot["anlage"] = anlage
    prot["zuletzt"] = datetime.now().isoformat(timespec="seconds")

    exp = Exporteur(s, oid)

    if args.mit_tageswerten or not os.path.exists(os.path.join(ROHDATEN, "_tageswerte.json.gz")):
        print("\nKontrollreihe (Tageswerte):")
        exp.tageswerte(datetime.strptime(anlage["min_date"], "%Y-%m-%d").date(), letzter)

    print("\nTag fuer Tag. Abbruch mit Strg+C ist gefahrlos - fertige Tage")
    print("werden beim naechsten Start uebersprungen.\n")

    begonnen = time.monotonic()
    geladen = uebersprungen = fehlerhaft = leer = 0
    zeiten = []
    nr = 0

    tag = erster
    try:
        while tag <= letzter:
            nr += 1
            if not args.neu and os.path.exists(ziel(tag, intervall)):
                uebersprungen += 1
                tag += timedelta(days=1)
                continue

            print(f"[{nr:>4}/{gesamt}] {tag} ", end="", flush=True)
            e = exp.tag_holen(tag, intervall)
            prot["tage"].setdefault(tag.isoformat(), {})[intervall] = e

            if e["status"] == "ok":
                geladen += 1
                zeiten.append(e["sekunden"])
                verbleibend = sum(
                    1 for i in range(nr, gesamt)
                    if not os.path.exists(ziel(erster + timedelta(days=i), intervall))
                ) if nr % 25 == 0 else max(0, offen - geladen)
                schnitt = sum(zeiten[-40:]) / len(zeiten[-40:]) + PAUSE
                print(f"Anlage {e['anlagenreihen']:>3}  Verbraucher {e['verbraucher']:>3}  "
                      f"{e['sekunden']:>5.1f}s   noch ca. {dauer_lesbar(verbleibend * schnitt)}")
            elif e["status"] == "leer":
                leer += 1
                print(f"LEER (Anlagenreihen {e['anlagenreihen']}, "
                      f"Verbraucher {e['verbraucher']}) - nicht gespeichert")
            else:
                fehlerhaft += 1
                print(f"{e['status'].upper()}  {str(e.get('hinweis',''))[:55]}")

            if nr % 10 == 0 or e["status"] != "ok":
                protokoll_schreiben(prot)

            time.sleep(PAUSE)
            tag += timedelta(days=1)

    except KeyboardInterrupt:
        print("\n\nAbgebrochen. Der Fortschritt ist gesichert - einfach erneut starten.")
    finally:
        protokoll_schreiben(prot)

    print("\n" + "=" * 74)
    print(f"geladen        : {geladen}")
    print(f"uebersprungen  : {uebersprungen} (waren schon da)")
    print(f"ohne Daten     : {leer}")
    print(f"fehlerhaft     : {fehlerhaft}")
    if exp.neuanmeldungen:
        print(f"Neuanmeldungen : {exp.neuanmeldungen}")
    print(f"Laufzeit       : {dauer_lesbar(time.monotonic() - begonnen)}")
    print(f"\nRohdaten in    : {ROHDATEN}")
    print(f"Protokoll in   : {PROTOKOLL}")
    if fehlerhaft:
        print("\nFehlerhafte Tage haben keine Datei bekommen - ein erneuter Start holt sie nach.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
