#!/usr/bin/env python3
"""
portal - Zugriff auf das klassische SMA Sunny Portal
=========================================================

Version        : 1.0.0
Letzte Aenderung: 2026-09-01

Beschreibung
------------
Gemeinsames Modul fuer alle Skripte dieses Projekts. Es wird importiert und
nicht direkt aufgerufen. Drei Aufgaben:

  anmelden()          Anmeldung ueber SMA ID (Keycloak) ohne Browser,
                      liefert eine angemeldete requests.Session
  anlage_ermitteln()  PlantOid sowie erster und letzter verfuegbarer Tag -
                      damit funktionieren die Skripte fuer JEDE Anlage,
                      nichts ist fest verdrahtet
  messwerte()         Rohantwort von GetMeasuredValues fuer einen Zeitraum

Aufruf
------
Nicht direkt aufrufbar. Wird von export_energiebilanz.py und export_verbraucher.py
verwendet:

    from portal import anmelden, anlage_ermitteln, messwerte

Zugangsdaten
------------
Stehen in zugangsdaten.ini neben den Skripten, niemals im Code:

    [sunnyportal]
    benutzer = deine@mailadresse.de
    passwort = deinPasswort

Die Datei wird beim ersten Start als Vorlage angelegt und gehoert nicht ins
Versionsverwaltungssystem - siehe .gitignore.

Aenderungen
-----------
1.0.0  2026-09-01  Erste zusammengefasste Fassung
"""

__version__ = "1.0.0"
__stand__ = "2026-09-01"

import configparser
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    sys.exit("Fehlt: das Paket 'requests'. Bitte 'pip install requests' ausfuehren.")


HIER = os.path.dirname(os.path.abspath(__file__))
CONF_DATEI = os.path.join(HIER, "zugangsdaten.ini")

PORTAL = "https://www.sunnyportal.com"
AUTH_URL = (
    "https://login.sma.energy/auth/realms/SMA/protocol/openid-connect/auth"
    "?response_type=code"
    "&client_id=SunnyPortalClassic"
    "&client_secret=baa6d5fe-f905-4fb2-bc8e-8f218acc2835"
    "&redirect_uri=https%3a%2f%2fwww.sunnyportal.com%2fTemplates%2fStart.aspx"
    "&ui_locales=de"
)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# Aus sma-types im Portal-Javascript, nicht geraten:
INTERVALLE = {
    "5min": 0,
    "10min": 1,
    "15min": 2,
    "hour": 3,
    "day": 4,
    "month": 5,
    "year": 6,
}

MESSWERTE_URL = f"{PORTAL}/Homan/ConsumerBalance/GetMeasuredValues"


class PortalFehler(RuntimeError):
    pass


def zugangsdaten():
    if not os.path.exists(CONF_DATEI):
        with open(CONF_DATEI, "w", encoding="utf-8") as f:
            f.write("[sunnyportal]\nbenutzer = deine@mailadresse.de\npasswort = deinPasswort\n")
        raise PortalFehler(
            f"Vorlage angelegt: {CONF_DATEI}\n"
            "Bitte Benutzer und Passwort eintragen und erneut starten."
        )
    cp = configparser.ConfigParser()
    cp.read(CONF_DATEI, encoding="utf-8")
    b = cp.get("sunnyportal", "benutzer", fallback="").strip()
    p = cp.get("sunnyportal", "passwort", fallback="").strip()
    if not b or not p or "@mailadresse" in b:
        raise PortalFehler(f"Bitte echte Zugangsdaten in {CONF_DATEI} eintragen.")
    return b, p


def ist_anmeldeseite(text):
    """
    Erkennt beide Anmeldeseiten: die des Portals (ASP.NET) und die von SMA ID
    (Keycloak). Absichtlich enge Marker - ein zu weiter Marker meldet sonst
    Fehlalarm auf einer voellig gueltigen Seite.
    """
    marker = (
        "SmaIdLoginButton",            # Anmeldeknopf des Portals
        "Start.aspx?ReturnUrl",        # Umleitung des Portals auf den Login
        "login-actions/authenticate",  # Formularziel von SMA ID
        "<title>Anmelden bei SMA",     # Titel der SMA-ID-Seite
    )
    return any(m in text for m in marker)


def anmelden(leise=False):
    """Meldet sich per Keycloak an und liefert eine Session mit gueltiger Portal-Sitzung."""
    def sag(*a):
        if not leise:
            print(*a)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"})

    r = s.get(AUTH_URL, timeout=30)
    treffer = re.search(r'action="([^"]*login-actions/authenticate[^"]*)"', r.text)
    if not treffer:
        raise PortalFehler("Anmeldeformular nicht gefunden - hat SMA die Loginseite geaendert?")
    action = urljoin(r.url, treffer.group(1).replace("&amp;", "&"))

    benutzer, passwort = zugangsdaten()
    r2 = s.post(
        action,
        data={"username": benutzer, "password": passwort, "credentialId": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": r.url},
        allow_redirects=True,
        timeout=30,
    )
    # Nur den Hostnamen pruefen - die Zieladresse enthaelt iss=...login.sma.energy...
    if "login.sma.energy" in urlparse(r2.url).netloc.lower():
        fehler = re.findall(r'kc-feedback-text[^>]*>([^<]{3,200})<', r2.text)
        hinweis = f" Meldung der Seite: {fehler[0].strip()}" if fehler else ""
        raise PortalFehler("Anmeldung wurde nicht akzeptiert." + hinweis)

    sag("   Anmeldung erfolgreich.")
    return s


def _fehlerseite_ablegen(text, name):
    """Legt eine unerwartete Antwort zur Analyse ab und liefert den Pfad zurueck."""
    ordner = os.path.join(HIER, "diagnose")
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, name)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(text)
    return pfad


def anlage_ermitteln(s):
    """Liest PlantOid, MinDate und MaxDate aus dem Modell der Verbraucherbilanz-Seite."""
    # Erst die Startseite anfahren. Im erfolgreichen Diagnoselauf lief es genau so,
    # und die ASP.NET-Sitzung setzt sich dabei zuverlaessig.
    s.get(f"{PORTAL}/Templates/Start.aspx", timeout=45)

    r = s.get(f"{PORTAL}/Homan/ConsumerBalance", timeout=45)
    if ist_anmeldeseite(r.text):
        # Einmal neu anfahren - manchmal greift die Sitzung erst im zweiten Anlauf.
        r = s.get(f"{PORTAL}/Homan/ConsumerBalance", timeout=45)

    if ist_anmeldeseite(r.text):
        titel = re.search(r"<title>([^<]{0,120})</title>", r.text)
        pfad = _fehlerseite_ablegen(r.text, "11_consumerbalance_fehler.html")
        raise PortalFehler(
            "Verbraucherbilanz liefert die Anmeldeseite.\n"
            f"        Endadresse: {r.url}\n"
            f"        Status    : {r.status_code}, {len(r.text)} Zeichen\n"
            f"        Titel     : {titel.group(1).strip() if titel else '(keiner)'}\n"
            f"        Abgelegt  : {pfad}"
        )

    oid = re.search(r'"PlantOid"\s*:\s*"([0-9a-fA-F-]{36})"', r.text)
    if not oid:
        pfad = _fehlerseite_ablegen(r.text, "11_consumerbalance_ohne_oid.html")
        raise PortalFehler(f"PlantOid nicht gefunden. Seite abgelegt: {pfad}")

    def datum(feld):
        m = re.search(
            r'"' + feld + r'"\s*:\s*\{[^}]*?"DateTime"\s*:\s*"(\d{4}-\d{2}-\d{2})', r.text
        )
        return m.group(1) if m else None

    return {"plant_oid": oid.group(1), "min_date": datum("MinDate"), "max_date": datum("MaxDate")}


class ZeitUeberschritten(PortalFehler):
    """Der Server hat innerhalb des Zeitlimits nicht geantwortet."""


def messwerte(s, plant_oid, start, ende, intervall="15min", timeout=180, versuche=2):
    """
    Ruft GetMeasuredValues auf.

    start/ende als 'YYYY-MM-DD'. ende ist exklusiv, so macht es das Portal auch:
    fuer einen einzelnen Tag ist ende = start + 1 Tag.

    Rueckgabe: (daten, rohtext, sekunden). daten ist None, wenn keine JSON-Antwort kam.
    Bei Netzproblemen wird ZeitUeberschritten bzw. PortalFehler geworfen - nie eine
    rohe requests-Ausnahme, damit der Aufrufer eine einzige Fehlerart behandeln kann.
    """
    if intervall not in INTERVALLE:
        raise PortalFehler(f"Unbekanntes Intervall '{intervall}'. Moeglich: {list(INTERVALLE)}")

    letzter_fehler = None
    for versuch in range(1, versuche + 1):
        begonnen = time.monotonic()
        try:
            r = s.get(
                MESSWERTE_URL,
                params={
                    "IntervalId": INTERVALLE[intervall],
                    "PlantOid": plant_oid,
                    "StartTime": start,
                    "EndTime": ende,
                },
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{PORTAL}/Homan/ConsumerBalance",
                },
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            letzter_fehler = ZeitUeberschritten(
                f"Keine Antwort innerhalb von {timeout} s (Versuch {versuch}/{versuche})."
            )
            continue
        except requests.exceptions.RequestException as e:
            letzter_fehler = PortalFehler(f"Netzwerkfehler: {type(e).__name__}: {e}")
            continue

        dauer = time.monotonic() - begonnen
        if ist_anmeldeseite(r.text):
            raise PortalFehler("Antwort ist die Anmeldeseite - die Sitzung ist abgelaufen.")
        try:
            return r.json(), r.text, dauer
        except ValueError:
            return None, r.text, dauer

    raise letzter_fehler
