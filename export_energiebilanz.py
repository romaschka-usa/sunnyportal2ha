#!/usr/bin/env python3
"""
sma_bilanz_export - Energiebilanz einer SMA-Anlage monatsweise als CSV
=======================================================================

Version         : 1.0.0
Letzte Aenderung: 2026-09-01

Beschreibung
------------
Holt die vollstaendige Historie der Energiebilanz aus dem klassischen SMA
Sunny Portal und legt sie als CSV ab - eine Datei je Monat, in voller
Viertelstundenaufloesung. Enthalten sind alle anlagenweiten Groessen:

    PV-Erzeugung | Gesamtverbrauch | Direktverbrauch
    Netzbezug    | Netzeinspeisung | Batterieladung und -entladung

Das Skript ist an keine bestimmte Anlage gebunden. Anlagenkennung und
Betriebszeitraum werden beim Start aus dem Portal gelesen; es laeuft mit
jedem Sunny-Portal-Konto, dessen Anlage eine Energiebilanz-Seite hat (also
mit Sunny Home Manager).

Voraussetzungen
---------------
    Python 3.9 oder neuer
    pip install requests
    zugangsdaten.ini neben dem Skript (wird beim ersten Start angelegt)

Aufruf
------
    python export_energiebilanz.py                  fehlende Monate holen
    python export_energiebilanz.py --neu            alles neu laden
    python export_energiebilanz.py --nur-pruefen    nur den Bestand berichten
    python export_energiebilanz.py --von 2025-01    ab einem bestimmten Monat

Ablage
------
    bilanz/JJJJ-MM.csv        eine Datei je Monat, unveraendert wie geliefert
    bilanz/_protokoll.json    Pruefwerte und Luecken je Monat
    bilanz/_verdaechtig/      aussortierte Dateien, zum Nachsehen

Wie es arbeitet
---------------
Die Energiebilanz-Seite laedt ihre Diagramme ueber eine eigene Schnittstelle
nach. Der Export macht dasselbe in zwei Schritten:

    1. GET /PortalCharts/Core/PortalChartsAPI.aspx?id=mainChart&xf=..&xt=..
       setzt den Zeitraum in der Sitzung (die Antwort ist ein Bild)
    2. GET /Templates/DownloadDiagram.aspx?down=homanEnergyRedesign&...
       liefert die Daten des zuletzt gesetzten Diagramms als CSV

Genau daraus folgt die wichtigste Fehlerquelle: Schlaegt Schritt 1 fehl,
bleibt das vorherige Diagramm stehen und Schritt 2 liefert den Vormonat ein
zweites Mal - ohne Fehlermeldung. Deshalb wird jeder Monat geprueft:

    * Die Kopfzeile muss die Spalte Netzeinspeisung enthalten.
    * Die Zahl der Tage muss zum Kalender passen.
    * Die Pruefsumme darf nicht mit der eines anderen Monats uebereinstimmen.
    * Die Diagrammantwort muss groesser als 8 kB sein (ein leeres Bild des
      Portals ist rund 3,2 kB gross).

Faellt eine Pruefung durch, wird bis zu dreimal neu angefordert; danach wird
der Monat nicht gespeichert, damit ein erneuter Start ihn nachholt.

Tage ohne Werte werden NICHT als Fehler behandelt, sondern benannt. Solche
Luecken gibt es im Portal wirklich, und beim spaeteren Import muessen sie als
fehlend gelten und nicht als Null.

Beim Umrechnen beachten
-----------------------
    * Die Einheit wechselt je nach Monat zwischen [W] und [kW]. Sie steht in
      der Kopfzeile und muss dort gelesen werden.
    * Die CSV enthaelt kein Datum, nur die Uhrzeit - und zwar das ENDE des
      Intervalls. Ein Tag laeuft von 00:15 bis 00:00.
    * Zahlen im deutschen Format mit Komma, Zeitspalte im Excel-Format.
    * "Direktverbrauch" kommt zweimal als Spaltenname vor.

Aenderungen
-----------
1.0.0  2026-09-01  Erste veroeffentlichte Fassung. Anlagendaten werden aus
                   dem Portal gelesen statt fest verdrahtet; Luecken werden
                   ausgewiesen statt abgelehnt.
"""

__version__ = "1.0.0"
__stand__ = "2026-09-01"

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import date, datetime, timedelta

from portal import (PORTAL, PortalFehler, anlage_ermitteln, anmelden,
                    ist_anmeldeseite)

HIER = os.path.dirname(os.path.abspath(__file__))
AUSGABE = os.path.join(HIER, "bilanz")
VERDAECHTIG = os.path.join(AUSGABE, "_verdaechtig")
PROTOKOLL = os.path.join(AUSGABE, "_protokoll.json")

SEITE = f"{PORTAL}/FixedPages/HoManEnergyRedesign.aspx"
CHART_API = f"{PORTAL}/PortalCharts/Core/PortalChartsAPI.aspx"
DOWNLOAD = f"{PORTAL}/Templates/DownloadDiagram.aspx?down=homanEnergyRedesign&chartId=mainChart"

# Der erste Tag mit Daten wird beim Start aus dem Portal gelesen (MinDate der
# Anlage). Nichts ist fest verdrahtet - das Skript laeuft mit jedem Konto.
ANLAGENSTART = None

# Ein leeres Diagramm des Portals ist rund 3155 Byte gross. Alles deutlich
# darueber ist ein echtes Bild - auch ein duenn besetzter Monat (2023-04 kam
# mit 16204 B, 2023-07 mit 15264 B, und beide sind gueltig).
MIN_DIAGRAMM = 8_000

# Wenig gefuellte Monate werden NICHT mehr abgelehnt. Juli 2023 und Maerz 2026
# sind nachweislich echte Datenluecken bei SMA - bestaetigt durch die
# unabhaengig geholten Rohdaten aus GetMeasuredValues. Ein duenner Monat wird
# uebernommen und die Luecke im Bericht ausgewiesen.
LUECKE_MELDEN = 0.90

VERSUCHE = 3
PAUSE = 3.0


# ------------------------------------------------------------------ Kalender

def monatsanfang(d):
    return d.replace(day=1)


def naechster_monat(d):
    return (d.replace(day=28) + timedelta(days=8)).replace(day=1)


def monate(von, bis):
    m = monatsanfang(von)
    while m <= bis:
        yield m
        m = naechster_monat(m)


def zeitraum(m, heute):
    """Der tatsaechlich vorhandene Zeitraum eines Monats - Anlagenstart und heute begrenzen ihn."""
    von = max(m, ANLAGENSTART)
    bis = min(naechster_monat(m), heute)
    return von, bis


def unix(d):
    return int(datetime(d.year, d.month, d.day).timestamp())


def datei(m):
    return os.path.join(AUSGABE, f"{m.year}-{m.month:02d}.csv")


# ------------------------------------------------------------------- Pruefen

def zahl(x):
    x = x.strip().strip('"')
    if not x:
        return None
    try:
        return float(x.replace(",", "."))
    except ValueError:
        return None


def csv_pruefen(text, erwartete_tage):
    """Liefert eine Bewertung der CSV: Zeilen, Tage, gefuellte Zeilen, Einheit."""
    zeilen = text.splitlines()
    if len(zeilen) < 2 or "Netzeinspeisung" not in zeilen[0]:
        return {"ok": False, "grund": "keine Kopfzeile mit Netzeinspeisung",
                "zeilen": len(zeilen) - 1}

    daten = [z.split(";") for z in zeilen[1:] if z.strip()]
    tage = len(re.findall(r'"=""00:00"""', text))
    gefuellt = sum(1 for r in daten if any(zahl(c) is not None for c in r[1:]))
    anteil = gefuellt / len(daten) if daten else 0
    einheit = (re.search(r"\[(k?W)\]", zeilen[0]) or [None, "?"])[1]

    # Tagesweise durchzaehlen, damit Luecken benannt werden koennen statt nur
    # als Prozentzahl aufzutauchen.
    leere_tage = []
    for nr in range(tage):
        block = daten[nr * 96:(nr + 1) * 96]
        if block and not any(zahl(c) is not None for r in block for c in r[1:]):
            leere_tage.append(nr + 1)

    e = {"zeilen": len(daten), "tage": tage, "gefuellt": gefuellt,
         "anteil": round(anteil, 3), "einheit": einheit,
         "erwartete_tage": erwartete_tage, "leere_tage": leere_tage,
         "pruefsumme": hashlib.md5(text.encode("utf-8")).hexdigest()[:12]}

    # Abgelehnt wird nur, was nachweislich falsch ist: fehlende Kopfzeile,
    # falsche Tageszahl, oder eine Datei, die es schon einmal gibt. Ein duenn
    # besetzter Monat ist eine Luecke in den Daten, kein Uebertragungsfehler.
    if tage != erwartete_tage:
        e.update(ok=False, grund=f"{tage} Tage statt {erwartete_tage}")
    else:
        e.update(ok=True, grund="")
        if anteil < LUECKE_MELDEN:
            e["hinweis"] = f"{len(leere_tage)} Tage ohne Werte"
    return e


def bestand_pruefen(heute):
    """Prueft vorhandene Dateien; fehlerhafte wandern nach _verdaechtig."""
    if not os.path.isdir(AUSGABE):
        return {}, []
    befund, aussortiert = {}, []
    pruefsummen = {}

    for m in monate(ANLAGENSTART, heute):
        p = datei(m)
        if not os.path.exists(p):
            continue
        schluessel = f"{m.year}-{m.month:02d}"
        von, bis = zeitraum(m, heute)
        text = open(p, encoding="utf-8-sig").read()
        e = csv_pruefen(text, (bis - von).days)

        # Doppelgaenger: gleiche Pruefsumme wie ein anderer Monat
        if e.get("pruefsumme") in pruefsummen:
            e.update(ok=False, grund=f"identisch mit {pruefsummen[e['pruefsumme']]}")
        else:
            pruefsummen[e["pruefsumme"]] = schluessel

        befund[schluessel] = e
        if not e["ok"]:
            os.makedirs(VERDAECHTIG, exist_ok=True)
            shutil.move(p, os.path.join(VERDAECHTIG, os.path.basename(p)))
            aussortiert.append((schluessel, e["grund"]))
    return befund, aussortiert


# -------------------------------------------------------------------- Laden

def monat_holen(s, m, heute, vorherige_pruefsummen):
    von, bis = zeitraum(m, heute)
    erwartet = (bis - von).days
    if erwartet <= 0:
        return {"status": "ausserhalb"}

    letzter = None
    for versuch in range(1, VERSUCHE + 1):
        r = s.get(CHART_API,
                  params={"id": "mainChart", "xf": unix(von), "xt": unix(bis),
                          "t": int(time.time() * 1000)},
                  headers={"Referer": SEITE, "X-Requested-With": "XMLHttpRequest"},
                  timeout=180)
        diagramm = len(r.content)

        if diagramm < MIN_DIAGRAMM:
            letzter = {"status": "fehlgeschlagen", "diagramm_bytes": diagramm,
                       "grund": f"Diagrammantwort nur {diagramm} B", "versuch": versuch}
            time.sleep(PAUSE)
            continue

        rd = s.get(DOWNLOAD, headers={"Referer": SEITE}, timeout=180)
        if ist_anmeldeseite(rd.text):
            raise PortalFehler("Anmeldeseite beim Download - Sitzung abgelaufen.")

        e = csv_pruefen(rd.text, erwartet)
        e["diagramm_bytes"] = diagramm
        e["versuch"] = versuch

        if e.get("pruefsumme") in vorherige_pruefsummen:
            e.update(ok=False,
                     grund=f"identisch mit {vorherige_pruefsummen[e['pruefsumme']]}")

        if e["ok"]:
            os.makedirs(AUSGABE, exist_ok=True)
            with open(datei(m), "w", encoding="utf-8-sig", newline="") as f:
                f.write(rd.text)
            vorherige_pruefsummen[e["pruefsumme"]] = f"{m.year}-{m.month:02d}"
            e["status"] = "ok"
            return e

        e["status"] = "unbrauchbar"
        letzter = e
        time.sleep(PAUSE)

    return letzter or {"status": "unbrauchbar", "grund": "unbekannt"}


# ---------------------------------------------------------------------- Main

def main():
    p = argparse.ArgumentParser(description="Energiebilanz monatsweise exportieren und pruefen")
    p.add_argument("--neu", action="store_true", help="alles neu laden")
    p.add_argument("--nur-pruefen", action="store_true", help="nichts laden, nur berichten")
    p.add_argument("--von", help="erster Monat JJJJ-MM")
    p.add_argument("--bis", help="letzter Monat JJJJ-MM")
    args = p.parse_args()

    global ANLAGENSTART
    heute = date.today()
    print("=" * 78)
    print(f"Energiebilanz aus dem Sunny Portal - Version {__version__} ({__stand__})")
    print("=" * 78)

    try:
        s = anmelden()
        anlage = anlage_ermitteln(s)
    except PortalFehler as e:
        print(f"\nABBRUCH: {e}")
        return 1

    ANLAGENSTART = datetime.strptime(anlage["min_date"], "%Y-%m-%d").date()
    print(f"\nAnlage    : {anlage['plant_oid']}")
    print(f"Daten ab  : {ANLAGENSTART}")

    print("\nVorhandene Dateien pruefen ...")
    befund, aussortiert = bestand_pruefen(heute)
    gut = sum(1 for e in befund.values() if e["ok"])
    print(f"   {gut} in Ordnung, {len(aussortiert)} aussortiert")
    for schluessel, grund in aussortiert:
        print(f"      {schluessel}  ->  {grund}")
    if aussortiert:
        print(f"   Die aussortierten Dateien liegen in {VERDAECHTIG}")

    if args.nur_pruefen:
        print("\nNur-Pruefen-Modus, es wird nichts geladen.")
        return 0

    if args.neu:
        for m in monate(ANLAGENSTART, heute):
            if os.path.exists(datei(m)):
                os.remove(datei(m))
        befund = {}

    s.get(f"{PORTAL}/Templates/Start.aspx", timeout=45)
    r = s.get(SEITE, timeout=120)
    if ist_anmeldeseite(r.text):
        print("Energiebilanz liefert die Anmeldeseite - Abbruch.")
        return 1

    pruefsummen = {e["pruefsumme"]: k for k, e in befund.items()
                   if e.get("ok") and e.get("pruefsumme")}

    erster, letzter = ANLAGENSTART, heute
    if args.von:
        erster = max(erster, datetime.strptime(args.von + "-01", "%Y-%m-%d").date())
    if args.bis:
        letzter = min(letzter, datetime.strptime(args.bis + "-01", "%Y-%m-%d").date())
    liste = [m for m in monate(erster, letzter) if not os.path.exists(datei(m))]
    print(f"\nZu laden: {len(liste)} Monate\n")
    if not liste:
        print("Nichts zu tun - alle Monate liegen geprueft vor.")
        return 0

    print(f"{'Monat':<9}{'Zeilen':>8}{'Tage':>6}{'erw':>5}{'gef.':>7}{'Einh':>6}{'Diagr.':>9}   Ergebnis")
    print("-" * 78)

    prot = {}
    if os.path.exists(PROTOKOLL):
        try:
            prot = json.load(open(PROTOKOLL, encoding="utf-8"))
        except ValueError:
            prot = {}

    geladen = schlecht = 0
    begonnen = time.monotonic()

    for m in liste:
        schluessel = f"{m.year}-{m.month:02d}"
        try:
            e = monat_holen(s, m, heute, pruefsummen)
        except PortalFehler as ex:
            if "Anmeldeseite" in str(ex):
                print(f"{schluessel:<9}  Sitzung abgelaufen, melde neu an ...")
                s = anmelden(leise=True)
                s.get(SEITE, timeout=120)
                e = monat_holen(s, m, heute, pruefsummen)
            else:
                print(f"{schluessel:<9}  FEHLER: {ex}")
                schlecht += 1
                continue
        except Exception as ex:
            print(f"{schluessel:<9}  FEHLER {type(ex).__name__}: {ex}")
            schlecht += 1
            continue

        prot[schluessel] = e
        with open(PROTOKOLL, "w", encoding="utf-8") as f:
            json.dump(prot, f, indent=2, ensure_ascii=False)

        if e["status"] == "ok":
            geladen += 1
            zusatz = ""
            if e.get("hinweis"):
                zusatz = f"   LUECKE: {e['hinweis']} ({e['leere_tage'][:6]}…)" \
                    if len(e["leere_tage"]) > 6 else f"   LUECKE: Tage {e['leere_tage']}"
            elif e["versuch"] > 1:
                zusatz = f"   (Versuch {e['versuch']})"
            print(f"{schluessel:<9}{e['zeilen']:>8}{e['tage']:>6}{e['erwartete_tage']:>5}"
                  f"{e['anteil']:>7.0%}{e['einheit']:>6}{e['diagramm_bytes']:>9}   ok{zusatz}")
        elif e["status"] == "ausserhalb":
            print(f"{schluessel:<9}   ausserhalb des Anlagenzeitraums")
        else:
            schlecht += 1
            print(f"{schluessel:<9}   NICHT UEBERNOMMEN: {e.get('grund','')}")

    print("\n" + "=" * 78)
    print(f"geladen     : {geladen} Monate")
    print(f"nicht ok    : {schlecht}")
    print(f"Laufzeit    : {int(time.monotonic() - begonnen)} s")
    print(f"\nCSV-Dateien : {AUSGABE}")

    # Luecken ueber den gesamten Bestand zusammenfassen - die brauchen wir
    # spaeter beim Import, damit fehlende Tage nicht als Nullwerte gelten.
    luecken = []
    for k in sorted(prot):
        e = prot[k]
        for tag in e.get("leere_tage") or []:
            luecken.append(f"{k}-{tag:02d}")
    if luecken:
        print(f"\nTage ohne Werte im Portal ({len(luecken)}):")
        for i in range(0, len(luecken), 10):
            print("   " + "  ".join(luecken[i:i + 10]))
        print("   Das sind Luecken in SMAs Daten, keine Uebertragungsfehler.")

    if schlecht:
        print("\nNicht uebernommene Monate haben keine Datei - erneut starten holt sie nach.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
