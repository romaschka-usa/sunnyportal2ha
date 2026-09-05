#!/usr/bin/env python3
"""
3_transform - aus den Portal-CSV wird ein importierbarer Datensatz
===================================================================

Version         : 2.4.0
Letzte Aenderung: 2026-09-02

Beschreibung
------------
Schritt 3 der Kette. Liest die monatsweisen CSV-Dateien aus dem Portal und
erzeugt daraus je Groesse eine stuendliche Energiereihe, wie Home Assistant
sie fuer seine Langzeitstatistik braucht.

    bilanz/JJJJ-MM.csv           Anlagensummen inkl. Netzeinspeisung
    wechselrichter/JJJJ-MM.csv   Gesamtanlage und die einzelnen Geraete
    geraeteregeln.json           bestaetigte Aufteilung aus Schritt 2
                    |
                    v
    import/sunnyportal2ha_<name>.json

Was dabei passiert
------------------
1. EINHEIT LESEN. Die Kopfzeile sagt, ob die Werte in [W] oder [kW] stehen -
   das wechselt von Monat zu Monat.

2. LEISTUNG WIRD ENERGIE. Die Werte sind Mittelwerte je Viertelstunde.
   Energie = Leistung * 0,25 h.

3. DATUM ERGAENZEN. Die CSV enthaelt nur Uhrzeiten, und zwar das ENDE des
   Intervalls: ein Tag laeuft von 00:15 bis 00:00.

4. AUF STUNDEN VERDICHTEN. Vier Viertelstunden ergeben eine Stunde. Bei
   Energiemengen ist das verlustfrei. Home Assistant speichert
   Langzeitstatistiken ausschliesslich stuendlich; feiner geht nicht.

5. LUECKEN BLEIBEN LUECKEN. Tage ohne Werte werden UEBERSPRUNGEN und nicht
   als Null ausgegeben. Eine Null waere die Aussage "hat nichts erzeugt",
   und das ist etwas anderes als "wir wissen es nicht".

6. SUMMEN BILDEN. Home Assistant fuehrt Zaehler als fortlaufende Summe.

Die Geraeteaufteilung kommt aus Schritt 2
-----------------------------------------
Dieses Skript entscheidet nichts ueber die Aufteilung auf einzelne
Wechselrichter. Es wendet an, was in geraeteregeln.json steht und dort mit
"bestaetigt": true freigegeben wurde. Fehlt die Datei oder ist sie nicht
bestaetigt, bricht der Lauf ab und verweist auf 2_analyse.py.

Erzeugte Reihen
---------------
    sunnyportal2ha:pv_gesamt          PV-Erzeugung, ganze Anlage
    sunnyportal2ha:netzbezug          aus dem Netz bezogen
    sunnyportal2ha:einspeisung        ins Netz eingespeist
    sunnyportal2ha:verbrauch_gesamt   Gesamtverbrauch des Hauses
    sunnyportal2ha:direktverbrauch    direkt verbrauchte PV-Energie
    sunnyportal2ha:batterie_ladung    in den Speicher geladen
    sunnyportal2ha:batterie_entladung aus dem Speicher entnommen
    sunnyportal2ha:wr_<name>          je Wechselrichter eine Reihe

Das sind EXTERNE Statistiken (Doppelpunkt statt Punkt). Sie stehen neben den
vorhandenen Sensoren und veraendern diese nicht.

Zeitumstellung
--------------
Das Portal liefert auch an den Umstellungstagen 96 Viertelstunden, obwohl der
Oktobertag 100 und der Maerztag 92 haette. An diesen beiden Tagen im Jahr kann
die Zuordnung um eine Stunde verschoben sein - eine Eigenheit der Quelle.

Voraussetzungen
---------------
    Python 3.9 oder neuer

Aufruf
------
    python 3_transform.py                 umrechnen
    python 3_transform.py --von 2025-01   Zeitraum eingrenzen
    python 3_transform.py --leistung      zusaetzlich die Leistungsreihen
    python 3_transform.py --bericht       nichts schreiben, nur berichten

Ablage
------
    import/sunnyportal2ha_<name>.json   je Reihe eine Datei
    import/_bericht.json                Kennzahlen und Luecken

Aenderungen
-----------
2.5.0  2026-09-05  Batterieladung und Batterieentladung werden mitgenommen.
                   Anlagen mit Speicher verloren sie bisher stillschweigend:
                   Die Spalten stehen in der Energiebilanz, standen aber
                   nicht in AUS_BILANZ - ohne Meldung, ohne Fehlbetrag in
                   irgendeiner Pruefsumme, weil die Plausibilitaet je Reihe
                   rechnet und eine gar nicht gelesene Reihe nicht auffaellt.
2.4.0  2026-09-02  Zusaetzlich die vorzeichenbehaftete Netzleistung
                   (netz_leistung): Bezug positiv, Einspeisung negativ - so
                   wie die Karte "Stromquellen" sie zeichnet.
2.3.0  2026-09-02  --leistung erzeugt jetzt ALLE Reihen der Energiebilanz
                   als Leistung, nicht nur die PV-Erzeugung. Ohne Netzbezugs-
                   und Netzeinspeiseleistung bleibt die Karte "Stromquellen"
                   im Energie-Dashboard vor dem Schnitt leer, und der dort
                   angezeigte Verbrauch ist keine Messung, sondern der Rest
                   einer unvollstaendigen Rechnung.
2.2.2  2026-09-02  Lesbare Namen fuer die Leistungsreihen.
2.2.1  2026-09-02  Die Gegenprobe rechnet nur noch die Energiereihen - die
                   neuen Leistungsreihen tragen keine Summe.
2.2.0  2026-09-02  Mit --leistung entstehen zusaetzlich Leistungsreihen in
                   Watt: je Stunde Mittelwert, Minimum und Maximum. Die
                   Quelle ist ohnehin Leistung - Energie entsteht erst durch
                   die Umrechnung. Standardmaessig aus, damit der
                   veroeffentlichte Weg unveraendert bleibt.
2.1.1  2026-09-02  Die Meldung "Tage ohne Werte" kommt jetzt aus dem
                   Ergebnis statt aus den Monatsdateien - sonst gilt ein
                   nachgeladener Tag weiter als Luecke. Und die Geraeteregeln
                   zaehlen Monate statt Dateien.
2.1.0  2026-09-02  Liest die einzeln nachgeladenen Lueckentage mit. Bisher
                   nur die Monatsdateien - damit fehlte der Maerz 2026
                   vollstaendig, rund 1700 kWh, ohne dass etwas nach einem
                   Fehler aussah.
2.0.0  2026-09-01  Analyse und Bestaetigung nach 2_analyse.py ausgelagert;
                   Lesefunktionen ins Modul daten.py
1.1.0  2026-09-01  Geraeteaufteilung wird erkannt statt fest eingetragen
1.0.0  2026-09-01  Erste Fassung
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

import daten

__version__ = "2.5.0"
__stand__ = "2026-09-05"

HIER = os.path.dirname(os.path.abspath(__file__))
BILANZ = os.path.join(HIER, "bilanz")
WECHSELRICHTER = os.path.join(HIER, "wechselrichter")
AUSGABE = os.path.join(HIER, "import")
REGELN = os.path.join(HIER, "geraeteregeln.json")

QUELLE = "sunnyportal2ha"
ZEITZONE = datetime.now().astimezone().tzinfo

AUS_BILANZ = {
    "PV-Erzeugung": ("pv_gesamt", "PV-Erzeugung (Sunny Portal)"),
    "Netzbezug": ("netzbezug", "Netzbezug (Sunny Portal)"),
    "Netzeinspeisung": ("einspeisung", "Netzeinspeisung (Sunny Portal)"),
    "Gesamtverbrauch": ("verbrauch_gesamt", "Gesamtverbrauch (Sunny Portal)"),
    "Direktverbrauch": ("direktverbrauch", "Direktverbrauch (Sunny Portal)"),
    "Batterieladung": ("batterie_ladung", "Batterieladung (Sunny Portal)"),
    "Batterieentladung": ("batterie_entladung",
                          "Batterieentladung (Sunny Portal)"),
}


# Wie die Leistungsreihen heissen sollen. Die Beschriftung landet in Home
# Assistant und taucht dort in den Auswahlfeldern auf - sie darf also nicht
# nach Dateiname klingen.
LEISTUNG_NAMEN = {
    "pv_gesamt": "PV-Leistung gesamt (Sunny Portal)",
    "netzbezug": "Netzbezugsleistung (Sunny Portal)",
    "einspeisung": "Netzeinspeiseleistung (Sunny Portal)",
    "verbrauch_gesamt": "Verbrauchsleistung (Sunny Portal)",
    "direktverbrauch": "Direktverbrauchsleistung (Sunny Portal)",
    "batterie_ladung": "Batterieladeleistung (Sunny Portal)",
    "batterie_entladung": "Batterieentladeleistung (Sunny Portal)",
}


def main():
    p = argparse.ArgumentParser(
        description="Portal-CSV in importierbare Stundenreihen umrechnen")
    p.add_argument("--von", help="erster Monat JJJJ-MM")
    p.add_argument("--bis", help="letzter Monat JJJJ-MM")
    p.add_argument("--leistung", action="store_true",
                   help="zusaetzlich Leistungsreihen (Watt, Stundenmittel mit "
                        "Minimum und Maximum) erzeugen")
    p.add_argument("--bericht", action="store_true",
                   help="nichts schreiben, nur berichten")
    args = p.parse_args()

    print("=" * 96)
    print(f"Schritt 3 - Transformation  (Version {__version__}, {__stand__})")
    print("=" * 96)

    def gefiltert(liste):
        raus = []
        for monat, pfad, ist_erste, start_tag in liste:
            s = f"{monat:%Y-%m}"
            if (args.von and s < args.von) or (args.bis and s > args.bis):
                continue
            raus.append((monat, pfad, ist_erste, start_tag))
        return raus

    def anzahl_beschreiben(liste):
        monate = sum(1 for e in liste if e[3] is None)
        tage = len(liste) - monate
        text = f"{monate} Monatsdateien"
        return text + (f" und {tage} nachgeladene Tage" if tage else "")

    def bilanz_wahl(kopf):
        aus = {}
        for suchtext, (name, _) in AUS_BILANZ.items():
            for i, spalte in enumerate(kopf):
                if i and suchtext in spalte:
                    aus[name] = i
                    break
        return aus

    # ---- Regeln aus Schritt 2 ---------------------------------------------
    if not os.path.exists(REGELN):
        print(f"\nABBRUCH: {os.path.basename(REGELN)} fehlt.")
        print("Bitte zuerst  python 2_analyse.py  laufen lassen.")
        return 2
    with open(REGELN, encoding="utf-8") as f:
        regeln = json.load(f)
    if not regeln.get("bestaetigt"):
        print(f"\nABBRUCH: In {os.path.basename(REGELN)} steht 'bestaetigt': false.")
        print("Bitte die Abschnitte und Fragen dort pruefen, auf true setzen")
        print("und erneut starten. Die Fragen lauten:")
        for frage in regeln.get("fragen") or []:
            print(f"   * {frage}")
        return 2

    # ---- Energiebilanz -----------------------------------------------------
    reihen, bericht = {}, {"monate": {}}
    # fein_dateien liefert Monatsdateien UND nachgeladene Lueckentage, letztere
    # zuletzt: Sie ersetzen den jeweiligen Tag, der in der Monatsdatei leer ist.
    dateien = gefiltert(list(daten.fein_dateien(BILANZ)))
    print(f"\nEnergiebilanz : {anzahl_beschreiben(dateien)}")
    for monat, pfad, ist_erste, start_tag in dateien:
        stunden, leere, einheit = daten.stunden_lesen(
            pfad, monat, ist_erste, bilanz_wahl, ZEITZONE, start_tag)
        for name, werte in stunden.items():
            reihen.setdefault(name, {}).update(werte)
        if start_tag is None:
            bericht["monate"][f"{monat:%Y-%m}"] = {"einheit": einheit,
                                                   "leere_tage": leere}

    # ---- Wechselrichter ----------------------------------------------------
    wr_dateien = gefiltert(list(daten.fein_dateien(WECHSELRICHTER)))
    print(f"Wechselrichter: {anzahl_beschreiben(wr_dateien)}")

    if wr_dateien:
        zuordnung = regeln["geraete"]
        anlage = regeln["anlagenspalte"]
        angewandt = {}
        for monat, pfad, ist_erste, start_tag in wr_dateien:
            schluessel = f"{monat:%Y-%m}"
            regel = daten.regel_fuer(schluessel, regeln["abschnitte"])
            if regel is None:
                continue
            stunden, _, _ = daten.stunden_lesen(
                pfad, monat, ist_erste, daten.wr_spalten, ZEITZONE, start_tag)
            # Monate zaehlen, nicht Dateien - sonst zaehlen die nachgeladenen
            # Tage ihren Monat mehrfach.
            angewandt.setdefault(regel["quelle"], set()).add(schluessel)
            if regel["quelle"] == "geraetespalten":
                for g, r in zuordnung.items():
                    reihen.setdefault(r, {}).update(stunden.get(g, {}))
            elif regel["quelle"] == "anlagensumme" and regel.get("ziel"):
                reihen.setdefault(regel["ziel"], {}).update(stunden.get(anlage, {}))
            # "keine": dieser Zeitraum bekommt keine Geraetereihen
        print("Geraeteregeln : " +
              ", ".join(f"{len(m)} Monate {q}" for q, m in sorted(angewandt.items())))

    if not reihen:
        print("\nKeine Daten gefunden. Erst  python 1_export.py alles  laufen lassen.")
        return 1

    # ---- Ausgabe -----------------------------------------------------------
    beschreibungen = {n: t for _, (n, t) in AUS_BILANZ.items()}
    for g, r in (regeln.get("geraete") or {}).items():
        beschreibungen[r] = f"PV-Erzeugung {g} (Sunny Portal)"

    print(f"\n{'Reihe':<46}{'Stunden':>9}  {'von':<12}{'bis':<12}{'kWh':>11}")
    print("-" * 96)

    zusammenfassung = {}
    if not args.bericht:
        os.makedirs(AUSGABE, exist_ok=True)
    for name in sorted(reihen):
        werte = reihen[name]
        if not werte:
            continue
        stunden = sorted(werte)
        gesamt = sum(werte.values())
        print(f"{QUELLE + ':' + name:<46}{len(stunden):>9}  "
              f"{stunden[0]:%Y-%m-%d}  {stunden[-1]:%Y-%m-%d}  {gesamt:>11.1f}")
        zusammenfassung[f"{QUELLE}:{name}"] = {
            "stunden": len(stunden), "von": stunden[0].isoformat(),
            "bis": stunden[-1].isoformat(), "summe_kwh": round(gesamt, 1)}
        if not args.bericht:
            paket = daten.reihe_aufbereiten(QUELLE, name,
                                            beschreibungen.get(name, name), werte)
            with open(os.path.join(AUSGABE, f"{QUELLE}_{name}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(paket, f, indent=1, ensure_ascii=False)

    # ---- Leistungsreihen ---------------------------------------------------
    # Die Quelle ist Leistung; Energie entsteht erst durch die Umrechnung oben.
    # Wer die Kurve selbst will, bekommt sie hier - als Stundenmittel, denn
    # feiner kann die Langzeitstatistik von Home Assistant nicht.
    if args.leistung:
        leistungen, leistung_namen = {}, {}
        def leistung_wahl(kopf):
            """Dieselben Spalten wie bei der Energie, nur als Leistung."""
            aus = {}
            for suchtext, (name, _) in AUS_BILANZ.items():
                for i, spalte in enumerate(kopf):
                    if i and suchtext in spalte:
                        aus[name + "_leistung"] = i
                        break
            return aus

        for monat, pfad, ist_erste, start_tag in dateien:
            werte, _ = daten.leistung_lesen(pfad, monat, ist_erste,
                                            leistung_wahl, ZEITZONE, start_tag)
            for name, stunden in werte.items():
                leistungen.setdefault(name, {}).update(stunden)
                leistung_namen[name] = LEISTUNG_NAMEN.get(
                    name[:-len("_leistung")], name)

            # Die vorzeichenbehaftete Netzleistung. Home Assistant zeichnet in
            # der Karte "Stromquellen" nicht Bezug und Einspeisung getrennt,
            # sondern eine Linie: positiv bei Bezug, negativ bei Einspeisung.
            netto, _ = daten.leistung_differenz_lesen(
                pfad, monat, ist_erste, "Netzbezug", "Netzeinspeisung",
                ZEITZONE, start_tag)
            if netto:
                leistungen.setdefault("netz_leistung", {}).update(netto)
                leistung_namen["netz_leistung"] = (
                    "Netzleistung, Bezug positiv (Sunny Portal)")
        for monat, pfad, ist_erste, start_tag in wr_dateien:
            regel = daten.regel_fuer(f"{monat:%Y-%m}", regeln["abschnitte"])
            if regel is None or regel["quelle"] != "geraetespalten":
                continue
            werte, _ = daten.leistung_lesen(pfad, monat, ist_erste,
                                            daten.wr_spalten, ZEITZONE, start_tag)
            for geraet, stunden in werte.items():
                ziel = (regeln.get("geraete") or {}).get(geraet)
                if ziel:
                    leistungen.setdefault(ziel + "_leistung", {}).update(stunden)
                    leistung_namen[ziel + "_leistung"] = \
                        f"PV-Leistung {geraet} (Sunny Portal)"

        print(f"\n{'Leistungsreihe':<46}{'Stunden':>9}  {'von':<12}{'bis':<12}"
              f"{'Spitze W':>11}")
        print("-" * 96)
        for name in sorted(leistungen):
            werte = leistungen[name]
            if not werte:
                continue
            stunden = sorted(werte)
            spitze = max(v[2] for v in werte.values())
            print(f"{QUELLE + ':' + name:<46}{len(stunden):>9}  "
                  f"{stunden[0]:%Y-%m-%d}  {stunden[-1]:%Y-%m-%d}  {spitze:>11.0f}")
            zusammenfassung[f"{QUELLE}:{name}"] = {
                "stunden": len(stunden), "von": stunden[0].isoformat(),
                "bis": stunden[-1].isoformat(), "spitze_w": round(spitze, 1)}
            if not args.bericht:
                paket = daten.leistungsreihe_aufbereiten(
                    QUELLE, name, leistung_namen.get(name, name), werte)
                with open(os.path.join(AUSGABE, f"{QUELLE}_{name}.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(paket, f, indent=1, ensure_ascii=False)

    bericht["reihen"] = zusammenfassung
    bericht["geraeteregeln"] = regeln.get("abschnitte")
    bericht["erstellt"] = datetime.now().isoformat(timespec="seconds")
    if not args.bericht:
        with open(os.path.join(AUSGABE, "_bericht.json"), "w", encoding="utf-8") as f:
            json.dump(bericht, f, indent=1, ensure_ascii=False)

    # ---- Gegenprobe --------------------------------------------------------
    gesamt = zusammenfassung.get(f"{QUELLE}:pv_gesamt", {}).get("summe_kwh")
    # Nur Energiereihen gegenrechnen - die Leistungsreihen tragen keine Summe.
    wr_summe = sum(v["summe_kwh"] for k, v in zusammenfassung.items()
                   if k.startswith(f"{QUELLE}:wr_") and "summe_kwh" in v)
    if gesamt and wr_summe:
        abw = abs(wr_summe - gesamt) / gesamt * 100
        print(f"\nGegenprobe: Wechselrichter zusammen {wr_summe:.1f} kWh gegen "
              f"Energiebilanz {gesamt:.1f} kWh  ->  {abw:.3f} %")
        if abw > 1:
            print("   Hinweis: Eine Abweichung ist zu erwarten, wenn ein Zeitraum")
            print("   bewusst keine Geraetereihen bekommen hat.")

    # Welche Tage am Ende ohne Werte blieben, sagt das ERGEBNIS - nicht die
    # Monatsdateien. Ein Tag, den die Monatsdatei leer laesst, kann durch eine
    # nachgeladene Tagesdatei gefuellt sein; wer nur die Monatsdateien fragt,
    # meldet den Maerz 2026 als Luecke, obwohl er vollstaendig ist.
    mit_werten = {z.date().isoformat() for werte in reihen.values() for z in werte}
    leer = sorted(t for m in bericht["monate"].values() for t in m["leere_tage"]
                  if t not in mit_werten)
    bericht["leere_tage"] = leer
    if leer:
        print(f"\nTage ohne Werte, uebersprungen ({len(leer)}):")
        for i in range(0, min(len(leer), 40), 10):
            print("   " + "  ".join(leer[i:i + 10]))
        if len(leer) > 40:
            print(f"   ... und {len(leer) - 40} weitere (vollstaendig im Bericht)")

    print("\n" + "=" * 96)
    if args.bericht:
        print("Nur-Bericht-Modus, es wurde nichts geschrieben.")
    else:
        print(f"Geschrieben nach: {AUSGABE}")
        print("Naechster Schritt: 4_import.py - laeuft ohne --los nur als Probelauf.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
