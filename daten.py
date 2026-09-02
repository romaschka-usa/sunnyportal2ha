#!/usr/bin/env python3
"""
daten - Portal-CSV lesen und die Geraeteaufteilung beurteilen
==============================================================

Version         : 1.8.0
Letzte Aenderung: 2026-09-02

Beschreibung
------------
Gemeinsames Modul fuer 2_analyse.py und 3_transform.py. Es wird importiert und
nicht direkt aufgerufen. Zwei Aufgaben:

1. DIE MONATSDATEIEN LESEN
   Aus einer Portal-CSV werden stuendliche Energiewerte. Dabei sind vier
   Eigenheiten der Quelle zu beachten:

     * Die Einheit wechselt zwischen [W] und [kW], je nachdem wie das Portal
       die Achse skaliert hat. Sie steht in der Kopfzeile.
     * Die Werte sind Mittelwerte je Zeitschritt, Energie = Leistung * Dauer.
       Der Schritt ist MEISTENS eine Viertelstunde, aber nicht immer: fuer den
       ersten, angebrochenen Monat einer Anlage liefert das Portal Stundenwerte.
       Deshalb wird der Schritt aus den Uhrzeiten der Datei abgeleitet und
       nicht angenommen.
     * Die CSV enthaelt kein Datum, nur die Uhrzeit - und zwar das ENDE des
       Intervalls. Ein Tag laeuft von 00:15 bis 00:00.
     * Tage ohne jeden Wert werden als Luecke gemeldet, nicht als Null.

2. DIE GERAETEAUFTEILUNG BEURTEILEN
   Anlagen wachsen: Wechselrichter kommen dazu, fallen aus, werden getauscht.
   Und die Analyse-Seite liefert die Geraetereihen nicht immer richtig - bei
   der Anlage, an der dieses Projekt entstand, betrug die Reihe des einen
   Geraetes ueber zwanzig Monate hinweg exakt ein Viertel der Anlagensumme.

   Deshalb wird nicht angenommen, sondern aus den Daten abgeleitet: Welches
   Geraet lieferte wann Werte, und ergeben die Geraetereihen zusammen die
   Anlagensumme? Daraus entstehen Abschnitte, Rueckfragen und ein Vorschlag,
   den der Anlagenbetreiber bestaetigt. Nur er weiss, ob im Maerz wirklich ein
   Geraet dazukam oder ob nur anders verkabelt wurde.

Aufruf
------
Nicht direkt. Wird von 2_analyse.py und 3_transform.py verwendet.

Aenderungen
-----------
1.8.0  2026-09-02  Neu leistung_differenz_lesen(): die vorzeichenbehaftete
                   Netzleistung, Bezug minus Einspeisung. Die Differenz wird
                   je Zeile gebildet, nicht aus den Stundenmitteln - sonst
                   heben sich in einer Wechselstunde beide Aeste auf.
1.7.0  2026-09-02  Liest die Feinkurven auch als LEISTUNG: je Stunde
                   Mittelwert, Minimum und Maximum in Watt. Home Assistant
                   fuehrt Leistung als Mittelwertstatistik; die Tagesspitze
                   bleibt dabei als Maximum erhalten, auch wenn das
                   Stundenmittel sie glaettet.
1.6.0  2026-09-02  Neu fein_dateien(): Monatsdateien UND nachgeladene
                   Lueckentage in einer Lesereihenfolge. Bisher musste jeder
                   Aufrufer selbst daran denken - 3_transform.py tat es nicht
                   und verlor damit den Maerz 2026.
1.5.0  2026-09-02  Die Geraetepruefung braucht jetzt eine relative UND eine
                   absolute Abweichung, um einen Monat unstimmig zu nennen.
                   Rein relativ schlug jeder fast leere Monat aus: Im Juli
                   2023 war der Wechselrichter in Wartung, und 1,98 Prozent
                   von 57 kWh sind 1,1 kWh.
1.4.0  2026-09-02  Der Zeittakt wird JE SPALTE bestimmt. Bis Ende 2024
                   liefert das Portal die Anlagensumme viertelstuendlich, die
                   Reihe eines Wechselrichters aber nur stuendlich - in
                   derselben Datei. Mit dem Takt der Zeilen gerechnet ergab
                   das exakt ein Viertel seiner Erzeugung. Der vermeintliche
                   Fehler des Portals war also einer dieser Auswertung.
1.3.0  2026-09-02  Liest die einzeln nachgeladenen Feintage aus
                   <ordner>/luecken mit. Sie ersetzen den jeweiligen Tag,
                   statt dazugezaehlt zu werden.
1.2.1  2026-09-02  Gleichnamige Spalten werden nicht mehr addiert. Die
                   Energiebilanz fuehrt 'Direktverbrauch' zweimal mit
                   identischen Werten; das ergab den doppelten Direktverbrauch.
1.2.0  2026-09-02  Liest auch die groben Zeitraster (Tag, Monat, Jahr)
                   und rechnet die Feinkurven auf Tagessummen herunter, damit
                   sich die Ebenen vergleichen lassen. Zeilen werden ueber
                   ihre Position gelesen, nicht ueber ihre Beschriftung - die
                   ist je nach Seite mal mit Jahr, mal ohne und uebersetzt.
1.1.0  2026-09-02  Der Zeitschritt wird aus der Datei abgelesen statt
                   angenommen. Bisher galt fest eine Viertelstunde - fuer den
                   ersten, angebrochenen Monat einer Anlage liefert das Portal
                   aber Stundenwerte. Deren 24 Zeilen landeten in den Stunden
                   0 bis 5 und wurden zusaetzlich geviertelt; der Monat waere
                   gestaucht und auf ein Viertel geschrumpft in Home Assistant
                   angekommen, ohne dass etwas aufgefallen waere. Die Stunde
                   kommt jetzt aus der Uhrzeit der Zeile, nicht aus einem
                   Zeilenzaehler.
1.0.0  2026-09-01  Erste Fassung; entstanden aus geraete.py und den
                   Lesefunktionen von transform.py
"""

import calendar
import os
import re
from datetime import date, datetime, timedelta

__version__ = "1.8.0"
__stand__ = "2026-09-01"

# Ab welchem Anteil an der Anlagensumme ein Geraet als "liefert Werte" gilt.
SCHWELLE_AKTIV = 0.005
# Wie weit die Summe der Geraete von der Anlagensumme abweichen darf -
# relativ UND absolut. Beides ist noetig: Rein relativ schlaegt jeder fast
# leere Monat aus (im Juli 2023 war der Wechselrichter in Wartung, und
# 1,98 Prozent von 57 kWh sind 1,1 kWh - das ist Rauschen, kein Ereignis).
# Rein absolut wuerde eine echte Abweichung im Winter durchrutschen.
TOLERANZ = 0.01
TOLERANZ_KWH = 20.0


# ============================================================================
# Teil 1 - Monatsdateien lesen
# ============================================================================

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


def uhrzeit(zelle):
    """Aus der Excel-Zeitzelle des Portals wird (Stunde, Minute)."""
    m = re.search(r"(\d{1,2}):(\d{2})", zelle)
    return (int(m.group(1)), int(m.group(2))) if m else None


def reihenname(geraetename):
    """Aus 'STP10.0-3SE-40 681' wird 'wr_stp10_0_3se_40_681'."""
    sauber = re.sub(r"[^a-z0-9]+", "_", geraetename.lower()).strip("_")
    return f"wr_{sauber}"[:60]


def monate_dateien(ordner):
    if not os.path.isdir(ordner):
        return []
    treffer = []
    for name in sorted(os.listdir(ordner)):
        m = re.fullmatch(r"(\d{4})-(\d{2})\.csv", name)
        if m:
            treffer.append((date(int(m.group(1)), int(m.group(2)), 1),
                            os.path.join(ordner, name)))
    return treffer


def startdatum(monat, tage_in_datei, ist_erste_datei):
    """
    Die CSV enthaelt kein Datum. Ein voller Monat beginnt am Ersten. Eine
    kuerzere Datei ist entweder der angebrochene aktuelle Monat (beginnt
    ebenfalls am Ersten) oder der erste Monat der Anlage (beginnt spaeter).
    """
    tage_im_monat = calendar.monthrange(monat.year, monat.month)[1]
    if tage_in_datei >= tage_im_monat or not ist_erste_datei:
        return monat
    return monat.replace(day=tage_im_monat - tage_in_datei + 1)


def csv_lesen(pfad):
    with open(pfad, encoding="utf-8-sig") as f:
        zeilen = [z for z in f.read().splitlines() if z.strip()]
    if len(zeilen) < 2:
        return [], [], "?"
    kopf = [c.strip() for c in zeilen[0].split(";")]
    einheit = (re.search(r"\[(k?W)\]", zeilen[0]) or [None, "?"])[1]
    return kopf, [z.split(";") for z in zeilen[1:]], einheit


def zeitschritt(zeilen):
    """
    Minuten je Zeile, aus den ersten beiden Uhrzeiten der Datei abgelesen.

    15 bei der ueblichen Viertelstundendatei, 60 beim ersten Monat einer
    Anlage. Faellt im Zweifel auf 15 zurueck - das ist der Normalfall.
    """
    zeiten = []
    for z in zeilen:
        u = uhrzeit(z[0])
        if u is not None:
            zeiten.append(u[0] * 60 + u[1])
            if len(zeiten) == 2:
                break
    if len(zeiten) < 2:
        return 15
    schritt = zeiten[1] - zeiten[0]
    return schritt if 0 < schritt <= 60 else 15


def spaltenschritt(zeilen, spalten, schritt_minuten):
    """
    Minuten je Wert - JE SPALTE. Nicht jede Reihe kommt im selben Takt.

    Das ist kein Sonderfall: In den Dateien dieser Anlage liefert die
    Anlagensumme bis Ende 2024 96 Werte am Tag, die Reihe des einen
    Wechselrichters aber nur 24 - in derselben Datei, mit leeren Zellen
    dazwischen. Wer stur mit dem Takt der Zeilen rechnet, macht aus jedem
    Stundenwert einen Viertelstundenwert und erhaelt fuer dieses Geraet exakt
    ein Viertel seiner Erzeugung. Das sieht nach einem Fehler des Portals aus,
    ist aber einer der Auswertung - die Spitzenleistung stimmt dabei naemlich,
    nur die Energie nicht.

    Genommen wird der HAEUFIGSTE Abstand, nicht der mittlere: Nachtstunden
    ohne Werte wuerden den Mittelwert verzerren.
    """
    ergebnis = {}
    for name, i in spalten.items():
        stellen = [nr for nr, z in enumerate(zeilen)
                   if len(z) > i and zahl(z[i]) is not None]
        abstaende = [b - a for a, b in zip(stellen, stellen[1:])]
        haeufigster = max(set(abstaende), key=abstaende.count) if abstaende else 1
        # Mehr als eine Stunde je Wert kommt nicht vor; ein groesserer Abstand
        # waere eine Luecke im Tag, kein anderer Takt.
        ergebnis[name] = min(60, max(1, haeufigster) * schritt_minuten)
    return ergebnis


def stunde_von(zeit):
    """
    Die Stunde, in die eine Zeile gehoert.

    Die Uhrzeit ist das ENDE des Intervalls: 00:15 gehoert zur Stunde 0,
    01:00 ebenfalls, 01:15 zur Stunde 1. Das Tagesende steht als 00:00 in der
    Datei und meint 24:00, gehoert also zur Stunde 23.
    """
    minute = zeit[0] * 60 + zeit[1]
    if minute == 0:
        minute = 24 * 60
    return (minute - 1) // 60


def luecken_dateien(ordner):
    """(Tag, Pfad) der einzeln nachgeladenen Feintage unter <ordner>/luecken."""
    unter = os.path.join(ordner, "luecken")
    if not os.path.isdir(unter):
        return []
    treffer = []
    for name in sorted(os.listdir(unter)):
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\.csv", name)
        if m:
            treffer.append((date(*(int(g) for g in m.groups())),
                            os.path.join(unter, name)))
    return treffer


def stunden_lesen(pfad, monat, ist_erste, spaltenwahl, zeitzone, start_tag=None):
    """
    Liest eine Monatsdatei und liefert {name: {stunde: kWh}}, die Tage ohne
    jeden Wert und die verwendete Einheit.
    """
    kopf, zeilen, einheit = csv_lesen(pfad)
    if not zeilen:
        return {}, [], einheit

    # Energie = Leistung * Dauer. Die Dauer kommt aus der Datei, die Einheit
    # aus der Kopfzeile - beides wechselt, je nach Monat.
    schritt = zeitschritt(zeilen)
    einheit_faktor = 1.0 if einheit == "kW" else 0.001
    tage = sum(1 for z in zeilen if uhrzeit(z[0]) == (0, 0))
    # Bei einer nachgeladenen Tagesdatei steht das Datum im Dateinamen; es muss
    # dann nicht aus der Zeilenzahl erschlossen werden.
    tag = start_tag or startdatum(monat, tage, ist_erste)
    spalten = spaltenwahl(kopf)
    faktoren = {name: (minuten / 60.0) * einheit_faktor
                for name, minuten in spaltenschritt(zeilen, spalten, schritt).items()}

    stunden = {name: {} for name in spalten}
    leere_tage = []
    tag_hat_werte = False

    for z in zeilen:
        zeit = uhrzeit(z[0])
        if zeit is None:
            continue
        stunde = stunde_von(zeit)
        for name, i in spalten.items():
            w = zahl(z[i]) if len(z) > i else None
            if w is None:
                continue
            tag_hat_werte = True
            zeitpunkt = datetime(tag.year, tag.month, tag.day, stunde, 0,
                                 tzinfo=zeitzone)
            stunden[name][zeitpunkt] = (stunden[name].get(zeitpunkt, 0.0)
                                        + w * faktoren[name])
        if zeit == (0, 0):
            if not tag_hat_werte:
                leere_tage.append(tag.isoformat())
            tag += timedelta(days=1)
            tag_hat_werte = False

    return stunden, leere_tage, einheit


# ------------------------------------------------- Die groben Zeitraster
#
# Neben den Viertelstundenkurven liefert das Portal dieselben Reihen als
# Zaehleraenderung je Tag, Monat und Jahr. Das ist eine zweite, unabhaengige
# Sicht - und sie ist die vollstaendigere: Im Juli 2023 stehen im Monatswert
# 270 kWh, in den Tageswerten 57 und in der Feinkurve ebenfalls 57. Im Maerz
# 2026 haben Monat und Tag die vollen 1702 kWh, die Feinkurve gar nichts.
# Je groeber, desto vollstaendiger.
#
# WICHTIG: Die Zeilen werden ueber ihre POSITION gelesen, nicht ueber ihre
# Beschriftung. Die ist naemlich uneinheitlich und uebersetzt - die
# Energiebilanz schreibt "01.06.2025" und "Januar", die Analyse-Seite "01.06."
# ohne Jahr und "Jan 25". Die Position dagegen ist verlaesslich: Zeile n ist
# der n-te Tag des Monats aus dem Dateinamen, der n-te Monat des Jahres, das
# n-te Jahr ab dem ersten.

def spaltenkurz(name):
    """'PV-Erzeugung / Zaehleraenderung [kWh]' -> 'PV-Erzeugung'."""
    return name.split(" /")[0].strip()


def einheitsfaktor(spaltenname):
    """Faktor auf kWh. Die Jahresansicht rechnet in MWh, die uebrigen in kWh."""
    treffer = re.search(r"\[(k|M)?Wh\]", spaltenname)
    if not treffer:
        return 1.0
    return {"M": 1000.0, "k": 1.0, None: 0.001}[treffer.group(1)]


def erste_spalten(kopf):
    """
    {Reihenname: Spaltennummer} - je Name nur EINE Spalte, die erste.

    Die Energiebilanz fuehrt 'Direktverbrauch' zweimal auf, einmal aus Sicht
    der Erzeugung und einmal aus Sicht des Verbrauchs. Die Werte sind
    identisch. Wer gleichnamige Spalten addiert, verdoppelt die Reihe - und
    bekommt einen Direktverbrauch groesser als die Erzeugung, was auffaellt,
    aber erst spaet.
    """
    spalten = {}
    for i in range(1, len(kopf)):
        name = spaltenkurz(kopf[i])
        if name and name not in spalten:
            spalten[name] = i
    return spalten


def grob_zeilen(pfad):
    """Eine grobe Datei als Liste von {Reihenname: kWh} - in Dateireihenfolge."""
    with open(pfad, encoding="utf-8-sig") as f:
        zeilen = [z for z in f.read().splitlines() if z.strip()]
    if len(zeilen) < 2:
        return []
    kopf = [c.strip() for c in zeilen[0].split(";")]
    spalten = erste_spalten(kopf)
    ergebnis = []
    for z in zeilen[1:]:
        felder = z.split(";")
        werte = {}
        for name, i in spalten.items():
            w = zahl(felder[i]) if len(felder) > i else None
            if w is not None:
                werte[name] = w * einheitsfaktor(kopf[i])
        ergebnis.append(werte)
    return ergebnis


def grob_lesen(ordner, ebene):
    """
    Alle Dateien eines groben Ordners.

    ebene "tag"    -> {date: {Reihe: kWh}}, Dateiname JJJJ-MM.csv
    ebene "monat"  -> {(Jahr, Monat): {...}}, Dateiname JJJJ.csv
    ebene "jahr"   -> {Jahr: {...}}, eine Datei, erste Zeile = fruehestes Jahr
    """
    if not os.path.isdir(ordner):
        return {}
    ergebnis = {}
    for name in sorted(os.listdir(ordner)):
        if not name.endswith(".csv"):
            continue
        pfad = os.path.join(ordner, name)
        zeilen = grob_zeilen(pfad)
        if ebene == "tag":
            jahr, monat = int(name[:4]), int(name[5:7])
            for nr, werte in enumerate(zeilen):
                try:
                    ergebnis[date(jahr, monat, nr + 1)] = werte
                except ValueError:
                    pass            # das Portal zeichnet 30 Balken, auch im Februar
        elif ebene == "monat":
            jahr = int(name[:4])
            for nr, werte in enumerate(zeilen[:12]):
                ergebnis[(jahr, nr + 1)] = werte
        else:
            # Die Jahresansicht beschriftet mit der Jahreszahl - hier ist die
            # Beschriftung ausnahmsweise eindeutig, aber die Position genuegt
            # auch: sie beginnt beim ersten Jahr mit Daten.
            roh = [z for z in open(pfad, encoding="utf-8-sig").read().splitlines()
                   if z.strip()][1:]
            for zeile, werte in zip(roh, zeilen):
                treffer = re.search(r"(\d{4})", zeile.split(";")[0])
                if treffer:
                    ergebnis[int(treffer.group(1))] = werte
    return ergebnis


def fein_dateien(ordner):
    """
    Alle feinen Dateien eines Ordners in Lesereihenfolge:
    (Monat, Pfad, ist_erste_datei, start_tag).

    Das sind die Monatsdateien UND die einzeln nachgeladenen Tage aus
    <ordner>/luecken. Die Tagesdateien kommen zuletzt, denn sie sollen den
    jeweiligen Tag ersetzen - in der Monatsdatei ist er leer, aber wer das
    voraussetzt, addiert nach einem erneuten Lauf doppelt. start_tag ist bei
    ihnen gesetzt, weil ihr Datum im Dateinamen steht und nicht aus der
    Zeilenzahl erschlossen werden muss.

    Wer nur die Monatsdateien liest, verliert genau die Zeitraeume, fuer die
    die Lueckensuche gebaut wurde - beim Maerz 2026 dieser Anlage sind das
    1700 kWh, ohne dass irgendetwas nach einem Fehler aussieht.
    """
    monate = monate_dateien(ordner)
    for nr, (monat, pfad) in enumerate(monate):
        yield monat, pfad, nr == 0, None
    for tag, pfad in luecken_dateien(ordner):
        yield tag.replace(day=1), pfad, False, tag


def fein_tagessummen(ordner, zeitzone):
    """
    Tagessummen aus den Viertelstundendateien - dieselbe Form wie grob_lesen.
    So lassen sich fein und grob unmittelbar vergleichen.
    """
    ergebnis = {}
    for nr, (monat, pfad) in enumerate(monate_dateien(ordner)):
        stunden, _, _ = stunden_lesen(pfad, monat, nr == 0, erste_spalten, zeitzone)
        for name, werte in stunden.items():
            for zeitpunkt, wert in werte.items():
                tag = ergebnis.setdefault(zeitpunkt.date(), {})
                tag[name] = tag.get(name, 0.0) + wert

    # Die einzeln nachgeladenen Tage ERSETZEN den jeweiligen Tag, sie werden
    # nicht dazugezaehlt. In der Monatsdatei ist er leer - aber wer das
    # voraussetzt, addiert nach einem erneuten Lauf doppelt.
    for tag, pfad in luecken_dateien(ordner):
        stunden, _, _ = stunden_lesen(pfad, tag.replace(day=1), False,
                                      erste_spalten, zeitzone, start_tag=tag)
        neu_tag = {}
        for name, werte in stunden.items():
            for zeitpunkt, wert in werte.items():
                if zeitpunkt.date() == tag:
                    neu_tag[name] = neu_tag.get(name, 0.0) + wert
        if neu_tag:
            ergebnis[tag] = neu_tag
    return ergebnis


def leistung_lesen(pfad, monat, ist_erste, spaltenwahl, zeitzone, start_tag=None):
    """
    {name: {Stunde: (Mittel, Min, Max)}} in WATT - die Leistung, nicht die
    Energie.

    Home Assistant fuehrt Leistung als Mittelwertstatistik: je Stunde ein
    Mittel und dazu Minimum und Maximum, die als Band um die Linie erscheinen.
    Beides koennen wir aus den Viertelstundenwerten bilden - die Spitze eines
    Tages bleibt so wenigstens als Maximum erhalten, auch wenn das Mittel sie
    glaettet.
    """
    kopf, zeilen, einheit = csv_lesen(pfad)
    if not zeilen:
        return {}, einheit
    faktor = 1000.0 if einheit == "kW" else 1.0
    tage = sum(1 for z in zeilen if uhrzeit(z[0]) == (0, 0))
    tag = start_tag or startdatum(monat, tage, ist_erste)
    spalten = spaltenwahl(kopf)

    roh = {name: {} for name in spalten}
    for z in zeilen:
        zeit = uhrzeit(z[0])
        if zeit is None:
            continue
        stunde = stunde_von(zeit)
        for name, i in spalten.items():
            w = zahl(z[i]) if len(z) > i else None
            if w is None:
                continue
            zeitpunkt = datetime(tag.year, tag.month, tag.day, stunde, 0,
                                 tzinfo=zeitzone)
            roh[name].setdefault(zeitpunkt, []).append(w * faktor)
        if zeit == (0, 0):
            tag += timedelta(days=1)

    return {name: {zp: (sum(v) / len(v), min(v), max(v))
                   for zp, v in werte.items()}
            for name, werte in roh.items()}, einheit


def leistung_differenz_lesen(pfad, monat, ist_erste, plus, minus, zeitzone,
                             start_tag=None):
    """
    {Stunde: (Mittel, Min, Max)} der DIFFERENZ zweier Spalten, in Watt.

    Gedacht fuer die vorzeichenbehaftete Netzleistung: Bezug minus
    Einspeisung, positiv bei Bezug, negativ bei Einspeisung - so, wie Home
    Assistant sie in der Karte "Stromquellen" zeichnet.

    Die Differenz wird je ZEILE gebildet, nicht erst aus den Stundenmitteln.
    Das ist nicht dasselbe: In einer Stunde, in der zur Halbzeit von Bezug auf
    Einspeisung gewechselt wird, heben sich die Mittelwerte gegenseitig auf,
    waehrend Minimum und Maximum die beiden Aeste weiterhin zeigen.
    """
    kopf, zeilen, einheit = csv_lesen(pfad)
    if not zeilen:
        return {}, einheit
    faktor = 1000.0 if einheit == "kW" else 1.0
    spalten = erste_spalten(kopf)
    i_plus = next((i for name, i in spalten.items() if plus in name), None)
    i_minus = next((i for name, i in spalten.items() if minus in name), None)
    if i_plus is None or i_minus is None:
        return {}, einheit

    tage = sum(1 for z in zeilen if uhrzeit(z[0]) == (0, 0))
    tag = start_tag or startdatum(monat, tage, ist_erste)
    roh = {}
    for z in zeilen:
        zeit = uhrzeit(z[0])
        if zeit is None:
            continue
        a = zahl(z[i_plus]) if len(z) > i_plus else None
        b = zahl(z[i_minus]) if len(z) > i_minus else None
        if a is not None or b is not None:
            zeitpunkt = datetime(tag.year, tag.month, tag.day,
                                 stunde_von(zeit), 0, tzinfo=zeitzone)
            roh.setdefault(zeitpunkt, []).append(
                ((a or 0.0) - (b or 0.0)) * faktor)
        if zeit == (0, 0):
            tag += timedelta(days=1)

    return {zp: (sum(v) / len(v), min(v), max(v)) for zp, v in roh.items()}, einheit


def leistungsreihe_aufbereiten(quelle, name, beschreibung, werte):
    """Eine Mittelwertstatistik fuer Home Assistant - ohne Summe."""
    eintraege = []
    for zeitpunkt in sorted(werte):
        mittel, kleinste, groesste = werte[zeitpunkt]
        eintraege.append({"start": zeitpunkt.isoformat(),
                          "mean": round(mittel, 1),
                          "min": round(kleinste, 1),
                          "max": round(groesste, 1)})
    return {
        "metadata": {
            "statistic_id": f"{quelle}:{name}", "name": beschreibung,
            "source": quelle, "unit_of_measurement": "W",
            "unit_class": "power", "has_sum": False, "mean_type": 1,
        },
        "stats": eintraege,
    }


def wr_spalten(kopf):
    """Alle Spalten der Wechselrichter-Datei: Anlagensumme und je Geraet eine."""
    spalten = {}
    for i, name in enumerate(kopf):
        if not i or not name:
            continue
        spalten[name.split("/")[0].strip()] = i
    return spalten


def anlagenspalte_finden(je_monat):
    """
    Welche Spalte ist die Anlagensumme? Die mit der groessten Gesamtsumme -
    sie enthaelt alle Geraete und ist damit immer die groesste.
    """
    summen = {}
    for stunden in je_monat.values():
        for name, werte in stunden.items():
            summen[name] = summen.get(name, 0.0) + sum(werte.values())
    if not summen:
        return None, []
    anlage = max(summen, key=summen.get)
    return anlage, sorted(n for n in summen if n != anlage)



# ============================================================================
# Teil 2 - Reihen fuer den Import aufbereiten
# ============================================================================

def reihe_aufbereiten(quelle, name, beschreibung, werte):
    stunden = sorted(werte)
    summe = 0.0
    eintraege = []
    for zeitpunkt in stunden:
        summe += werte[zeitpunkt]
        eintraege.append({"start": zeitpunkt.isoformat(),
                          "state": round(summe, 4), "sum": round(summe, 4)})
    return {
        "metadata": {
            "statistic_id": f"{quelle}:{name}", "name": beschreibung,
            "source": quelle, "unit_of_measurement": "kWh",
            "unit_class": "energy", "has_sum": True, "mean_type": 0,
        },
        "stats": eintraege,
    }



# ============================================================================
# Teil 3 - Geraeteaufteilung beurteilen
# ============================================================================

def monat_bewerten(anlage_kwh, geraete_kwh):
    """
    Bewertet einen einzelnen Monat.
    anlage_kwh: Anlagensumme, geraete_kwh: {Geraetename: kWh}
    """
    aktiv = sorted(n for n, w in geraete_kwh.items()
                   if anlage_kwh and w > anlage_kwh * SCHWELLE_AKTIV)
    summe = sum(geraete_kwh.values())
    verhaeltnis = summe / anlage_kwh if anlage_kwh else None

    if not anlage_kwh:
        lage = "keine_erzeugung"
    elif verhaeltnis is None:
        lage = "unbekannt"
    elif (abs(verhaeltnis - 1) <= TOLERANZ
            or abs(summe - anlage_kwh) <= TOLERANZ_KWH):
        lage = "stimmig"
    else:
        lage = "unstimmig"

    return {"anlage_kwh": round(anlage_kwh, 1),
            "geraete_kwh": {n: round(w, 1) for n, w in geraete_kwh.items()},
            "aktiv": aktiv, "verhaeltnis": None if verhaeltnis is None else round(verhaeltnis, 4),
            "lage": lage}


def abschnitte_bilden(monate):
    """
    Fasst aufeinanderfolgende Monate mit gleicher Lage zu Abschnitten zusammen.
    monate: {"JJJJ-MM": Bewertung} - sortiert verarbeitet.
    """
    abschnitte = []
    for schluessel in sorted(monate):
        b = monate[schluessel]
        if b["lage"] == "keine_erzeugung":
            # Monate ohne Erzeugung sagen nichts aus und brechen keinen
            # Abschnitt auf - sie werden dem laufenden zugeschlagen.
            if abschnitte:
                abschnitte[-1]["bis"] = schluessel
                abschnitte[-1]["monate"].append(schluessel)
            continue

        kennzeichen = (tuple(b["aktiv"]), b["lage"])
        if abschnitte and abschnitte[-1]["kennzeichen"] == kennzeichen:
            abschnitte[-1]["bis"] = schluessel
            abschnitte[-1]["monate"].append(schluessel)
            abschnitte[-1]["verhaeltnisse"].append(b["verhaeltnis"])
        else:
            abschnitte.append({
                "kennzeichen": kennzeichen, "von": schluessel, "bis": schluessel,
                "aktiv": list(b["aktiv"]), "lage": b["lage"],
                "monate": [schluessel], "verhaeltnisse": [b["verhaeltnis"]],
            })

    for a in abschnitte:
        werte = [v for v in a["verhaeltnisse"] if v is not None]
        a["verhaeltnis_mittel"] = round(sum(werte) / len(werte), 4) if werte else None
        del a["kennzeichen"]
        del a["verhaeltnisse"]
    return abschnitte


def ereignisse_ableiten(abschnitte):
    """Was hat sich zwischen zwei Abschnitten geaendert? Formuliert als Rueckfrage."""
    ereignisse = []
    for vorher, nachher in zip(abschnitte, abschnitte[1:]):
        dazu = [g for g in nachher["aktiv"] if g not in vorher["aktiv"]]
        weg = [g for g in vorher["aktiv"] if g not in nachher["aktiv"]]
        for g in dazu:
            ereignisse.append({
                "ab": nachher["von"], "geraet": g, "art": "neu",
                "frage": f"Ab {nachher['von']} liefert '{g}' erstmals Werte. "
                         f"Kam dort ein Wechselrichter dazu?"})
        for g in weg:
            ereignisse.append({
                "ab": nachher["von"], "geraet": g, "art": "weg",
                "frage": f"Ab {nachher['von']} liefert '{g}' keine Werte mehr. "
                         f"Wurde er abgeschaltet, getauscht oder ausgebaut?"})
        if vorher["lage"] != nachher["lage"]:
            ereignisse.append({
                "ab": nachher["von"], "geraet": None, "art": "lagewechsel",
                "frage": f"Ab {nachher['von']} passen die Geraetereihen "
                         f"{'wieder ' if nachher['lage'] == 'stimmig' else 'nicht mehr '}"
                         f"zur Anlagensumme."})
    return ereignisse


def vorschlag_bilden(abschnitte, zuordnung):
    """
    Schlaegt je Abschnitt vor, woher die Geraetereihen kommen sollen.
    zuordnung: {Geraetename: Reihenname}
    """
    vorschlag = []
    for a in abschnitte:
        eintrag = {"von": a["von"], "bis": a["bis"], "aktiv": a["aktiv"],
                   "lage": a["lage"], "verhaeltnis": a["verhaeltnis_mittel"]}

        if a["lage"] == "stimmig":
            eintrag["quelle"] = "geraetespalten"
            eintrag["begruendung"] = "Die Geraetereihen ergeben die Anlagensumme."

        elif len(a["aktiv"]) == 1:
            geraet = a["aktiv"][0]
            eintrag["quelle"] = "anlagensumme"
            eintrag["ziel"] = zuordnung.get(geraet, geraet)
            eintrag["begruendung"] = (
                f"Nur '{geraet}' war aktiv, seine Reihe passt aber nicht zur "
                f"Anlagensumme (Verhaeltnis {a['verhaeltnis_mittel']}). Wenn wirklich "
                f"nur dieses Geraet lief, IST die Anlagensumme seine Erzeugung.")

        else:
            eintrag["quelle"] = "keine"
            eintrag["begruendung"] = (
                f"Mehrere Geraete aktiv, aber ihre Summe ergibt nicht die "
                f"Anlagensumme (Verhaeltnis {a['verhaeltnis_mittel']}). Eine "
                f"Aufteilung laesst sich daraus nicht ableiten - dieser Zeitraum "
                f"bekommt keine Geraetereihen. Die Anlagensumme bleibt korrekt.")

        vorschlag.append(eintrag)
    return vorschlag


def regel_fuer(monat, regeln):
    """Welche Regel gilt fuer diesen Monat? monat als 'JJJJ-MM'."""
    for r in regeln:
        if r["von"] <= monat and (not r.get("bis") or monat <= r["bis"]):
            return r
    return None
