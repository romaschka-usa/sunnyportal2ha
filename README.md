# sunnyportal2ha

**Die PV-Historie aus dem SMA Sunny Portal holen, aufbereiten und nach Home Assistant übernehmen.**

Wer eine Photovoltaikanlage von SMA betreibt, hat jahrelange Messdaten — aber sie
liegen in der Cloud des Herstellers und nicht im eigenen Haus. Wer auf Home
Assistant umsteigt, fängt dort bei null an: Das Energie-Dashboard kennt nur, was
seit der Installation aufgezeichnet wurde. Dieses Projekt schließt die Lücke.

Es holt den kompletten Bestand seit Inbetriebnahme in voller
Viertelstundenauflösung, rechnet ihn in ein importierbares Format um und spielt
ihn in die Langzeitstatistik von Home Assistant ein.

---

## Die drei Stufen

```
   ┌───────────────┐      ┌──────────────────┐      ┌────────────────┐
   │  1  Export    │ ───▶ │ 2 Transformation │ ───▶ │  3  Import     │
   │               │      │                  │      │                │
   │ Sunny Portal  │      │ Einheiten        │      │ HA aufräumen   │
   │ → Rohdateien  │      │ Zeitstempel      │      │ → Statistik    │
   │               │      │ Lücken markieren │      │                │
   └───────────────┘      └──────────────────┘      └────────────────┘
        fertig                  in Arbeit               in Arbeit
```

### Stufe 1 — Export

Zwei Skripte holen zwei verschiedene Datenarten:

| Skript | Was es liefert | Zuschnitt |
|---|---|---|
| `export_energiebilanz.py` | PV-Erzeugung, Gesamtverbrauch, Direktverbrauch, Netzbezug, **Netzeinspeisung**, Batterie | ein Monat je Abfrage |
| `export_verbraucher.py` | die Kurven **je Gerät** — Wärmepumpe, Wallbox, Heizstab und so weiter | ein Tag je Abfrage |

Für die Anlagensummen ist die Energiebilanz der bessere Weg: Sie holt einen
ganzen Monat in einer Anfrage und kennt als einzige Quelle die Netzeinspeisung.
Dreieinhalb Jahre sind damit in gut einer Viertelstunde exportiert.

### Stufe 2 — Transformation *(noch nicht gebaut)*

Aus den Rohdateien wird ein sauberer Datensatz: Einheiten vereinheitlichen,
Zeitstempel setzen, Lücken als *fehlend* markieren statt als Null.

### Stufe 3 — Import *(noch nicht gebaut)*

Vorhandene, möglicherweise unvollständige Statistiken in Home Assistant
bereinigen und die Historie einspielen.

---

## Schnellstart

```bash
pip install requests
python export_energiebilanz.py
```

Beim ersten Start wird `zugangsdaten.ini` als Vorlage angelegt. Dort trägst du
die Zugangsdaten deines Sunny-Portal-Kontos ein:

```ini
[sunnyportal]
benutzer = deine@mailadresse.de
passwort = deinPasswort
```

Diese Datei steht in `.gitignore` und darf niemals ins Repository. Danach genügt
ein erneuter Aufruf; das Skript arbeitet sich Monat für Monat durch und legt die
Ergebnisse in `bilanz/` ab.

Ein Abbruch mit `Strg+C` ist jederzeit gefahrlos — fertige Zeiträume werden beim
nächsten Start übersprungen.

**Voraussetzungen:** Python 3.9 oder neuer, ein Sunny-Portal-Konto, und eine
Anlage mit Sunny Home Manager (nur dann gibt es die Energiebilanz-Seite).

---

## Wie der Zugriff funktioniert

Es gibt keine offene API. Der Weg führt über dieselben Aufrufe, die auch die
Weboberfläche benutzt — nur ohne Browser.

**Anmeldung.** Das Portal meldet über SMA ID an, einen Keycloak-Server. Das
Skript holt die Anmeldeseite, sendet Benutzername und Passwort an das
Formularziel und folgt der Weiterleitung zurück ins Portal. Kein Selenium, kein
Chromedriver.

**Energiebilanz.** Ihre Diagramme werden nachgeladen. Der Export macht dasselbe
in zwei Schritten:

```
1. GET /PortalCharts/Core/PortalChartsAPI.aspx?id=mainChart&xf=<von>&xt=<bis>
      setzt den Zeitraum in der Sitzung; die Antwort ist ein Bild

2. GET /Templates/DownloadDiagram.aspx?down=homanEnergyRedesign&chartId=mainChart
      liefert die Daten des zuletzt gesetzten Diagramms als CSV
```

`xf` und `xt` sind Unix-Zeiten in Sekunden.

**Verbraucherbilanz.** Hier gibt es einen JSON-Endpunkt:

```
GET /Homan/ConsumerBalance/GetMeasuredValues
    ?IntervalId=<n>&PlantOid=<guid>&StartTime=JJJJ-MM-TT&EndTime=JJJJ-MM-TT
```

mit `IntervalId` 0=5min, 1=10min, 2=15min, 3=Stunde, 4=Tag, 5=Monat, 6=Jahr.
`EndTime` ist ausschließend. Mehrtägige Zeiträume nimmt der Endpunkt nur bei
Tageswerten an.

Anlagenkennung und Betriebszeitraum liest das Skript beim Start aus dem Portal.
Es ist an keine bestimmte Anlage gebunden.

---

## Fallstricke, die Zeit gekostet haben

Diese Punkte stehen hier, weil sie stille Fehler erzeugen — Läufe, die
erfolgreich aussehen und falsche Daten liefern.

**Der Download gibt immer das zuletzt angezeigte Diagramm aus.** Schlägt Schritt
1 fehl, bleibt das vorherige stehen und Schritt 2 liefert den Vormonat ein
zweites Mal, ohne Fehlermeldung. Das Skript prüft deshalb jede Datei gegen die
Prüfsummen aller anderen Monate und die Tageszahl gegen den Kalender.

**Fünf-Minuten-Auflösung liefert nur die Verbraucher.** Die anlagenweiten Reihen
kommen dann als leere Listen. Wer eine Antwort schon deshalb als gültig ansieht,
weil irgendetwas darin steht, exportiert jahrelang Hüllen.

**Die Einheit wechselt zwischen `[W]` und `[kW]`,** abhängig davon, wie das
Portal die Achse skaliert. Sie steht in der Kopfzeile und muss dort gelesen
werden.

**Die CSV enthält kein Datum, nur die Uhrzeit** — und zwar das *Ende* des
Intervalls. Ein Tag läuft von 00:15 bis 00:00. Über die Zeitumstellung hinweg
darf man nicht stur durch 96 teilen.

**Es gibt echte Lücken.** Zeiträume ohne Werte sind nicht immer
Übertragungsfehler; das Portal hat sie manchmal wirklich nicht. Solche Tage
werden benannt und müssen beim Import als *fehlend* gelten, nicht als Null —
sonst verfälschen sie jede Bilanz.

---

## Aufbau des Projekts

```
portal.py                  gemeinsames Modul: Anmeldung, Anlagendaten, Abfragen
export_energiebilanz.py    Stufe 1 — Anlagensummen, monatsweise
export_verbraucher.py      Stufe 1 — Verbraucher je Gerät, tageweise
analyse/                   Hilfsskripte aus der Entwicklung, nicht im Repository
```

Die Skripte in `analyse/` haben die Schnittstellen erkundet — Endpunkte gesucht,
Auflösungen vermessen, Seiten durchprobiert. Sie sind für den Betrieb nicht
nötig, aber lehrreich, wenn SMA etwas ändert und der Weg neu gefunden werden
muss.

Exportierte Daten liegen in `bilanz/` und `rohdaten/` und bleiben ebenfalls
außerhalb des Repositories.

---

## Mitmachen

Beiträge sind willkommen — **am liebsten als Pull Request.**

Besonders wertvoll sind Rückmeldungen von *anderen* Anlagen. Entwickelt wurde
das Projekt an genau einer: zwei Wechselrichtern, Sunny Home Manager 2.0, ohne
Batteriespeicher. Ob es mit Speicher, mit nur einem Wechselrichter, mit einer
Anlage im ennexOS-Portal oder mit einem Konto voller mehrerer Anlagen ebenso
läuft, weiß niemand. Wenn du es ausprobierst, sag Bescheid — auch und gerade
dann, wenn es nicht funktioniert hat.

Ebenso hilfreich: eine Meldung, sobald SMA etwas ändert und der Export bricht.
Die Skripte in `analyse/` sind genau dafür da, den Weg wiederzufinden.

### Bevor du einen Pull Request stellst

Ein paar Dinge, die Ärger ersparen:

* **Keine Zugangsdaten und keine Messdaten** im Commit. `zugangsdaten.ini`,
  `bilanz/` und `rohdaten/` stehen in der `.gitignore` — bitte prüfe mit
  `git status`, bevor du committest.
* **Den Kopf des Skripts pflegen.** Jede produktive Datei trägt Version, Datum
  der letzten Änderung, Beschreibung und Aufruf. Wenn du etwas am Verhalten
  änderst, gehört eine Zeile in den Änderungsblock und die Version eine Stufe
  hoch.
* **Nichts fest verdrahten.** Anlagenkennung und Zeitraum werden zur Laufzeit
  aus dem Portal gelesen. Wer eigene Werte einträgt, macht das Projekt für
  alle anderen unbrauchbar.
* **Stille Fehler sind der Feind.** Wenn du eine neue Abfrage einbaust, baue
  auch die Prüfung dazu: Ist die Antwort wirklich das, was sie sein soll?
  Der Abschnitt oben erklärt, warum.
* Ein Issue vorab ist nie verkehrt, besonders bei größeren Änderungen — dann
  arbeitet niemand doppelt.

Fehlerberichte gern mit der Ausgabe des Laufs und, falls vorhanden, dem
zugehörigen Eintrag aus `bilanz/_protokoll.json`. **Bitte ohne echte Messwerte
und ohne Anlagenkennung.**

---

## Hinweise

Dieses Projekt nutzt **nicht dokumentierte Schnittstellen** der Weboberfläche.
Sie können sich jederzeit ändern; dann bricht der Export. Ob automatisierte
Abrufe von den Nutzungsbedingungen des Portals gedeckt sind, wurde nicht
geprüft — jeder nutzt das auf eigene Verantwortung und ausschließlich für die
eigenen Anlagendaten.

Die Skripte lesen ausschließlich. Sie verändern nichts im Portal und in keiner
Anlagenkonfiguration.

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

---

*Dieses Projekt steht in keiner Verbindung zur SMA Solar Technology AG. SMA,
Sunny Portal und Sunny Home Manager sind eingetragene Marken der SMA Solar
Technology AG und werden hier ausschließlich zur Beschreibung der
Kompatibilität genannt. Home Assistant ist eine Marke der Open Home Foundation.*
