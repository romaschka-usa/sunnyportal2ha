#!/usr/bin/env python3
"""
2_analyse - Bestand prüfen und die Geräteaufteilung klären
===========================================================

Version         : 1.1.0
Letzte Aenderung: 2026-09-01

Beschreibung
------------
Schritt 2 der Kette. Zwischen Export und Umrechnung steht die Frage, was
ueberhaupt da ist - auf beiden Seiten:

  PORTAL   Welcher Wechselrichter hat wann Werte geliefert? Ergeben die
           Geraetereihen zusammen die Anlagensumme? Daraus entsteht
           geraeteregeln.json, das der Anlagenbetreiber BESTAETIGEN muss.

  HOME     Welche Langzeitstatistiken gibt es schon? Ab wann reichen sie
  ASSISTANT zurueck, wo sind Luecken? Welche verwendet das Energie-Dashboard?
           Das entscheidet, was importiert werden muss und was nicht.

Dieses Skript SCHREIBT NICHTS in Home Assistant und veraendert keine
exportierten Daten. Es liest, beurteilt und legt einen Vorschlag vor.

Warum ueberhaupt bestaetigen?
-----------------------------
Bei der Anlage, an der dieses Projekt entstand, lieferte die Analyse-Seite
ueber zwanzig Monate hinweg exakt ein Viertel der Anlagensumme als Ertrag des
einen Wechselrichters - ein Faktor vier, kein Rauschen. Die Anlagensumme selbst
war korrekt. Wer das nicht bemerkt, importiert zwanzig Monate mit einem Viertel
des tatsaechlichen Ertrags, und im Dashboard sieht es plausibel aus.

Erkannt werden kann so etwas. Entschieden werden muss es vom Menschen: Nur er
weiss, ob im Maerz wirklich ein Geraet dazukam, ausfiel oder getauscht wurde.

Voraussetzungen
---------------
    Python 3.9 oder neuer
    pip install requests websocket-client
    zugangsdaten.ini - der Abschnitt [homeassistant] ist optional

Aufruf
------
    python 2_analyse.py                nur die Portaldaten beurteilen
    python 2_analyse.py --ha           zusaetzlich Home Assistant abfragen
    python 2_analyse.py --neu          Geraeteanalyse neu erstellen,
                                       vorhandene Bestaetigung verwerfen
    python 2_analyse.py --ha-alles     in HA jede Statistik untersuchen,
                                       nicht nur die energiebezogenen

Ablage
------
    geraeteregeln.json      Abschnitte, Fragen, Vorschlag, Bestaetigung
    ha/inventar.json        alle Statistiken mit Zeitraum und Luecken
    ha/kennungen.txt        nur die Namen, zum Durchsehen
    ha/energie_dashboard.json   was das Dashboard verwendet

Naechster Schritt
-----------------
geraeteregeln.json pruefen, "bestaetigt" auf true setzen, dann 3_transform.py

Aenderungen
-----------
1.2.0  2026-09-05  Die Geraeteanalyse liest die nachgeladenen Lueckentage
                   mit. Bisher nur die Monatsdateien - fuer einen Monat,
                   dessen Feinkurve erst die Lueckensuche geholt hat, wies
                   geraeteregeln.json daher einen viel zu kleinen Ertrag
                   aus (bei dieser Anlage 329 statt 1252 kWh im Maerz
                   2026). Die Aufteilung stimmte trotzdem, weil Anlagen-
                   und Geraetespalte gleich verkuerzt sind - aber die Zahl
                   ist das, was der Betreiber bestaetigen soll.
1.1.0  2026-09-02  Plausibilitaetspruefung ueber alle vier Aufloesungen.
                   Sie vergleicht Feinkurve, Tages-, Monats- und Jahreswerte
                   gegeneinander und benennt jede Luecke mit Zeitraum, Reihe
                   und Fehlbetrag in kWh - Ergebnis in plausibilitaet.json.
1.0.0  2026-09-01  Erste Fassung; vereint die frueheren Skripte ha_inventar.py
                   und ha_energie.py mit der Geraeteerkennung aus transform.py
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import daten

__version__ = "1.2.0"
__stand__ = "2026-09-05"

HIER = os.path.dirname(os.path.abspath(__file__))
WECHSELRICHTER = os.path.join(HIER, "wechselrichter")
REGELN = os.path.join(HIER, "geraeteregeln.json")
HA_ORDNER = os.path.join(HIER, "ha")

QUELLE = "sunnyportal2ha"
ZEITZONE = datetime.now().astimezone().tzinfo

ENERGIE_EINHEITEN = {"kWh", "Wh", "MWh", "W", "kW"}
ENERGIE_WOERTER = ("pv", "solar", "energie", "energy", "strom", "netz", "grid",
                   "einspeis", "bezug", "verbrauch", "consumption", "power",
                   "leistung", "ertrag", "sma", "wechselrichter", "inverter",
                   "batterie", "battery", "speicher", "wallbox", "zaehler",
                   "zähler", "meter")


def speichern(ordner, name, inhalt):
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, name)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(inhalt)
    return pfad


# ============================================================================
# Teil 1 - Geraeteaufteilung im Portal
# ============================================================================

def geraete_analysieren(neu_erstellen=False):
    # fein_dateien liefert Monatsdateien UND die nachgeladenen Lueckentage.
    # Nur die Monatsdateien zu lesen unterschlaegt genau die Zeitraeume, fuer
    # die die Lueckensuche gebaut wurde - der Monat sieht dann viel zu klein
    # aus, und diese Zahl legt geraeteregeln.json dem Betreiber zur
    # Bestaetigung vor.
    dateien = list(daten.fein_dateien(WECHSELRICHTER))
    if not dateien:
        print(f"\nKeine Monatsdateien in {os.path.basename(WECHSELRICHTER)}/ gefunden.")
        print("Erst  python 1_export.py wechselrichter  laufen lassen.")
        return None

    je_monat = {}
    for monat, pfad, ist_erste, start_tag in dateien:
        stunden, _, _ = daten.stunden_lesen(pfad, monat, ist_erste,
                                            daten.wr_spalten, ZEITZONE, start_tag)
        ziel = je_monat.setdefault(f"{monat:%Y-%m}", {})
        for name, werte in stunden.items():
            # Ein nachgeladener Tag ERSETZT seine Stunden, er addiert nicht.
            ziel.setdefault(name, {}).update(werte)

    anlage, geraete = daten.anlagenspalte_finden(je_monat)
    zuordnung = {g: daten.reihenname(g) for g in geraete}

    bewertungen = {}
    for schluessel, stunden in je_monat.items():
        anlage_kwh = sum(stunden.get(anlage, {}).values())
        geraete_kwh = {g: sum(stunden.get(g, {}).values()) for g in geraete}
        bewertungen[schluessel] = daten.monat_bewerten(anlage_kwh, geraete_kwh)

    abschnitte = daten.abschnitte_bilden(bewertungen)
    fragen = [e["frage"] for e in daten.ereignisse_ableiten(abschnitte)]
    vorschlag = daten.vorschlag_bilden(abschnitte, zuordnung)

    # Eine vorhandene Bestaetigung nicht ueberschreiben, wenn sich nichts
    # geaendert hat - sonst muesste man nach jedem Export erneut bestaetigen.
    alt = {}
    if os.path.exists(REGELN) and not neu_erstellen:
        try:
            with open(REGELN, encoding="utf-8") as f:
                alt = json.load(f)
        except ValueError:
            alt = {}
    unveraendert = (alt.get("abschnitte") == vorschlag
                    and alt.get("geraete") == zuordnung)

    analyse = {
        "erstellt": datetime.now().isoformat(timespec="seconds"),
        "bestaetigt": bool(alt.get("bestaetigt")) if unveraendert else False,
        "hinweis": ("Bitte die Abschnitte und Fragen pruefen. Wenn sie stimmen, "
                    "'bestaetigt' auf true setzen und 3_transform.py starten. "
                    "Einzelne Abschnitte lassen sich von Hand anpassen - "
                    "'quelle' kennt geraetespalten, anlagensumme und keine."),
        "anlagenspalte": anlage,
        "geraete": zuordnung,
        "fragen": fragen,
        "abschnitte": vorschlag,
        "monate": bewertungen,
    }
    return analyse, unveraendert and bool(alt.get("bestaetigt"))


def geraete_ausgeben(analyse, war_bestaetigt):
    print(f"\nAnlagensumme steht in der Spalte : {analyse['anlagenspalte']}")
    print(f"Erkannte Wechselrichter          : {len(analyse['geraete'])}")
    for g, r in analyse["geraete"].items():
        print(f"   {g:<44} -> {QUELLE}:{r}")

    print(f"\n{'Zeitraum':<22}{'aktiv':<44}{'Verh.':>7}  Bewertung")
    print("-" * 96)
    for a in analyse["abschnitte"]:
        aktiv = ", ".join(a["aktiv"]) or "(keins)"
        verh = "-" if a["verhaeltnis"] is None else f"{a['verhaeltnis']:.3f}"
        print(f"{a['von']} bis {a['bis']:<10}{aktiv[:43]:<44}{verh:>7}  "
              f"{a['lage']} -> {a['quelle']}")

    if analyse["fragen"]:
        print("\nBITTE BESTAETIGEN:")
        for f in analyse["fragen"]:
            print(f"   * {f}")

    print("\nVorgehen je Abschnitt:")
    for a in analyse["abschnitte"]:
        print(f"   {a['von']} bis {a['bis']}: {a['quelle']}")
        print(f"      {a['begruendung']}")

    if war_bestaetigt:
        print("\nDiese Aufteilung war bereits bestaetigt und ist unveraendert.")


# ============================================================================
# Teil 2 - Bestand in Home Assistant
# ============================================================================

def ist_energie(eintrag):
    einheit = (eintrag.get("display_unit_of_measurement")
               or eintrag.get("statistics_unit_of_measurement") or "")
    if einheit in ENERGIE_EINHEITEN:
        return True
    text = f"{eintrag.get('statistic_id','')} {eintrag.get('name') or ''}".lower()
    return any(w in text for w in ENERGIE_WOERTER)


def monatsuebersicht(v, ha, kennung, von, bis):
    try:
        roh = ha.statistiken(v, [kennung], von, bis, zeitraum="month")
    except Exception as e:
        return {"fehler": str(e)}
    reihe = roh.get(kennung) or []
    monate = {}
    for eintrag in reihe:
        dt = ha.zeitstempel(eintrag)
        if dt is None:
            continue
        wert = eintrag.get("change")
        if wert is None:
            wert = eintrag.get("sum")
        monate[f"{dt.astimezone():%Y-%m}"] = None if wert is None else round(float(wert), 2)
    if not monate:
        return {"monate": 0}
    schluessel = sorted(monate)
    return {"monate": len(monate), "von": schluessel[0], "bis": schluessel[-1],
            "werte": {s: monate[s] for s in schluessel}}


def rollen_sammeln(prefs):
    rollen = {}

    def merken(kennung, rolle):
        if kennung:
            rollen.setdefault(kennung, set()).add(rolle)

    for quelle in prefs.get("energy_sources") or []:
        art = quelle.get("type")
        # Aeltere HA-Fassungen fuehren Listen, neuere schreiben direkt in die
        # Quelle. Beides lesen, sonst fehlen Netzbezug und Einspeisung.
        for fluss in quelle.get("flow_from") or []:
            merken(fluss.get("stat_energy_from"), "Netzbezug")
        for fluss in quelle.get("flow_to") or []:
            merken(fluss.get("stat_energy_to"), "Einspeisung")
        if art == "grid":
            merken(quelle.get("stat_energy_from"), "Netzbezug")
            merken(quelle.get("stat_energy_to"), "Einspeisung")
        elif art == "solar":
            merken(quelle.get("stat_energy_from"), "PV-Erzeugung")
        elif art == "battery":
            merken(quelle.get("stat_energy_from"), "Batterie Entladung")
            merken(quelle.get("stat_energy_to"), "Batterie Ladung")
        elif art in ("gas", "water"):
            merken(quelle.get("stat_energy_from"), art.capitalize())

    for geraet in prefs.get("device_consumption") or []:
        merken(geraet.get("stat_consumption"),
               f"Verbraucher: {geraet.get('name') or geraet.get('stat_consumption')}")
    return {k: sorted(v) for k, v in rollen.items()}


def ha_analysieren(alles=False, jahre=5, tage=70):
    try:
        import ha
    except SystemExit as e:
        print(f"\n{e}")
        return None
    try:
        info = ha.version()
    except Exception as e:
        print(f"\nHome Assistant nicht erreichbar: {type(e).__name__}: {e}")
        return None

    print(f"\nInstanz  : {info['name']}, HA {info['version']}, {info['zeitzone']}")

    bis = date.today() + timedelta(days=1)
    von_monat = date(bis.year - jahre, 1, 1)
    von_tag = bis - timedelta(days=tage)
    ergebnis = {"instanz": info, "statistiken": {}, "dashboard": {}}

    with ha.Verbindung() as v:
        alle = ha.statistik_kennungen(v)
        print(f"Statistiken insgesamt: {len(alle)}")
        nach_quelle = defaultdict(int)
        for e in alle:
            nach_quelle[e.get("source") or "?"] += 1
        print("   nach Quelle: " + ", ".join(f"{k}={n}" for k, n in sorted(nach_quelle.items())))

        speichern(HA_ORDNER, "kennungen.txt", "\n".join(
            f"{e.get('statistic_id'):<60} "
            f"{(e.get('display_unit_of_measurement') or e.get('statistics_unit_of_measurement') or '-'):<8} "
            f"{'Summe' if e.get('has_sum') else 'Mittel'}"
            for e in sorted(alle, key=lambda x: x.get("statistic_id") or "")))

        auswahl = alle if alles else [e for e in alle if ist_energie(e)]
        print(f"Naeher untersucht    : {len(auswahl)}\n")

        print(f"{'Statistik':<56}{'Einheit':<8}{'von':<9}{'bis':<9}{'Mon':>4}")
        print("-" * 90)
        for e in sorted(auswahl, key=lambda x: x.get("statistic_id") or ""):
            kennung = e.get("statistic_id")
            b = monatsuebersicht(v, ha, kennung, von_monat, bis)
            einheit = (e.get("display_unit_of_measurement")
                       or e.get("statistics_unit_of_measurement") or "-")
            ergebnis["statistiken"][kennung] = {"einheit": einheit, **b}
            if b.get("monate"):
                print(f"{kennung[:55]:<56}{einheit:<8}{b['von']:<9}{b['bis']:<9}"
                      f"{b['monate']:>4}")
            else:
                print(f"{kennung[:55]:<56}{einheit:<8}{'-':<9}{'-':<9}{0:>4}")

        # Energie-Dashboard
        try:
            prefs = v.befehl("energy/get_prefs")
        except Exception as e:
            print(f"\nEnergie-Dashboard nicht lesbar: {e}")
            prefs = None

        if prefs:
            rollen = rollen_sammeln(prefs)
            print(f"\nIm Energie-Dashboard eingetragen: {len(rollen)}\n")
            print(f"{'Rolle':<30}{'Statistik':<56}{'erster Tag':<12}")
            print("-" * 98)
            roh = {}
            if rollen:
                roh = ha.statistiken(v, list(rollen), von_tag, bis, zeitraum="day")
            tageswerte = {}
            for kennung, r in sorted(rollen.items(), key=lambda x: (x[1], x[0])):
                reihe = roh.get(kennung) or []
                tage_werte = {}
                for eintrag in reihe:
                    dt = ha.zeitstempel(eintrag)
                    if dt is None:
                        continue
                    w = eintrag.get("change")
                    if w is None:
                        w = eintrag.get("sum")
                    tage_werte[f"{dt.astimezone():%Y-%m-%d}"] = (
                        None if w is None else round(float(w), 3))
                tageswerte[kennung] = tage_werte
                mit_wert = sorted(t for t, w in tage_werte.items() if w)
                print(f"{', '.join(r)[:29]:<30}{kennung[:55]:<56}"
                      f"{(mit_wert[0] if mit_wert else '-'):<12}")
            ergebnis["dashboard"] = {"konfiguration": prefs, "rollen": rollen,
                                     "tageswerte": tageswerte}

    speichern(HA_ORDNER, "inventar.json",
              json.dumps({k: v for k, v in ergebnis.items() if k != "dashboard"},
                         indent=1, ensure_ascii=False))
    if ergebnis["dashboard"]:
        speichern(HA_ORDNER, "energie_dashboard.json",
                  json.dumps(ergebnis["dashboard"], indent=1, ensure_ascii=False))
    return ergebnis


# ============================================================================
# Main
# ============================================================================

# ------------------------------------------------------- Plausibilitaet
#
# Das Portal liefert dieselben Reihen in vier Aufloesungen. Sie muessten
# uebereinstimmen - tun sie aber nicht, und die Abweichungen sind kein
# Rundungsrauschen, sondern fehlende Werte. Zwei Beispiele aus der Anlage,
# an der das Projekt entstand:
#
#   Juli 2023 (Wartung)  Monat 270 kWh, Tage 57 kWh, Feinkurve 57 kWh
#   Maerz 2026           Monat 1702 kWh, Tage 1702 kWh, Feinkurve 0 kWh
#
# Die Regel daraus: Je groeber die Aufloesung, desto vollstaendiger. Wer nur
# die Feinkurve nimmt, verliert Energie, ohne dass irgendetwas danach schief
# aussieht. Diese Pruefung sagt, wo und wie viel.

PAARE = [("bilanz", "Energiebilanz"), ("wechselrichter", "Wechselrichter")]

# Ab wann eine Abweichung eine ist: nicht rein relativ, sonst schlagen leere
# Wintermonate aus; nicht rein absolut, sonst verschwinden Prozente im Sommer.
MINDEST_KWH = 3.0
MINDEST_ANTEIL = 0.01


def jahressumme(werte, reihe, jahr, schluessel_jahr):
    return sum(w.get(reihe, 0.0) for k, w in werte.items()
               if schluessel_jahr(k) == jahr)


def auffaellig(fein, grob):
    return grob - fein > max(MINDEST_KWH, MINDEST_ANTEIL * abs(grob))


def plausibilitaet_pruefen():
    bericht = {"quellen": {}, "luecken": []}
    for ordner, titel in PAARE:
        fein = daten.fein_tagessummen(os.path.join(HIER, ordner), ZEITZONE)
        tage = daten.grob_lesen(os.path.join(HIER, f"{ordner}_tage"), "tag")
        monate = daten.grob_lesen(os.path.join(HIER, f"{ordner}_monate"), "monat")
        jahre = daten.grob_lesen(os.path.join(HIER, f"{ordner}_jahre"), "jahr")
        if not (fein or monate):
            print(f"\n{titel}: keine Dateien gefunden.")
            continue

        reihen = sorted({r for w in monate.values() for r in w} or
                        {r for w in fein.values() for r in w})
        alle_jahre = sorted({d.year for d in fein} | {j for j, _ in monate} | set(jahre))

        print(f"\n{titel}   (kWh; Fehlbetrag = fein minus Monatswert)")
        print(f"  {'Reihe':<24}{'Jahr':<6}{'fein':>9}{'Tage':>9}{'Monate':>9}"
              f"{'Jahre':>9}{'Fehlbetrag':>12}{'':>2}%")
        quelle = {}
        for reihe in reihen:
            for jahr in alle_jahre:
                a = jahressumme(fein, reihe, jahr, lambda d: d.year)
                b = jahressumme(tage, reihe, jahr, lambda d: d.year)
                c = jahressumme(monate, reihe, jahr, lambda k: k[0])
                d = jahre.get(jahr, {}).get(reihe, 0.0)
                if not any((a, b, c, d)):
                    continue
                quelle.setdefault(reihe, {})[jahr] = {
                    "fein": round(a, 1), "tage": round(b, 1),
                    "monate": round(c, 1), "jahre": round(d, 1)}
                marke = "  <--" if auffaellig(a, c) else ""
                print(f"  {reihe[:23]:<24}{jahr:<6}{a:>9.0f}{b:>9.0f}{c:>9.0f}"
                      f"{d:>9.0f}{a - c:>12.0f}{(100 * (a - c) / c if c else 0):>6.1f}"
                      f"{marke}")
        bericht["quellen"][ordner] = quelle

        # Wo genau fehlt etwas? Monat fuer Monat, beide Uebergaenge.
        for (jahr, monat), werte in sorted(monate.items()):
            for reihe, monatswert in werte.items():
                tagesumme = sum(w.get(reihe, 0.0) for d, w in tage.items()
                                if (d.year, d.month) == (jahr, monat))
                feinsumme = sum(w.get(reihe, 0.0) for d, w in fein.items()
                                if (d.year, d.month) == (jahr, monat))
                if auffaellig(tagesumme, monatswert):
                    bericht["luecken"].append({
                        "quelle": ordner, "reihe": reihe,
                        "monat": f"{jahr}-{monat:02d}", "ebene": "tag",
                        "vorhanden_kwh": round(tagesumme, 1),
                        "laut_monat_kwh": round(monatswert, 1),
                        "fehlt_kwh": round(monatswert - tagesumme, 1)})
                if auffaellig(feinsumme, max(tagesumme, monatswert)):
                    bericht["luecken"].append({
                        "quelle": ordner, "reihe": reihe,
                        "monat": f"{jahr}-{monat:02d}", "ebene": "fein",
                        "vorhanden_kwh": round(feinsumme, 1),
                        "laut_grober_ebene_kwh": round(max(tagesumme, monatswert), 1),
                        "fehlt_kwh": round(max(tagesumme, monatswert) - feinsumme, 1)})

    if bericht["luecken"]:
        print(f"\n  {len(bericht['luecken'])} Luecken gefunden - die groessten:")
        for e in sorted(bericht["luecken"], key=lambda e: -e["fehlt_kwh"])[:12]:
            print(f"     {e['monat']}  {e['quelle']:<15}{e['reihe'][:22]:<23}"
                  f"Ebene {e['ebene']:<5} fehlen {e['fehlt_kwh']:>8.0f} kWh")
        print("\n  Vollstaendig in plausibilitaet.json. Sie sind kein Fehler des")
        print("  Exports: Das Portal hat die Werte im groben Raster und im feinen")
        print("  nicht. Schritt 3 muss deshalb je Zeitraum die feinste Ebene")
        print("  nehmen, die es gibt - und darf die Luecken nicht als Null lesen.")
    else:
        print("\n  Keine Abweichungen zwischen den Aufloesungen.")
    return bericht


def main():
    p = argparse.ArgumentParser(
        description="Bestand pruefen und die Geraeteaufteilung klaeren")
    p.add_argument("--ha", action="store_true",
                   help="zusaetzlich Home Assistant abfragen")
    p.add_argument("--ha-alles", action="store_true",
                   help="in HA jede Statistik untersuchen, nicht nur Energie")
    p.add_argument("--neu", action="store_true",
                   help="Geraeteanalyse neu erstellen, Bestaetigung verwerfen")
    args = p.parse_args()

    print("=" * 96)
    print(f"Schritt 2 - Analyse  (Version {__version__}, {__stand__})")
    print("Dieses Skript schreibt nichts nach Home Assistant.")
    print("=" * 96)

    print("\n" + "-" * 96)
    print("PORTAL - Geraeteaufteilung")
    print("-" * 96)
    ergebnis = geraete_analysieren(args.neu)
    bestaetigt = False
    if ergebnis:
        analyse, bestaetigt = ergebnis
        geraete_ausgeben(analyse, bestaetigt)
        with open(REGELN, "w", encoding="utf-8") as f:
            json.dump(analyse, f, indent=1, ensure_ascii=False)
        print(f"\nGeschrieben: {REGELN}")

    print("\n" + "-" * 96)
    print("PORTAL - Plausibilitaet ueber alle Aufloesungen")
    print("-" * 96)
    bericht = plausibilitaet_pruefen()
    with open(os.path.join(HIER, "plausibilitaet.json"), "w", encoding="utf-8") as f:
        json.dump(bericht, f, indent=1, ensure_ascii=False)
    print(f"\nGeschrieben: {os.path.join(HIER, 'plausibilitaet.json')}")

    if args.ha or args.ha_alles:
        print("\n" + "-" * 96)
        print("HOME ASSISTANT - vorhandene Statistiken")
        print("-" * 96)
        ha_analysieren(alles=args.ha_alles)
    else:
        print("\n(Home Assistant wurde nicht abgefragt - mit --ha einschalten.)")

    print("\n" + "=" * 96)
    if ergebnis and not bestaetigt:
        print("NAECHSTER SCHRITT: geraeteregeln.json pruefen, die Fragen oben")
        print("beantworten, 'bestaetigt' auf true setzen - dann 3_transform.py.")
    elif ergebnis:
        print("Die Geraeteaufteilung ist bestaetigt. Weiter mit 3_transform.py.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
