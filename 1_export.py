#!/usr/bin/env python3
"""
1_export - alle Daten aus dem Sunny Portal holen
=================================================

Version         : 2.10.0
Letzte Aenderung: 2026-09-02

Beschreibung
------------
Stufe 1 der Kette. Fasst die drei bisherigen Exportskripte zusammen und holt
sie wahlweise einzeln oder in einem Rutsch - mit mehreren gleichzeitigen
Verbindungen, denn das Portal erlaubt parallele Anmeldungen.

    bilanz          Anlagensummen: PV-Erzeugung, Gesamtverbrauch,
                    Direktverbrauch, Netzbezug, NETZEINSPEISUNG, Batterie
                    Quelle: Energiebilanz-Seite, ein Monat je Abfrage,
                    Leistungsmittelwerte je Viertelstunde

    bilanz_tage     dieselben Reihen als Zaehleraenderung je TAG in kWh
    bilanz_monate   dieselben Reihen je MONAT, ein Jahr je Abfrage
    bilanz_jahre    dieselben Reihen je JAHR, eine einzige Abfrage

                    Die drei groben Stufen sind keine Wiederholung, sondern
                    eine zweite Sicht: Feinkurve und Zaehleraenderung
                    entstehen im Portal getrennt und weichen voneinander ab.
                    Im Juli 2023 stehen im Tageszaehler rund 300 kWh, in der
                    Viertelstundenkurve nur 92. Sie sind billig und dienen als
                    Pruefsumme fuer jede Ebene.

    wechselrichter  Ertrag je Geraet plus Anlagensumme
                    Quelle: Analyse-Seite, ein Monat je Abfrage

    wechselrichter_tage / _monate / _jahre
                    dasselbe in den groben Stufen

    bilanz_luecken / wechselrichter_luecken
                    laedt einzelne TAGE nach, an denen die Monatsabfrage
                    keine Feinkurve hergab, der Tageszaehler aber Energie
                    ausweist. Diese Tage sind im Portal vorhanden - die
                    Monatsabfrage gibt sie nur nicht her. Setzt voraus, dass
                    die zugehoerige _tage-Quelle schon geholt wurde.

    verbraucher     Verbrauch je angeschlossenem Geraet
                    Quelle: Verbraucherbilanz, ein TAG je Abfrage - deshalb
                    dauert dieser Export am laengsten und profitiert am
                    meisten von parallelen Verbindungen

Voraussetzungen
---------------
    Python 3.9 oder neuer
    pip install requests
    zugangsdaten.ini neben dem Skript

Parallele Verbindungen
----------------------
In zugangsdaten.ini:

    [export]
    parallel = 4
    timeout = 300

Jeder Arbeiter meldet sich eigenstaendig an und arbeitet eine eigene
Portalsitzung ab. Vier bis sechs sind ein vernuenftiger Bereich; mehr belastet
den Server eines Herstellers ohne viel zu bringen. Ohne Eintrag werden drei
Verbindungen verwendet.

Aufruf
------
    python 1_export.py alles                 alle Quellen nacheinander
    python 1_export.py bilanz                nur die Energiebilanz
    python 1_export.py bilanz_tage           nur deren Tageswerte
    python 1_export.py bilanz_monate         nur deren Monatswerte
    python 1_export.py bilanz_jahre          nur deren Jahreswerte
    python 1_export.py wechselrichter        nur die Geraetereihen
    python 1_export.py wechselrichter_tage   nur deren Tageswerte
    python 1_export.py bilanz_luecken        fehlende Feintage nachladen
    python 1_export.py verbraucher           nur die Verbraucher

    python 1_export.py alles --von 2025-01   Zeitraum eingrenzen
    python 1_export.py bilanz --nur-pruefen  vorhandene Dateien pruefen
    python 1_export.py bilanz --neu          alles neu laden
    python 1_export.py                     dasselbe wie "alles"
    python 1_export.py alles --parallel 6  Vorgabe aus der INI uebergehen
    python 1_export.py alles --timeout 240 Zeitbudget je Aufgabe

Ablage
------
    bilanz/JJJJ-MM.csv                 Anlagensummen, Viertelstunden
    bilanz_tage/JJJJ-MM.csv            Anlagensummen, Tageszaehler
    bilanz_monate/JJJJ.csv             Anlagensummen, Monatszaehler
    bilanz_jahre/gesamt.csv            Anlagensummen, Jahreszaehler
    wechselrichter/JJJJ-MM.csv         Ertrag je Geraet, Viertelstunden
    wechselrichter_tage/JJJJ-MM.csv    Ertrag je Geraet, Tageszaehler
    wechselrichter_monate/JJJJ.csv     Ertrag je Geraet, Monatszaehler
    wechselrichter_jahre/gesamt.csv    Ertrag je Geraet, Jahreszaehler
    bilanz/luecken/JJJJ-MM-TT.csv      einzeln nachgeladene Feintage
    wechselrichter/luecken/...         dasselbe je Geraet
    rohdaten/JJJJ/JJJJ-MM-TT_*.json.gz Verbraucher, gzip-gepackt
    <ordner>/_protokoll.json           Pruefwerte und Luecken
    <ordner>/_verdaechtig/             aussortierte Dateien

Fortsetzbar
-----------
Vorhandene Dateien werden uebersprungen. Abbruch mit Strg+C kostet hoechstens
die gerade laufenden Abfragen.

Warum so viel geprueft wird
---------------------------
Das Portal entscheidet selbst ueber das Zeitraster, wenn man es ihm nicht
sagt. Deshalb geht jeder Diagrammanfrage der Energiebilanz ein
presetting=day voraus - sonst koennen statt 15-Minuten-Mittelwerten
kommentarlos Tagessummen kommen.

Der Download des Portals gibt immer das ZULETZT ANGEZEIGTE Diagramm aus.
Schlaegt die Diagrammanforderung fehl, kommt der Vormonat ein zweites Mal -
ohne Fehlermeldung. Deshalb wird jede Datei geprueft: Kopfzeile, Tageszahl,
Pruefsumme gegen alle anderen Monate, Groesse der Diagrammantwort. Bei den
Verbrauchern gilt Entsprechendes: In 5-Minuten-Aufloesung liefert das Portal
NUR die Verbraucherkurven, die anlagenweiten Reihen bleiben leer.

Aenderungen
-----------
2.10.0 2026-09-02  Die Lueckensuche nimmt jetzt auch Tage mit, an denen der
                   Tageszaehler selbst leer ist - aber nur in Monaten, in denen
                   der MONATSzaehler mehr ausweist als die Tageswerte zusammen.
                   Genau so sieht der Juli 2023 dieser Anlage aus: 270 kWh im
                   Monat, 57 kWh in den Tagen. Ob die Tagesansicht dort Kurven
                   hat, war nicht zu erraten - jetzt fragt das Skript nach.
2.9.0  2026-09-02  Neue Quellen bilanz_luecken und wechselrichter_luecken.
                   Sie laden die Tage einzeln nach, an denen die Monatsabfrage
                   keine Feinkurve hergab, der Tageszaehler aber Energie
                   ausweist - fuer diese Anlage 57 Tage, im Wesentlichen der
                   Maerz 2026. Das Portal hat sie: der 15.03.2026 zeigt im
                   Reiter "Tag" eine vollstaendige Viertelstundenkurve. Damit
                   muss nichts aus Tagessummen verteilt werden.
2.8.1  2026-09-02  Die Gesamtansicht haengt ein leeres Folgejahr an; fuenf
                   Zeilen fuer vier Jahre sind also richtig.
2.8.0  2026-09-02  Nachbesserungen an den Raendern. Die groben Quellen
                   fragen immer den ganzen Kalendermonat beziehungsweise das
                   ganze Jahr an - bei einer Spanne von einem Tag faellt das
                   Portal auf das zuletzt gezeichnete Diagramm zurueck, was
                   den September 2026 gekostet hat. Im laufenden Monat gilt
                   eine Spanne statt einer festen Zeilenzahl. Die Schwelle
                   fuer die Diagrammantwort sinkt von 8 auf 4 kB: ein fast
                   leerer Monat ergibt ein sehr kleines Bild und war deshalb
                   faelschlich abgelehnt worden. Und die feine Geraetequelle
                   sagt ihr Raster jetzt ebenfalls an (presetting=day) - der
                   Lauf von wechselrichter_tage hat belegt, dass die
                   Analyse-Seite den Parameter genauso auswertet.
2.7.0  2026-09-02  Die groben Zeitraster als eigene Quellen: _tage,
                   _monate und _jahre je Seite (presetting month/year/total).
                   Sechs zusaetzliche Quellen, zusammen 94 Abfragen - und
                   dafuer auf jeder Ebene eine unabhaengige Pruefsumme.
2.6.0  2026-09-02  Zwei neue Quellen: bilanz_tage und wechselrichter_tage
                   holen dieselben Reihen als Zaehleraenderung je Tag
                   (presetting=month). Das ist eine zweite, unabhaengige
                   Sicht - im Juli 2023 stehen im Tageszaehler rund 300 kWh,
                   in der Viertelstundenkurve nur 92. Ausserdem wird die
                   Tageslaenge nicht mehr fest mit 96 Zeilen angenommen,
                   sondern aus der Datei gerechnet.
2.5.0  2026-09-02  Der Verbraucherexport bereitet seine Sitzung jetzt vor.
                   Bisher erbte er ein leeres sitzung_vorbereiten und ging
                   direkt auf den JSON-Endpunkt - der antwortet dann mit der
                   Anmeldeseite. Erst Startseite, dann Verbraucherbilanz macht
                   die ASP.NET-Sitzung gueltig; in den getrennten Skripten
                   erledigte das noch anlage_ermitteln() nebenbei.
2.4.0  2026-09-02  Das Zeitraster wird jetzt angesagt statt gehofft: die
                   Diagrammanfrage der Energiebilanz bekommt den Parameter
                   presetting=day mit - denselben, den der Browser beim Klick
                   auf den Reiter "Tag" schickt. Ohne ihn entscheidet die
                   Vorgabe des Servers, und stand die auf "month", kamen
                   Tagessummen statt 15-Minuten-Werten, ohne Fehlermeldung.
                   Das versteckte Reiterfeld war nur Anzeige und ist kein
                   Abbruchgrund mehr. Neu dafuer ein Wachtposten: scheitern die
                   ersten fuenf Abfragen ausnahmslos, wird die Quelle
                   abgebrochen, statt tausend weitere ins Leere zu schicken.
2.3.0  2026-09-02  Der Reiter wird nicht mehr nur gemeldet, sondern
                   umgestellt: das Formular wird mit geaendertem Feld
                   zurueckgeschickt, so wie es der Browser tut. Ein Klick im
                   Browser hilft naemlich nicht - er gilt nur fuer die
                   Browsersitzung. Laesst der Reiter sich nicht stellen, wird
                   fuer diese Quelle gar nichts geladen statt 42 Monate
                   Tagessummen. Ausserdem beendet Strg+C jetzt den ganzen Lauf;
                   bisher wurde nur die laufende Quelle abgebrochen und gleich
                   darauf die naechste begonnen.
2.2.0  2026-09-02  Zwei Fehler behoben. Erstens hing der Lauf nach genau
                   zehn erledigten Aufgaben: der Arbeiter schrieb das Protokoll
                   waehrend er die Sperre schon hielt, und json_schreiben nahm
                   dieselbe Sperre noch einmal - eine threading.Lock ist nicht
                   reentrant, also blockierte er sich selbst und mit ihm alle
                   anderen; auch Strg+C kam dann nicht mehr durch. Jetzt RLock,
                   und geschrieben wird ausserhalb der Sperre. Zweitens wird der
                   Reiter (Tag/Monat/Jahr) der Portalseite gelesen und gemeldet;
                   steht er nicht auf "Tag", liefert das Portal Tagessummen
                   statt 15-Minuten-Werten. Das hiess bisher irrefuehrend
                   "0 Tage statt 31" und heisst nun beim Namen.
2.1.0  2026-09-02  Arbeiter melden sich VERSETZT an und wiederholen bei
                   Ablehnung - gleichzeitige Anmeldungen weist SMA ID ab.
                   Zeitbudget je Aufgabe aus [export] timeout. Tabellenkopf
                   wieder da. Ohne Argument wird "alles" geholt. Bei einem
                   Fehlschlag wird die Rohantwort des Portals gesichert.
                   Strg+C leert die Warteschlange und wartet hoechstens
                   Zeitbudget + 30 s.
2.0.1  2026-09-01  Strg+C erklaert jetzt, dass auf die laufenden Abfragen
                   gewartet wird, und zeigt den Fortschritt dabei an
2.0.0  2026-09-01  Die drei Exportskripte zusammengefasst; parallele
                   Verbindungen, Anzahl aus zugangsdaten.ini
1.0.0  2026-09-01  Getrennte Skripte je Quelle
"""

import argparse
import configparser
import gzip
import hashlib
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
from datetime import date, datetime, timedelta

from portal import (PORTAL, PortalFehler, ZeitUeberschritten,
                    anlage_ermitteln, anmelden, ist_anmeldeseite, messwerte)

__version__ = "2.10.0"
__stand__ = "2026-09-02"

HIER = os.path.dirname(os.path.abspath(__file__))
CONF_DATEI = os.path.join(HIER, "zugangsdaten.ini")

CHART_API = f"{PORTAL}/PortalCharts/Core/PortalChartsAPI.aspx"
SEITE_BILANZ = f"{PORTAL}/FixedPages/HoManEnergyRedesign.aspx"
SEITE_ANALYSE = f"{PORTAL}/FixedPages/AnalysisTool.aspx"
DOWN_BILANZ = f"{PORTAL}/Templates/DownloadDiagram.aspx?down=homanEnergyRedesign&chartId=mainChart"
DOWN_ANALYSE = f"{PORTAL}/Templates/DownloadDiagram.aspx?down=analysisTool&chartId=mainChart"

GERAETEWAHL = "ctl00$ContentPlaceHolder1$UserControlShowAnalysisTool1$DeviceSelection"

# Kleinste Diagrammantwort, die noch ernst genommen wird. Sie ist nur ein
# grober Vorfilter gegen abgebrochene Anfragen - die eigentliche Pruefung
# macht die CSV. Ein fast leerer Monat wie der April 2023 ergibt ein sehr
# kleines Bild (7243 B) und ist trotzdem gueltig.
MIN_DIAGRAMM = 4_000
VERSUCHE = 3
PAUSE = 3.0

# Zeitbudget je Aufgabe. Wird beim Start aus [export] timeout gesetzt und
# gilt sowohl als Zeitlimit je Anfrage als auch als Obergrenze dafuer, wie
# lange ein Arbeiter an einem einzelnen Monat oder Tag sitzen darf.
TIMEOUT = 300

# Abstand zwischen den Anmeldungen der Arbeiter. Melden sich mehrere
# gleichzeitig bei SMA ID an, weist der Anmeldedienst einen Teil davon ab -
# offenbar ein Schutz gegen zu viele Anmeldungen in kurzer Folge.
ANMELDE_ABSTAND = 2.5
ANMELDE_VERSUCHE = 3

# Nach so vielen Aufgaben ohne einen einzigen Erfolg wird abgebrochen.
FRUEHSTOPP = 5

# Reentrant, weil unter dieser Sperre auch Funktionen aufgerufen werden,
# die sie selbst noch einmal nehmen (json_schreiben). Mit einer einfachen
# Lock blockiert sich der Arbeiter dabei selbst - und mit ihm alle anderen.
sperre = threading.RLock()

# Wird bei Strg+C gesetzt. arbeiten() faengt die Unterbrechung selbst ab, damit
# die laufenden Abfragen sauber zu Ende kommen - ohne diese Merker liefe danach
# aber die naechste Quelle an, und der Abbruch waere wirkungslos.
ABGEBROCHEN = threading.Event()


# ------------------------------------------------------------------ Allgemein

def einstellung(name, vorgabe, kleinstes, groesstes):
    """Eine Zahl aus dem Abschnitt [export] der zugangsdaten.ini."""
    if not os.path.exists(CONF_DATEI):
        return vorgabe
    cp = configparser.ConfigParser()
    cp.read(CONF_DATEI, encoding="utf-8")
    try:
        return max(kleinstes, min(groesstes, cp.getint("export", name, fallback=vorgabe)))
    except ValueError:
        return vorgabe


def parallel_aus_ini(vorgabe=3):
    return einstellung("parallel", vorgabe, 1, 12)


def timeout_aus_ini(vorgabe=300):
    """Zeitbudget je Aufgabe in Sekunden."""
    return einstellung("timeout", vorgabe, 60, 900)


def zahl(x):
    """
    Eine Zahl aus einer Portalzelle - in deutscher Schreibweise.

    Der Punkt trennt die Tausender, das Komma die Dezimalen: "1.008" sind
    1008, nicht 1,008. Wer den Punkt als Dezimalzeichen liest, teilt jeden
    Wert ab tausend durch tausend - und weil das nur die grossen Werte trifft,
    sieht die Datei danach immer noch plausibel aus.

    In den Dateien dieser Anlage stehen ueber 49000 Zahlen mit Punkt, und in
    jeder einzelnen folgen genau drei Ziffern. Punkte mit anderer Ziffernzahl
    kommen ausschliesslich in Kopfzeilen vor (Geraetenamen wie STP10.0-3SE-40).
    """
    x = x.strip().strip('"').strip()
    if not x:
        return None
    try:
        return float(x.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def unix(d):
    return int(datetime(d.year, d.month, d.day).timestamp())


def naechster_monat(d):
    return (d.replace(day=28) + timedelta(days=8)).replace(day=1)


def monate(von, bis):
    m = von.replace(day=1)
    while m <= bis:
        yield m
        m = naechster_monat(m)


def json_laden(pfad, vorgabe):
    if os.path.exists(pfad):
        try:
            with open(pfad, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            pass
    return vorgabe


def json_schreiben(pfad, inhalt):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with sperre:
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump(inhalt, f, indent=1, ensure_ascii=False)


def dauer(sekunden):
    sekunden = int(sekunden)
    if sekunden < 90:
        return f"{sekunden} s"
    if sekunden < 5400:
        return f"{sekunden // 60} min"
    return f"{sekunden / 3600:.1f} h"


# ------------------------------------------------ Zeitraster des Diagramms
#
# Ueber den Diagrammen sitzen Reiter: Aktuell / Tag / Monat / Jahr / Gesamt.
# Welcher davon gilt, entscheidet ueber das Zeitraster der Antwort: beim Reiter
# "Tag" kommen 15-Minuten-Mittelwerte, beim Reiter "Monat" nur noch Tagessummen.
# Dieser Reiter steht NICHT in der Anfrage des Skripts - das Portal merkt ihn
# sich und schickt ihn mit der Seite zurueck (verstecktes Feld
# DateTimeTabs$CurrentTab). Wer nebenher im Browser auf "Monat" klickt,
# veraendert damit unter Umstaenden, was dieses Skript geliefert bekommt.
# Deshalb wird der Reiter gelesen und gemeldet, bevor stundenlang das Falsche
# heruntergeladen wird.

def felder_lesen(html):
    """Alle Formularfelder einer WebForms-Seite, so wie ein Browser sie zuruecksendet."""
    felder = {}
    for m in re.finditer(r"<input\b([^>]*)>", html, re.I):
        a = m.group(1)
        name = re.search(r'name="([^"]+)"', a)
        if not name:
            continue
        typ = (re.search(r'type="([^"]+)"', a) or [None, "text"])[1].lower()
        if typ == "submit":
            continue
        if typ in ("checkbox", "radio") and "checked" not in a.lower():
            continue
        wert = re.search(r'value="([^"]*)"', a)
        felder[name.group(1)] = wert.group(1) if wert else ("on" if typ == "checkbox" else "")
    for m in re.finditer(r"<select\b([^>]*)>(.*?)</select>", html, re.I | re.S):
        name = re.search(r'name="([^"]+)"', m.group(1))
        if not name:
            continue
        sel = re.search(r'<option[^>]*selected[^>]*value="([^"]*)"', m.group(2), re.I)
        felder[name.group(1)] = sel.group(1) if sel else ""
    return felder


TAG_NAMEN = ("tag", "day", "jour", "giorno", "dia", "d\u00eda", "dag", "dzien")


def tab_zustand(html):
    """(Nummer des aktiven Reiters, {Nummer: Beschriftung}); beides kann fehlen."""
    m = re.search(r'name="[^"]*DateTimeTabs\$CurrentTab"[^>]*value="(\d+)"', html)
    aktuell = int(m.group(1)) if m else None
    namen = {int(nr): text.strip() for nr, text in re.findall(
        r'id="TabSpan(\d+)"[^>]*>\s*<span>([^<]*)</span>', html)}
    return aktuell, namen


def tag_reiter(namen):
    """Nummer des Reiters "Tag" - die Beschriftung haengt an der Portalsprache."""
    for nr, text in namen.items():
        if text.lower() in TAG_NAMEN:
            return nr
    return None


# ------------------------------------------- Grobe Dateien nachrechnen
#
# Nur so viel Leseleistung, wie die Lueckensuche braucht: Summe je Reihe. Die
# ausgewachsene Auswertung macht Stufe 2; dieses Skript soll fuer sich allein
# lauffaehig bleiben und nichts aus den spaeteren Stufen importieren.

def grob_summen(pfad, zeilen_bereich=None):
    """
    Spaltensummen einer groben Datei in kWh, {Reihenname: Summe}.

    Gleichnamige Spalten zaehlen EINMAL: Die Energiebilanz fuehrt
    'Direktverbrauch' zweimal mit identischen Werten auf.
    zeilen_bereich grenzt auf einen Ausschnitt ein, etwa eine Monatszeile.
    """
    if not os.path.exists(pfad):
        return {}
    with open(pfad, encoding="utf-8-sig") as f:
        zeilen = [z for z in f.read().splitlines() if z.strip()]
    if len(zeilen) < 2:
        return {}
    kopf = [c.strip() for c in zeilen[0].split(";")]
    spalten = {}
    for i in range(1, len(kopf)):
        name = kopf[i].split(" /")[0].strip()
        if name and name not in spalten:
            spalten[name] = i
    daten = zeilen[1:]
    if zeilen_bereich is not None:
        daten = daten[zeilen_bereich:zeilen_bereich + 1]
    summen = {}
    for z in daten:
        felder = z.split(";")
        for name, i in spalten.items():
            w = zahl(felder[i]) if len(felder) > i else None
            if w is None:
                continue
            einheit = re.search(r"\[(k|M)?Wh\]", kopf[i])
            faktor = {"M": 1000.0, "k": 1.0, None: 0.001}[
                einheit.group(1) if einheit else "k"]
            summen[name] = summen.get(name, 0.0) + w * faktor
    return summen


# --------------------------------------------------- Pruefung der Monatsdatei

def monats_csv_pruefen(text, erwartete_tage, min_reihen=1, pflichtwort=None,
                       raster="fein", hoechstens=None):
    """
    Beurteilt eine Monatsdatei.

    raster="fein"  Leistungsmittelwerte, mehrere Zeilen je Tag. Ein Tag ist an
                   seiner Schlusszeile 00:00 zu erkennen.
    raster="grob"  Zaehleraenderung, eine Zeile je Zeiteinheit - je nach Quelle
                   ein Tag, ein Monat oder ein Jahr. Geprueft wird die
                   Zeilenzahl gegen die erwartete Zahl von Einheiten; dass die
                   Beschriftung mal ein Datum und mal ein Monatsname ist,
                   spielt dann keine Rolle.

    erwartete_tage meint in beiden Faellen die erwartete Zahl von Einheiten.
    """
    zeilen = [z for z in text.splitlines() if z.strip()]
    if len(zeilen) < 2:
        return {"ok": False, "grund": "leere Antwort", "zeilen": 0}

    kopf = [c.strip() for c in zeilen[0].split(";")]
    reihen = [c for c in kopf[1:] if c]
    if pflichtwort and not any(pflichtwort in c for c in kopf):
        return {"ok": False, "zeilen": len(zeilen) - 1,
                "grund": f"Spalte '{pflichtwort}' fehlt in der Kopfzeile"}
    if len(reihen) < min_reihen:
        return {"ok": False, "zeilen": len(zeilen) - 1, "reihen": reihen,
                "grund": f"nur {len(reihen)} Reihe(n), erwartet {min_reihen}"}

    daten = [z.split(";") for z in zeilen[1:]]
    if raster == "grob":
        tage = len(daten)
    else:
        tage = len(re.findall(r'"=""00:00"""', text))
    gefuellt = sum(1 for r in daten if any(zahl(c) is not None for c in r[1:]))
    anteil = gefuellt / len(daten) if daten else 0

    # Wie viele Zeilen bilden einen Tag? Nicht fest 96 annehmen - der erste,
    # angebrochene Monat einer Anlage kommt in Stundenwerten.
    je_tag = max(1, len(daten) // tage) if tage else 0
    leere_tage = []
    for nr in range(tage):
        block = daten[nr * je_tag:(nr + 1) * je_tag]
        if block and not any(zahl(c) is not None for r in block for c in r[1:]):
            leere_tage.append(nr + 1)

    e = {"zeilen": len(daten), "tage": tage, "erwartete_tage": erwartete_tage,
         "reihen": reihen, "anteil": round(anteil, 3), "leere_tage": leere_tage,
         "zeilen_je_tag": je_tag,
         "einheit": (re.search(r"\[(k?Wh?)\]", zeilen[0]) or [None, "?"])[1],
         "pruefsumme": hashlib.md5(text.encode("utf-8")).hexdigest()[:12]}

    if raster == "grob":
        # Im laufenden Monat oder Jahr weiss niemand vorher, wie viele Balken
        # das Portal schon zeichnet. Dann gilt eine Spanne statt einer Zahl.
        obergrenze = erwartete_tage if hoechstens is None else hoechstens
        if not erwartete_tage <= tage <= obergrenze:
            erwartung = (str(erwartete_tage) if obergrenze == erwartete_tage
                         else f"{erwartete_tage} bis {obergrenze}")
            e.update(ok=False, grund=f"{tage} Zeilen statt {erwartung}")
        else:
            e.update(ok=True, grund="")
            if leere_tage:
                e["hinweis"] = f"{len(leere_tage)} ohne Werte"
        return e

    if tage != erwartete_tage:
        # Kommt gar kein Tagesbeginn vor, dafuer aber Datumszeilen, dann hat das
        # Portal Tagessummen geschickt statt 15-Minuten-Werten. Das ist kein
        # leerer Monat, sondern das falsche Zeitraster - und muss anders heissen,
        # sonst sucht man den Fehler an der falschen Stelle.
        tagessummen = len(re.findall(r'"=""\d{2}\.\d{2}\.\d{4}"""', text))
        if tage == 0 and tagessummen:
            e.update(ok=False, grund=(
                f"Tagesraster statt 15 Minuten: {tagessummen} Tagessummen - "
                f"der Reiter im Portal steht nicht auf 'Tag'"))
        else:
            e.update(ok=False, grund=f"{tage} Tage statt {erwartete_tage}")
    else:
        e.update(ok=True, grund="")
        if leere_tage:
            e["hinweis"] = f"{len(leere_tage)} Tage ohne Werte"
        elif anteil < 0.90:
            e["hinweis"] = f"nur {anteil:.0%} der Zeilen gefuellt"
    return e


# --------------------------------------------------------------- Die Quellen

class Quelle:
    """Gemeinsames Geruest. Eine Quelle sagt, was zu holen ist und wie geprueft wird."""

    name = "?"
    ordner = "?"

    def __init__(self, anlage, heute):
        self.anlage = anlage
        self.start = datetime.strptime(anlage["min_date"], "%Y-%m-%d").date()
        self.heute = heute
        self.ziel = os.path.join(HIER, self.ordner)
        self.verdaechtig = os.path.join(self.ziel, "_verdaechtig")
        self.protokoll_datei = os.path.join(self.ziel, "_protokoll.json")
        self.protokoll = json_laden(self.protokoll_datei, {})
        self.pruefsummen = {}

    # --- vom Aufrufer zu ueberschreiben ---
    def aufgaben(self, von, bis):
        raise NotImplementedError

    def datei(self, aufgabe):
        raise NotImplementedError

    def sitzung_vorbereiten(self, s):
        pass

    # Meldungen zum Reiter sollen einmal erscheinen, nicht je Arbeiter.
    reiter_gemeldet = False

    def reiter_pruefen(self, s, html):
        """
        Sorgt dafuer, dass die Seite auf dem Reiter "Tag" steht, und gibt das
        (ggf. neue) Seiten-HTML zurueck.

        Der Reiter ist ein verstecktes Formularfeld. Ein Klick im Browser
        aendert ihn nur in DIESER Browsersitzung - eine frische Sitzung des
        Skripts bekommt wieder die Vorgabe des Portals, und die ist bei der
        Energiebilanz "Monat". Also wird der Reiter hier so umgestellt, wie es
        der Browser tut: das Formular mit geaendertem Feld zurueckschicken.
        """
        aktuell, namen = tab_zustand(html)
        soll = tag_reiter(namen)
        if aktuell is None or soll is None or aktuell == soll:
            return html

        feld = re.search(r'name="([^"]*DateTimeTabs\$CurrentTab)"', html)
        if feld:
            felder = felder_lesen(html)
            felder[feld.group(1)] = str(soll)
            felder["__EVENTTARGET"] = ""
            felder["__EVENTARGUMENT"] = ""
            neu_html = s.post(self.seite, data=felder,
                              headers={"Referer": self.seite}, timeout=TIMEOUT).text
            if tab_zustand(neu_html)[0] == soll:
                with sperre:
                    if not self.reiter_gemeldet:
                        self.reiter_gemeldet = True
                        print(f"   Reiter von '{namen.get(aktuell, aktuell)}' auf "
                              f"'{namen[soll]}' umgestellt.")
                return neu_html

        with sperre:
            if not self.reiter_gemeldet:
                self.reiter_gemeldet = True
                print(f"   Hinweis: Reiter '{namen.get(aktuell, aktuell)}' liess "
                      f"sich nicht auf '{namen[soll]}' stellen.")
        return html

    def holen(self, s, aufgabe):
        raise NotImplementedError

    # --- gemeinsam ---
    def bestand_pruefen(self, von, bis):
        aussortiert = []
        for aufgabe in self.aufgaben(von, bis):
            p = self.datei(aufgabe)
            if not os.path.exists(p):
                continue
            e = self.vorhandene_pruefen(aufgabe, p)
            if e is None:
                continue
            schluessel = self.schluessel(aufgabe)
            with sperre:
                doppelt = self.pruefsummen.get(e.get("pruefsumme"))
                if doppelt:
                    e.update(ok=False, grund=f"identisch mit {doppelt}")
                elif e.get("pruefsumme"):
                    self.pruefsummen[e["pruefsumme"]] = schluessel
            if not e["ok"]:
                os.makedirs(self.verdaechtig, exist_ok=True)
                shutil.move(p, os.path.join(self.verdaechtig, os.path.basename(p)))
                aussortiert.append((schluessel, e["grund"]))
        return aussortiert

    def vorhandene_pruefen(self, aufgabe, pfad):
        return None

    def schluessel(self, aufgabe):
        return str(aufgabe)


class MonatsQuelle(Quelle):
    """Gemeinsames fuer Energiebilanz und Wechselrichter: ein Monat je Abfrage."""

    seite = None
    download = None
    min_reihen = 1
    pflichtwort = None

    # Das Zeitraster der Antwort. Der Browser schickt es als Parameter
    # "presetting" mit, sobald man oben einen Reiter anklickt:
    #
    #     SwitchToDayTab()  ->  updateCharts("day", true)
    #                       ->  param.presetting = "day"
    #                       ->  PortalChartsAPI.aspx?id=mainChart&presetting=day
    #
    # Ohne diesen Parameter nimmt der Server seine eigene Vorgabe - und die ist
    # nicht verlaesslich. Lange ging es gut, weil sie zufaellig "day" war; steht
    # sie auf "month", kommen Tagessummen statt 15-Minuten-Mittelwerten, und
    # zwar ohne jede Fehlermeldung. Deshalb wird es jetzt gesagt statt gehofft.
    #
    presetting = None

    def aufgaben(self, von, bis):
        for m in monate(max(von, self.start.replace(day=1)), bis):
            yield m

    def datei(self, m):
        return os.path.join(self.ziel, f"{m.year}-{m.month:02d}.csv")

    def schluessel(self, m):
        return f"{m.year}-{m.month:02d}"

    def zeitraum(self, m):
        return max(m, self.start), min(naechster_monat(m), self.heute)

    def erwartete_einheiten(self, von, bis):
        """Wie viele Zeilen die Antwort mindestens haben muss - hier: Tage."""
        return (bis - von).days

    def hoechstens_einheiten(self, von, bis):
        """Und hoechstens. Gleich viele, solange der Zeitraum abgeschlossen ist."""
        return self.erwartete_einheiten(von, bis)

    # "fein" = Leistungsmittelwerte je Viertelstunde, "tag" = Zaehleraenderung
    # je Tag. Das eine ist die feine Kurve, das andere der harte Zaehlerwert.
    raster = "fein"

    def vorhandene_pruefen(self, m, pfad):
        von, bis = self.zeitraum(m)
        return monats_csv_pruefen(open(pfad, encoding="utf-8-sig").read(),
                                  self.erwartete_einheiten(von, bis),
                                  self.min_reihen, self.pflichtwort, self.raster,
                                  self.hoechstens_einheiten(von, bis))

    def sitzung_vorbereiten(self, s):
        s.get(f"{PORTAL}/Templates/Start.aspx", timeout=45)
        self.reiter_pruefen(s, s.get(self.seite, timeout=TIMEOUT).text)
        self.raster_setzen(s)

    def raster_setzen(self, s):
        """Ein Klick auf den Reiter "Tag", so wie der Browser ihn ausloest."""
        if not self.presetting:
            return
        s.get(CHART_API,
              params={"id": "mainChart", "presetting": self.presetting,
                      "t": int(time.time() * 1000)},
              headers={"Referer": self.seite, "X-Requested-With": "XMLHttpRequest"},
              timeout=TIMEOUT)

    def holen(self, s, m):
        von, bis = self.zeitraum(m)
        erwartet = self.erwartete_einheiten(von, bis)
        if erwartet <= 0:
            return {"status": "ausserhalb"}

        letzter = None
        for versuch in range(1, VERSUCHE + 1):
            r = s.get(CHART_API,
                      params={"id": "mainChart", "xf": unix(von), "xt": unix(bis),
                              "t": int(time.time() * 1000)},
                      headers={"Referer": self.seite,
                               "X-Requested-With": "XMLHttpRequest"},
                      timeout=TIMEOUT)
            if len(r.content) < MIN_DIAGRAMM:
                letzter = {"status": "fehlgeschlagen", "diagramm_bytes": len(r.content),
                           "grund": f"Diagrammantwort nur {len(r.content)} B",
                           "versuch": versuch}
                time.sleep(PAUSE)
                continue

            rd = s.get(self.download, headers={"Referer": self.seite}, timeout=TIMEOUT)
            if ist_anmeldeseite(rd.text):
                raise PortalFehler("Anmeldeseite beim Download - Sitzung abgelaufen.")

            e = monats_csv_pruefen(rd.text, erwartet, self.min_reihen,
                                   self.pflichtwort, self.raster,
                                   self.hoechstens_einheiten(von, bis))
            e["diagramm_bytes"] = len(r.content)
            e["versuch"] = versuch

            # Beim letzten Fehlversuch die Rohantwort sichern. Ohne sie laesst
            # sich hinterher nicht klaeren, WAS das Portal geschickt hat.
            if not e["ok"] and versuch == VERSUCHE:
                os.makedirs(self.verdaechtig, exist_ok=True)
                with open(os.path.join(self.verdaechtig,
                                       f"{self.schluessel(m)}_rohantwort.csv"),
                          "w", encoding="utf-8-sig", newline="") as f:
                    f.write(rd.text)
                e["rohantwort_gesichert"] = True

            with sperre:
                doppelt = self.pruefsummen.get(e.get("pruefsumme"))
                if doppelt:
                    e.update(ok=False, grund=f"identisch mit {doppelt}")
                elif e["ok"]:
                    self.pruefsummen[e["pruefsumme"]] = self.schluessel(m)

            if e["ok"]:
                os.makedirs(self.ziel, exist_ok=True)
                with open(self.datei(m), "w", encoding="utf-8-sig", newline="") as f:
                    f.write(rd.text)
                e["status"] = "ok"
                return e

            e["status"] = "unbrauchbar"
            letzter = e
            time.sleep(PAUSE)

        return letzter or {"status": "unbrauchbar", "grund": "unbekannt"}

    @staticmethod
    def kopfzeile():
        return (f"{'':>9}{'Monat':<9}{'Zeilen':>7}{'Tage':>5}{'Rei':>4}"
                f"{'Einh':>5}{'Diagramm':>9}   Ergebnis")

    def zeile(self, schluessel, e):
        if e["status"] == "ok":
            zusatz = f"   LUECKE: {e['hinweis']}" if e.get("hinweis") else ""
            return (f"{schluessel:<9}{e['zeilen']:>7}{e['tage']:>5}"
                    f"{len(e.get('reihen') or []):>4}{e['einheit']:>5}"
                    f"{e['diagramm_bytes']:>9}   ok{zusatz}")
        if e["status"] == "ausserhalb":
            return f"{schluessel:<9}   ausserhalb des Anlagenzeitraums"
        return f"{schluessel:<9}   NICHT UEBERNOMMEN: {e.get('grund','')}"


class Bilanz(MonatsQuelle):
    name = "bilanz"
    ordner = "bilanz"
    seite = SEITE_BILANZ
    download = DOWN_BILANZ
    pflichtwort = "Netzeinspeisung"
    presetting = "day"


class Wechselrichter(MonatsQuelle):
    name = "wechselrichter"
    ordner = "wechselrichter"
    seite = SEITE_ANALYSE
    download = DOWN_ANALYSE
    min_reihen = 2      # mindestens Anlage plus ein Geraet
    # Anfangs stand hier None: Die Analyse-Seite laedt anderes JavaScript, und
    # der Parametername war fuer sie nicht belegt. Der Lauf von
    # wechselrichter_tage hat gezeigt, dass sie ihn genauso auswertet - die
    # Diagramm-Schnittstelle liest ihn, nicht die Seite. Also wird er auch
    # hier gesagt, statt sich auf die Vorgabe des Servers zu verlassen.
    presetting = "day"

    def sitzung_vorbereiten(self, s):
        """
        Die Geraeteauswahl der Analyse-Seite ist Sitzungszustand. Jede Sitzung
        muss sie selbst setzen, sonst enthaelt die Datei nur die Anlagensumme.
        """
        s.get(f"{PORTAL}/Templates/Start.aspx", timeout=45)
        html = s.get(self.seite, timeout=TIMEOUT).text
        if ist_anmeldeseite(html):
            raise PortalFehler("Analyse-Seite liefert die Anmeldeseite.")
        html = self.reiter_pruefen(s, html)
        self.raster_setzen(s)

        # Wie viele Geraete bietet die Seite an? Das steht in der Checkboxliste.
        anzahl = len(set(re.findall(
            re.escape(GERAETEWAHL.replace("$", "_")) + r"_SimpleCheckboxList_(\d+)", html)))
        for nr in range(anzahl):
            ziel = f"{GERAETEWAHL}$SimpleCheckboxList${nr}"
            kennung = ziel.replace("$", "_")
            m = re.search(r'id="' + re.escape(kennung) + r'"([^>]*)>', html)
            if m and "checked" in m.group(1).lower():
                continue
            felder = felder_lesen(html)
            felder.update({"__EVENTTARGET": ziel, "__EVENTARGUMENT": "", ziel: "on"})
            html = s.post(self.seite, data=felder,
                          headers={"Referer": self.seite}, timeout=TIMEOUT).text
            time.sleep(0.4)


class Verbraucher(Quelle):
    """Ein TAG je Abfrage - der langwierige Teil, und der Grund fuer die Parallelitaet."""

    name = "verbraucher"
    ordner = "rohdaten"
    ANLAGENREIHEN = ("PvGeneration", "TotalConsumption", "ExternalSupply",
                     "BatteryCharging", "BatteryDischarging", "BasicLoad")

    def __init__(self, anlage, heute, intervall="15min"):
        super().__init__(anlage, heute)
        self.intervall = intervall

    def sitzung_vorbereiten(self, s):
        """
        Die ASP.NET-Sitzung setzen, bevor der JSON-Endpunkt gefragt wird.

        Die Anmeldung allein reicht dafuer nicht: Wer gleich
        GetMeasuredValues aufruft, bekommt die Anmeldeseite zurueck. Erst die
        Startseite und danach die Verbraucherbilanz machen die Sitzung
        gueltig - dieselbe Reihenfolge, die auch anlage_ermitteln() geht.
        Manchmal greift es erst im zweiten Anlauf.
        """
        s.get(f"{PORTAL}/Templates/Start.aspx", timeout=45)
        for _ in range(2):
            r = s.get(f"{PORTAL}/Homan/ConsumerBalance", timeout=TIMEOUT)
            if not ist_anmeldeseite(r.text):
                return
        raise PortalFehler("Verbraucherbilanz liefert die Anmeldeseite.")

    def aufgaben(self, von, bis):
        tag = max(von, self.start)
        letzter = min(bis, self.heute - timedelta(days=1))
        while tag <= letzter:
            yield tag
            tag += timedelta(days=1)

    def datei(self, tag):
        return os.path.join(self.ziel, str(tag.year),
                            f"{tag.isoformat()}_{self.intervall}.json.gz")

    def schluessel(self, tag):
        return tag.isoformat()

    def anlagenreihen_punkte(self, daten):
        if not isinstance(daten, dict):
            return 0
        for k in self.ANLAGENREIHEN:
            v = daten.get(k)
            if isinstance(v, list) and v:
                return len(v)
        return 0

    def verbraucher_punkte(self, daten):
        if not isinstance(daten, dict):
            return 0
        for c in daten.get("Consumers") or []:
            v = c.get("Consume")
            if isinstance(v, list) and v:
                return len(v)
        return 0

    def holen(self, s, tag):
        start = tag.isoformat()
        ende = (tag + timedelta(days=1)).isoformat()
        begonnen = time.monotonic()
        try:
            daten, roh, sek = messwerte(s, self.anlage["plant_oid"], start, ende,
                                        self.intervall, timeout=TIMEOUT)
        except ZeitUeberschritten as e:
            return {"status": "zeitlimit", "grund": str(e),
                    "sekunden": round(time.monotonic() - begonnen, 1)}

        if daten is None:
            return {"status": "kein_json", "zeichen": len(roh),
                    "sekunden": round(sek, 1)}

        anlage = self.anlagenreihen_punkte(daten)
        verbraucher = self.verbraucher_punkte(daten)
        brauchbar = verbraucher > 0 if self.intervall == "5min" else anlage > 0
        if not brauchbar:
            return {"status": "leer", "anlagenreihen": anlage,
                    "verbraucher": verbraucher, "sekunden": round(sek, 1)}

        pfad = self.datei(tag)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with gzip.open(pfad, "wt", encoding="utf-8") as f:
            f.write(roh)
        return {"status": "ok", "anlagenreihen": anlage, "verbraucher": verbraucher,
                "zeichen": len(roh), "sekunden": round(sek, 1)}

    @staticmethod
    def kopfzeile():
        return (f"{'':>9}{'Tag':<12}{'Anlagenreihen':<14}{'Verbraucher':<14}"
                f"{'Zeit':>7}")

    def zeile(self, schluessel, e):
        if e["status"] == "ok":
            return (f"{schluessel:<12}Anlage {e['anlagenreihen']:>3}  "
                    f"Verbraucher {e['verbraucher']:>3}  {e['sekunden']:>5.1f}s")
        if e["status"] == "leer":
            return (f"{schluessel:<12}keine Daten "
                    f"(Anlage {e['anlagenreihen']}, Verbraucher {e['verbraucher']})")
        return f"{schluessel:<12}{e['status'].upper()}  {str(e.get('grund',''))[:50]}"


# ---------------------------------------------- Die groben Zeitraster
#
# Dieselben Seiten, nur mit anderem presetting. Das ist keine Wiederholung,
# sondern eine zweite, unabhaengige Sicht: Feinkurve und Zaehleraenderung
# entstehen im Portal getrennt und weichen voneinander ab. Im Juli 2023 - der
# Wechselrichter war in Wartung - stehen im Tageszaehler rund 300 kWh, in der
# Viertelstundenkurve nur 92. Wer nur das Feine holt, verliert Energie, ohne
# es zu merken.
#
# Die groben Abfragen sind billig: ein Monat, ein Jahr oder alles auf einmal.
# Sie taugen als Pruefsumme fuer jede Ebene und als Notnagel dort, wo die
# feine Aufloesung fehlt.

class TagesQuelle(MonatsQuelle):
    """Ein Monat je Abfrage; die Antwort enthaelt Tagessummen."""

    presetting = "month"
    raster = "grob"

    def zeitraum(self, m):
        # Immer der ganze Kalendermonat, auch wenn die Anlage mitten darin
        # anfing und auch wenn er noch laeuft. Das Portal zeichnet ihn ohnehin
        # so; fragt man dagegen eine Spanne von einem Tag an, faellt es auf das
        # zuletzt gezeichnete Diagramm zurueck.
        return m, naechster_monat(m)

    def erwartete_einheiten(self, von, bis):
        if bis <= self.heute:
            return (bis - von).days
        return 1        # laufender Monat: mindestens ein Balken

    def hoechstens_einheiten(self, von, bis):
        return (bis - von).days


class JahresQuelle(MonatsQuelle):
    """Ein Jahr je Abfrage; die Antwort enthaelt Monatssummen."""

    presetting = "year"
    raster = "grob"

    def aufgaben(self, von, bis):
        for jahr in range(max(von, self.start).year, bis.year + 1):
            yield date(jahr, 1, 1)

    def datei(self, j):
        return os.path.join(self.ziel, f"{j.year}.csv")

    def schluessel(self, j):
        return str(j.year)

    def zeitraum(self, j):
        return j, date(j.year + 1, 1, 1)

    def erwartete_einheiten(self, von, bis):
        if bis <= self.heute:
            return 12
        return 1        # laufendes Jahr

    def hoechstens_einheiten(self, von, bis):
        return 12


class GesamtQuelle(MonatsQuelle):
    """Eine einzige Abfrage ueber alles; die Antwort enthaelt Jahressummen."""

    presetting = "total"
    raster = "grob"

    def aufgaben(self, von, bis):
        yield date(self.start.year, 1, 1)

    def datei(self, j):
        return os.path.join(self.ziel, "gesamt.csv")

    def schluessel(self, j):
        return "gesamt"

    def zeitraum(self, j):
        return date(self.start.year, 1, 1), self.heute

    def erwartete_einheiten(self, von, bis):
        return bis.year - von.year + 1

    def hoechstens_einheiten(self, von, bis):
        # Die Gesamtansicht haengt dem letzten Jahr noch ein leeres Folgejahr
        # an - 2023 bis 2026 ergibt fuenf Zeilen, nicht vier.
        return self.erwartete_einheiten(von, bis) + 1


class LueckenQuelle(MonatsQuelle):
    """
    Faehrt einzelne TAGE an, an denen die Monatsabfrage keine Feinkurve
    hergab, der Tageszaehler aber Energie ausweist.

    Dass es solche Tage gibt, ist belegt und keine Vermutung: Fuer den
    15.03.2026 zeigt das Portal im Reiter "Tag" eine vollstaendige
    Viertelstundenkurve - dieselbe Reihe bleibt in der Monatsabfrage leer.
    Die Messwerte sind vorhanden, die Monatsabfrage gibt sie nur nicht her.
    Deshalb werden sie geholt statt gerechnet: Ein nachgeladener Tag ist
    gemessen, ein verteilter Tageswert waere erfunden.

    Welche Tage das sind, steht schon in den Protokollen: die leeren Tage der
    feinen Datei, abzueglich der Tage, an denen auch der Tageszaehler nichts
    hat - die sind im Portal wirklich leer.
    """

    presetting = "day"
    basis = None                # "bilanz" oder "wechselrichter"

    def luecken_tage(self):
        fein = json_laden(os.path.join(HIER, self.basis, "_protokoll.json"), {})
        grob = json_laden(os.path.join(HIER, self.basis + "_tage",
                                       "_protokoll.json"), {})
        tage = []
        for schluessel, e in sorted(fein.items()):
            if e.get("status") != "ok" or schluessel not in grob:
                continue
            jahr, monat = int(schluessel[:4]), int(schluessel[5:7])
            # Die leeren Tage der feinen Datei sind ab deren ERSTEM Tag
            # gezaehlt, und der ist im Anfangsmonat nicht der Monatserste.
            beginn = max(date(jahr, monat, 1), self.start)
            ohne_zaehler = set(grob[schluessel].get("leere_tage") or [])
            # Wenn schon der Monatszaehler mehr weiss als die Tageswerte, dann
            # sind auch die scheinbar leeren Tage einen Versuch wert - der Juli
            # 2023 dieser Anlage hat im Monat 270 kWh und in den Tagen 57.
            unvollstaendig = self.monat_unvollstaendig(jahr, monat)
            for nr in e.get("leere_tage") or []:
                tag = beginn + timedelta(days=nr - 1)
                if tag >= self.heute:
                    continue
                if tag.day in ohne_zaehler and not unvollstaendig:
                    continue
                tage.append(tag)
        return tage

    def monat_unvollstaendig(self, jahr, monat):
        """Liegt die Summe der Tageswerte unter dem Monatswert?"""
        tagesdatei = os.path.join(HIER, self.basis + "_tage",
                                  f"{jahr}-{monat:02d}.csv")
        monatsdatei = os.path.join(HIER, self.basis + "_monate", f"{jahr}.csv")
        aus_tagen = grob_summen(tagesdatei)
        aus_monat = grob_summen(monatsdatei, zeilen_bereich=monat - 1)
        if not aus_tagen or not aus_monat:
            return False
        for reihe, wert in aus_monat.items():
            if wert - aus_tagen.get(reihe, 0.0) > max(3.0, 0.01 * wert):
                return True
        return False

    def aufgaben(self, von, bis):
        for tag in self.luecken_tage():
            if von <= tag <= bis:
                yield tag

    def datei(self, tag):
        return os.path.join(self.ziel, f"{tag.isoformat()}.csv")

    def schluessel(self, tag):
        return tag.isoformat()

    def zeitraum(self, tag):
        return tag, tag + timedelta(days=1)

    @staticmethod
    def kopfzeile():
        return (f"{'':>9}{'Tag':<12}{'Zeilen':>7}{'Tage':>5}{'Rei':>4}"
                f"{'Einh':>5}{'Diagramm':>9}   Ergebnis")

    def zeile(self, schluessel, e):
        return super().zeile(schluessel, e).replace(f"{schluessel:<9}",
                                                    f"{schluessel:<12}", 1)


class BilanzTage(TagesQuelle, Bilanz):
    name = ordner = "bilanz_tage"


class BilanzMonate(JahresQuelle, Bilanz):
    name = ordner = "bilanz_monate"


class BilanzJahre(GesamtQuelle, Bilanz):
    name = ordner = "bilanz_jahre"


class BilanzLuecken(LueckenQuelle, Bilanz):
    name = "bilanz_luecken"
    ordner = "bilanz/luecken"
    basis = "bilanz"


class WechselrichterTage(TagesQuelle, Wechselrichter):
    name = ordner = "wechselrichter_tage"


class WechselrichterMonate(JahresQuelle, Wechselrichter):
    name = ordner = "wechselrichter_monate"


class WechselrichterJahre(GesamtQuelle, Wechselrichter):
    name = ordner = "wechselrichter_jahre"


class WechselrichterLuecken(LueckenQuelle, Wechselrichter):
    name = "wechselrichter_luecken"
    ordner = "wechselrichter/luecken"
    basis = "wechselrichter"


QUELLEN = {
    "bilanz":               Bilanz,
    "bilanz_tage":          BilanzTage,
    "bilanz_monate":        BilanzMonate,
    "bilanz_jahre":         BilanzJahre,
    "bilanz_luecken":       BilanzLuecken,
    "wechselrichter":       Wechselrichter,
    "wechselrichter_tage":  WechselrichterTage,
    "wechselrichter_monate": WechselrichterMonate,
    "wechselrichter_jahre": WechselrichterJahre,
    "wechselrichter_luecken": WechselrichterLuecken,
    "verbraucher":          Verbraucher,
}


# --------------------------------------------------------------- Arbeiterpool

def arbeiten(quelle, offene, anzahl_arbeiter):
    """Arbeitet die Liste mit mehreren eigenstaendig angemeldeten Sitzungen ab."""
    warteschlange = queue.Queue()
    for aufgabe in offene:
        warteschlange.put(aufgabe)

    zaehler = {"ok": 0, "leer": 0, "fehler": 0, "erledigt": 0}
    gesamt = len(offene)
    begonnen = time.monotonic()
    abbruch = threading.Event()

    def anmelden_mit_geduld(nr):
        """
        Melden sich mehrere Arbeiter gleichzeitig an, weist SMA ID einen Teil
        davon ab. Deshalb versetzt starten und bei Ablehnung erneut versuchen -
        die Ablehnung ist keine falsche Zugangsdatenangabe, sondern ein
        Schutz gegen zu viele Anmeldungen in kurzer Folge.
        """
        time.sleep((nr - 1) * ANMELDE_ABSTAND)
        letzter = None
        for versuch in range(1, ANMELDE_VERSUCHE + 1):
            try:
                s = anmelden(leise=True)
                quelle.sitzung_vorbereiten(s)
                if versuch > 1:
                    with sperre:
                        print(f"   Arbeiter {nr}: angemeldet (Versuch {versuch})")
                return s
            except Exception as e:
                letzter = e
                wartezeit = versuch * 5
                with sperre:
                    print(f"   Arbeiter {nr}: Anmeldung abgelehnt, "
                          f"neuer Versuch in {wartezeit} s ({versuch}/{ANMELDE_VERSUCHE})")
                time.sleep(wartezeit)
        with sperre:
            print(f"   Arbeiter {nr}: gibt auf - {letzter}")
        return None

    def arbeiter(nr):
        s = anmelden_mit_geduld(nr)
        if s is None:
            return

        while not abbruch.is_set():
            try:
                aufgabe = warteschlange.get_nowait()
            except queue.Empty:
                return
            schluessel = quelle.schluessel(aufgabe)
            try:
                e = quelle.holen(s, aufgabe)
            except PortalFehler as ex:
                if "Anmeldeseite" in str(ex):
                    try:
                        s = anmelden(leise=True)
                        quelle.sitzung_vorbereiten(s)
                        e = quelle.holen(s, aufgabe)
                    except Exception as ex2:
                        e = {"status": "fehler", "grund": str(ex2)}
                else:
                    e = {"status": "fehler", "grund": str(ex)}
            except Exception as ex:
                e = {"status": "fehler", "grund": f"{type(ex).__name__}: {ex}"}

            with sperre:
                quelle.protokoll[schluessel] = e
                zaehler["erledigt"] += 1
                if e["status"] == "ok":
                    zaehler["ok"] += 1
                elif e["status"] in ("leer", "ausserhalb"):
                    zaehler["leer"] += 1
                else:
                    zaehler["fehler"] += 1

                fertig = zaehler["erledigt"]
                verstrichen = time.monotonic() - begonnen
                rest = (gesamt - fertig) * verstrichen / fertig if fertig else 0
                print(f"[{fertig:>4}/{gesamt}] {quelle.zeile(schluessel, e)}"
                      f"   noch ca. {dauer(rest)}")

                # Wenn die ersten Abfragen ausnahmslos scheitern, stimmt etwas
                # Grundsaetzliches nicht - dann sind auch die restlichen 1200
                # vergeblich. Lieber frueh anhalten und den Grund zeigen.
                if fertig >= FRUEHSTOPP and zaehler["ok"] == 0 and not abbruch.is_set():
                    abbruch.set()
                    print("\n" + "!" * 88)
                    print(f"ABBRUCH: Die ersten {fertig} Abfragen sind ALLE "
                          f"fehlgeschlagen.")
                    print("Es wird nicht weitergemacht - der Grund steht in den "
                          "Zeilen darueber")
                    print("und ausfuehrlich im Protokoll. Rohantworten des Portals "
                          "liegen in")
                    print(f"   {quelle.verdaechtig}")
                    print("!" * 88)

            # Bewusst AUSSERHALB der Sperre: Schreiben auf die Platte soll die
            # anderen Arbeiter nicht aufhalten.
            if fertig % 10 == 0:
                json_schreiben(quelle.protokoll_datei, quelle.protokoll)
            warteschlange.task_done()

    faeden = [threading.Thread(target=arbeiter, args=(i + 1,), daemon=True)
              for i in range(min(anzahl_arbeiter, max(1, gesamt)))]
    for f in faeden:
        f.start()

    try:
        while any(f.is_alive() for f in faeden):
            for f in faeden:
                f.join(timeout=0.4)
    except KeyboardInterrupt:
        abbruch.set()
        ABGEBROCHEN.set()
        # Warteschlange leeren. Der Zustandstest allein genuegt nicht: Ein
        # Arbeiter kann zwischen Test und Entnahme stehen und dann noch eine
        # Aufgabe ziehen. Eine leere Warteschlange kann er nicht ziehen.
        entfernt = 0
        while True:
            try:
                warteschlange.get_nowait()
                entfernt += 1
            except queue.Empty:
                break
        auf_arbeiter_warten(faeden, zaehler, gesamt, entfernt)

    json_schreiben(quelle.protokoll_datei, quelle.protokoll)
    return zaehler, time.monotonic() - begonnen


def auf_arbeiter_warten(faeden, zaehler, gesamt, uebersprungen=0):
    """
    Nach Strg+C. Neue Abfragen werden keine mehr begonnen, aber die laufenden
    muessen zu Ende gebracht werden - das Portal antwortet in seinem eigenen
    Tempo, im schlimmsten Fall erst nach dem Zeitlimit. Wer hier hart abbricht,
    verliert nur die angefangenen Abfragen; darum wird gewartet und der
    Fortschritt angezeigt, damit niemand glaubt, das Programm haenge.
    """
    laufend = sum(1 for f in faeden if f.is_alive())
    with sperre:
        print("\n" + "=" * 88)
        print("ABBRUCH ANGEFORDERT - bitte warten, es wird NICHT sofort beendet.")
        print("=" * 88)
        if uebersprungen:
            print(f"{uebersprungen} noch nicht begonnene Aufgaben wurden verworfen.")
        print(f"Es werden keine neuen Abfragen mehr begonnen. {laufend} laufende")
        print(f"Abfrage(n) muessen noch zu Ende gebracht werden - das kann bis zu")
        print(f"{TIMEOUT} Sekunden dauern, weil das Portal in seinem Tempo antwortet.")
        print(f"Laenger nicht: Nach {TIMEOUT + 30} s wird das Warten abgebrochen.")
        print("")
        print("Der Fortschritt ist gesichert: Fertige Zeitraeume haben ihre Datei")
        print("und werden beim naechsten Start uebersprungen. Bitte das Fenster")
        print("nicht schliessen und Strg+C nicht wiederholen.\n")

    begonnen = time.monotonic()
    letzte_meldung = 0.0
    grenze = TIMEOUT + 30
    while any(f.is_alive() for f in faeden):
        if time.monotonic() - begonnen > grenze:
            with sperre:
                print(f"\nNach {int(grenze)} s immer noch aktiv - es wird nicht "
                      f"laenger gewartet.\nDer Fortschritt ist gesichert.")
            return
        try:
            for f in faeden:
                f.join(timeout=0.3)
        except KeyboardInterrupt:
            with sperre:
                print("   (Strg+C erneut - es wird trotzdem gewartet, "
                      "das Beenden laesst sich nicht beschleunigen)")
            continue
        verstrichen = time.monotonic() - begonnen
        if verstrichen - letzte_meldung >= 5:
            letzte_meldung = verstrichen
            noch = sum(1 for f in faeden if f.is_alive())
            with sperre:
                print(f"   ... noch {noch} Arbeiter aktiv, seit {int(verstrichen)} s "
                      f"({zaehler['erledigt']}/{gesamt} erledigt)")

    with sperre:
        print(f"\nAlle Arbeiter beendet nach {int(time.monotonic() - begonnen)} s. "
              f"Fortschritt gesichert.")


# ---------------------------------------------------------------------- Main

def quelle_ausfuehren(art, anlage, heute, args, anzahl):
    quelle = QUELLEN[art](anlage, heute)
    print("\n" + "=" * 88)
    print(f"{art.upper()}  ->  {quelle.ziel}")
    print("=" * 88)

    von = datetime.strptime(args.von + "-01", "%Y-%m-%d").date() if args.von else quelle.start
    bis = datetime.strptime(args.bis + "-01", "%Y-%m-%d").date() if args.bis else heute
    if art == "verbraucher":
        if args.von:
            von = datetime.strptime(args.von if len(args.von) > 7 else args.von + "-01",
                                    "%Y-%m-%d").date()
        bis = heute

    print("\nVorhandene Dateien pruefen ...")
    aussortiert = quelle.bestand_pruefen(von, bis)
    print(f"   {len(aussortiert)} aussortiert")
    for schluessel, grund in aussortiert:
        print(f"      {schluessel}  ->  {grund}")

    if args.nur_pruefen:
        print("\nNur-Pruefen-Modus, es wird nichts geladen.")
        return

    alle = list(quelle.aufgaben(von, bis))
    if args.neu:
        for a in alle:
            p = quelle.datei(a)
            if os.path.exists(p):
                os.remove(p)
    offen = [a for a in alle if not os.path.exists(quelle.datei(a))]

    print(f"\nZeitraum : {von} bis {bis}")
    print(f"Zu laden : {len(offen)} von {len(alle)}")
    print(f"Parallel : {anzahl} Verbindungen, Zeitbudget {TIMEOUT} s je Aufgabe")
    if not offen:
        print("\nNichts zu tun.")
        return

    print()
    print(quelle.kopfzeile())
    print("-" * 88)

    zaehler, verstrichen = arbeiten(quelle, offen, anzahl)
    print(f"\ngeladen {zaehler['ok']}  ohne Daten {zaehler['leer']}  "
          f"fehlerhaft {zaehler['fehler']}  Laufzeit {dauer(verstrichen)}")
    if zaehler["fehler"]:
        print("Fehlerhafte Eintraege haben keine Datei - ein erneuter Start holt sie nach.")


def main():
    p = argparse.ArgumentParser(
        description="Daten aus dem Sunny Portal holen",
        epilog="Beispiel: python 1_export.py alles --parallel 4")
    p.add_argument("quelle", nargs="?", default="alles",
                   choices=list(QUELLEN) + ["alles"],
                   help="was geholt werden soll (Vorgabe: alles)")
    p.add_argument("--von", help="erster Monat JJJJ-MM (bei verbraucher auch JJJJ-MM-TT)")
    p.add_argument("--bis", help="letzter Monat JJJJ-MM")
    p.add_argument("--neu", action="store_true", help="vorhandene Dateien neu laden")
    p.add_argument("--nur-pruefen", action="store_true", help="nichts laden, nur pruefen")
    p.add_argument("--parallel", type=int, help="Anzahl gleichzeitiger Verbindungen")
    p.add_argument("--timeout", type=int,
                   help="Zeitbudget je Aufgabe in Sekunden (Vorgabe aus der INI, sonst 300)")
    args = p.parse_args()

    global TIMEOUT
    anzahl = args.parallel or parallel_aus_ini()
    TIMEOUT = args.timeout or timeout_aus_ini()

    print("=" * 88)
    print(f"Sunny Portal - Export  (Version {__version__}, {__stand__})")
    print("=" * 88)

    try:
        s = anmelden()
        anlage = anlage_ermitteln(s)
    except PortalFehler as e:
        print(f"\nABBRUCH: {e}")
        return 1

    heute = date.today()
    print(f"\nAnlage   : {anlage['plant_oid']}")
    print(f"Daten ab : {anlage['min_date']}")

    fuer = list(QUELLEN) if args.quelle == "alles" else [args.quelle]
    for art in fuer:
        try:
            quelle_ausfuehren(art, anlage, heute, args, anzahl)
        except KeyboardInterrupt:
            ABGEBROCHEN.set()
        if ABGEBROCHEN.is_set():
            print("\nAbgebrochen. Ein erneuter Start setzt dort fort, wo es aufhoerte.")
            return 130

    print("\n" + "=" * 88)
    print("Fertig. Naechster Schritt: 2_analyse.py")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    sys.exit(main())
