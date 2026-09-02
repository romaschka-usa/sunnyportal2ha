# Änderungshistorie

Alle nennenswerten Änderungen an diesem Projekt. Neueste zuerst.

Jede produktive Datei führt zusätzlich ihre eigene Historie im Kopf — dort
steht es genauer und näher am Code. Diese Datei fasst zusammen, was sich für
Anwender ändert.

---

## 1.0.0 — 2026-09-02

**Die Kette ist vollständig.** Bisher lag nur Schritt 1 im Repository; jetzt
liegt der ganze Weg vom Portal bis in die Langzeitstatistik von Home Assistant
darin.

Enthaltene Fassungen:

| Datei | Version |
|---|---|
| `1_export.py` | 2.13.1 |
| `2_analyse.py` | 1.1.0 |
| `3_transform.py` | 2.4.0 |
| `4_import.py` | 1.12.0 |
| `daten.py` | 1.8.0 |
| `ha.py` | 1.0.0 |
| `portal.py` | 1.0.0 |

### Neu veröffentlicht

* **Schritt 2 — `2_analyse.py`.** Beurteilt beide Seiten, ohne etwas zu
  verändern. Auf der Portalseite die Geräteaufteilung und die
  Plausibilitätsprüfung über alle vier Auflösungen; auf der HA-Seite das
  Inventar der vorhandenen Statistiken und was das Energie-Dashboard davon
  verwendet.
* **Schritt 3 — `3_transform.py`.** Macht aus den Portal-CSV stündliche
  Energiereihen. Mit `--leistung` zusätzlich Leistungsreihen in Watt, je
  Stunde Mittelwert, Minimum und Maximum — samt der vorzeichenbehafteten
  Netzleistung.
* **Schritt 4 — `4_import.py`.** Schreibt die Reihen als externe Statistiken
  nach Home Assistant. Probelauf ist die Vorgabe; `--entfernen` nimmt alles
  wieder zurück.
* **Module `daten.py` und `ha.py`.** Das Lesen der Portal-CSV und der
  lesende Zugriff auf Home Assistant, von den Schritten gemeinsam benutzt.

### Was dabei gelernt wurde

* **Der Vergleich vor dem Import.** `--vergleich` stellt Home Assistant und
  Portal Tag für Tag gegenüber und schlägt den Tag vor, ab dem beide
  übereinstimmen. `--bis` schneidet den Import dort ab. So schließen
  Portalhistorie und eigene Sensoren lücken- und überschneidungsfrei
  aneinander an.
* **Einheiten sind nicht einheitlich.** Home Assistant führt Energie je nach
  Gerät in Wh, kWh oder MWh — im selben Dashboard nebeneinander. Stumpf
  addiert ergab die PV-Erzeugung das 660-fache.
* **Der Recorder schreibt im Hintergrund.** `import_statistics` quittiert
  sofort. Wer gleich danach nachliest, sieht abgeschnittene Reihen und hält
  einen gelungenen Import für misslungen. Der Import wartet jetzt, bis Home
  Assistant die Reihen auch zeigt.
* **Große Blöcke reißen die Verbindung ab.** Bei 5000 Werten am Stück ist der
  Recorder mit dem Nachrechnen so lange beschäftigt, dass die
  WebSocket-Verbindung wegfällt. Jetzt 1000er Blöcke mit Verschnaufpause und
  Wiederaufbau bei Abriss.
* **Ein Importprotokoll.** `import/_import-protokoll.json` hält je Lauf fest,
  welche Kennung von welcher bis zu welcher Stunde geschrieben wurde. Ohne das
  lässt sich später nichts gezielt korrigieren.

### Bekannte Einschränkungen

* **Stundenauflösung ist die Obergrenze.** Home Assistant führt zwei
  Statistiktabellen: `statistics` (stündlich, dauerhaft) und
  `statistics_short_term` (fünf Minuten, nach etwa zehn Tagen weg). Die
  Importschnittstelle schreibt ausschließlich in die erste. Am Schnitt ist der
  Unterschied sichtbar — davor Stundenwerte, danach die feine Kurve der
  eigenen Sensoren.
* **Die Leistungskurve im Energie-Dashboard braucht einen Umweg.** Wird der
  Netzanschluss mit „Zwei Sensoren" konfiguriert und sind die Quellen externe
  Statistiken, baut Home Assistant daraus eine Hilfsentität, deren Kennung die
  Doppelpunkte der Quellkennungen enthält — und die kann es nie geben. Siehe
  `4_import.py --ziel` und den Abschnitt im README.
* **Erprobt an genau einer Anlage.** Zwei Wechselrichter, Sunny Home
  Manager 2.0, kein Speicher. Rückmeldungen von anderen Anlagen sind der
  nützlichste Beitrag, den dieses Projekt bekommen kann.

---

## 0.2.0 — 2026-09-02

Vier Auflösungen, Lückennachladung, Laufprotokoll. `1_export.py` 2.13.1.

Das Portal liefert dieselben Reihen in vier Auflösungen, und sie sind **nicht
gleich vollständig**. Ohne Vergleich fällt das nicht auf:

```
März 2026, PV     Monat 1971 kWh    Tage 1971 kWh    Feinkurve    0 kWh
Juli 2023, PV     Monat  270 kWh    Tage   57 kWh    Feinkurve   57 kWh
```

* Sechs neue Quellen für die groben Stufen (`presetting` month/year/total) und
  zwei für die Lückensuche. Letztere laden einzelne **Tage** nach, an denen
  die Monatsabfrage keine Feinkurve hergab — gemessene Werte statt aus
  Tagessummen verteilter.
* Leere Zeiträume sind ein Ergebnis, kein Fehler. Der Duplikatschutz gilt nur
  noch für Dateien mit Werten, und der Wachtposten zählt nur echte Fehler.
* Laufprotokoll in `export-log.txt`: enthält bewusst keine Messwerte, keine
  Anlagenkennung und keine Gerätenamen und darf einem Fehlerbericht beiliegen.
* Das Zeitraster wird immer angesagt (`presetting=day`), auch auf der
  Analyse-Seite. Ohne den Parameter entscheidet die Vorgabe des Servers.
* Der Verbraucherendpunkt antwortet unter Last gelegentlich mit etwas anderem
  als JSON. Im ersten Lauf traf das 255 von 1228 Tagen; jetzt wird wiederholt.

Die README korrigierte einen Fallstrick, der so nicht stimmte: Die
Analyse-Seite liefert nicht ein Viertel der Anlagensumme als Geräteertrag —
sie liefert die Anlagensumme viertelstündlich und die Gerätereihe stündlich,
in derselben Datei, mit leeren Zellen dazwischen. Wer jeden Wert mit einer
Viertelstunde multipliziert, erhält exakt 25 Prozent.

---

## 0.1.0 — 2026-09-01

Erste Veröffentlichung. Nur Schritt 1: `1_export.py` und `portal.py`.

* Anmeldung über SMA ID (Keycloak) ohne Browser, ohne Selenium.
* Energiebilanz, Wechselrichter und Verbraucher als drei Quellen, wahlweise
  einzeln oder mit `alles`.
* Mehrere gleichzeitige Verbindungen; Anzahl aus `zugangsdaten.ini`.
* Der Abbruch mit `Strg+C` beendet den ganzen Lauf und nicht nur die laufende
  Quelle; fertige Zeiträume werden beim nächsten Start übersprungen.
