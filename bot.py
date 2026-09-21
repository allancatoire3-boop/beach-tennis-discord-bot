#!/usr/bin/env python3
"""Surveille les nouveaux tournois de Beach Tennis sur Ten'Up et les annonce sur Discord."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

TENUP_API = "https://tenup.fft.fr/back/public/v1/tournois"
TENUP_SEARCH = "https://tenup.fft.fr/recherche/tournois"
STATE_FILE = Path("seen_tournaments.json")
CURRENT_FILE = Path("current_tournaments.json")

MONTPELLIER_LAT = 43.610476
MONTPELLIER_LNG = 3.87048
RADIUS_KM = 199
SEARCH_DAYS = 93
PAGE_SIZE = 10
TIMEOUT_SECONDS = 30


class BotError(RuntimeError):
    pass


def request_payload(offset: int) -> dict[str, Any]:
    today = date.today()
    return {
        "dateDebut": today.isoformat(),
        "dateFin": (today + timedelta(days=SEARCH_DAYS)).isoformat(),
        "distance": RADIUS_KM,
        "from": offset,
        "lat": MONTPELLIER_LAT,
        "lng": MONTPELLIER_LNG,
        "pratique": "BEACH",
        "size": PAGE_SIZE,
        "sort": "DATE_DEBUT",
    }


def fetch_tournaments() -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://tenup.fft.fr",
        "Referer": TENUP_SEARCH,
        "User-Agent": "BeachTennisMontpellierNotifier/1.0",
    })

    all_cards: list[dict[str, Any]] = []
    offset = 0

    while True:
        response = session.post(
            TENUP_API,
            json=request_payload(offset),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        cards = data.get("cards", [])

        if not isinstance(cards, list):
            raise BotError("Réponse Ten'Up inattendue : le champ 'cards' est absent.")

        all_cards.extend(card for card in cards if isinstance(card, dict))

        if len(cards) < PAGE_SIZE:
            break

        offset += len(cards)
        if offset > 5000:
            raise BotError("Pagination Ten'Up anormalement longue.")

    # Déduplication défensive.
    unique: dict[str, dict[str, Any]] = {}
    for card in all_cards:
        unique[tournament_id(card)] = card
    return list(unique.values())


def tournament_id(card: dict[str, Any]) -> str:
    homologation = card.get("idHomologation")
    if homologation:
        return str(homologation)

    # Solution de secours si Ten'Up change exceptionnellement ce champ.
    return "|".join(str(card.get(key, "")) for key in (
        "libelleTournoi", "dateDebut", "dateFin", "ville", "club"
    ))


def load_seen() -> set[str]:
    if not STATE_FILE.exists():
        return set()

    try:
        content = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BotError(f"Impossible de lire {STATE_FILE}: {exc}") from exc

    if isinstance(content, list):
        return {str(item) for item in content}
    if isinstance(content, dict):
        return {str(item) for item in content.get("ids", [])}
    raise BotError(f"Format invalide dans {STATE_FILE}.")


def save_seen(ids: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_current_tournaments(tournaments: list[dict[str, Any]]) -> None:
    ordered = sorted(tournaments, key=lambda card: str(card.get("dateDebut", "")))
    CURRENT_FILE.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def first_text(value: Any, default: str = "Non précisé") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, dict):
        for key in ("libelle", "nom", "name", "ville"):
            if value.get(key):
                return str(value[key])
        return default
    if isinstance(value, list):
        texts = [first_text(item, "") for item in value]
        return ", ".join(text for text in texts if text) or default
    return str(value)


def french_date(raw: Any) -> str:
    if not raw:
        return "Date non précisée"
    try:
        parsed = date.fromisoformat(str(raw)[:10])
        months = (
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        )
        return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
    except ValueError:
        return str(raw)


def distance_km(card: dict[str, Any]) -> str:
    raw = card.get("distance")
    try:
        value = float(raw)
        # L'API renvoie actuellement la distance en mètres.
        km = value / 1000 if value > 1000 else value
        return f"{round(km)} km de Montpellier"
    except (TypeError, ValueError):
        return "Distance non précisée"


def nature_label(card: dict[str, Any]) -> str:
    value = card.get("naturesEpreuves")
    if not value:
        return "Épreuve non précisée"
    return first_text(value)


def tournament_embed(card: dict[str, Any]) -> dict[str, Any]:
    title = first_text(card.get("libelleTournoi"), "Tournoi de Beach Tennis")
    city = first_text(card.get("ville"))
    club = first_text(card.get("club"), "")
    start = french_date(card.get("dateDebut"))
    end = french_date(card.get("dateFin"))

    date_text = start if start == end else f"Du {start} au {end}"
    place = city + (f" — {club}" if club and club.upper() != city.upper() else "")

    return {
        "title": title[:256],
        "url": TENUP_SEARCH,
        "color": 0xF39C12,
        "fields": [
            {"name": "📅 Date", "value": date_text[:1024], "inline": True},
            {"name": "📍 Lieu", "value": place[:1024], "inline": True},
            {"name": "📏 Distance", "value": distance_km(card), "inline": True},
            {"name": "👥 Épreuve", "value": nature_label(card)[:1024], "inline": False},
        ],
        "footer": {"text": f"Ten'Up • {tournament_id(card)}"},
    }


def send_to_discord(webhook_url: str, card: dict[str, Any]) -> None:
    payload = {
        "username": "Tournois Beach Tennis",
        "content": "🆕 **Nouveau tournoi de Beach Tennis dans un rayon de 200 km !**",
        "embeds": [tournament_embed(card)],
        "allowed_mentions": {"parse": []},
    }

    response = requests.post(webhook_url, json=payload, timeout=TIMEOUT_SECONDS)
    if response.status_code == 429:
        retry_after = float(response.json().get("retry_after", 1))
        time.sleep(min(retry_after, 30))
        response = requests.post(webhook_url, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()


def main() -> int:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise BotError(
            "Le secret DISCORD_WEBHOOK_URL est absent. "
            "Ajoute-le dans Settings > Secrets and variables > Actions."
        )

    tournaments = fetch_tournaments()
    save_current_tournaments(tournaments)
    current_ids = {tournament_id(card) for card in tournaments}
    seen = load_seen()

    # Le dépôt contient au départ une liste vide. La toute première exécution
    # mémorise l'existant sans envoyer une rafale d'anciennes annonces.
    first_run = len(seen) == 0 and os.getenv("INITIALIZED", "") != "true"
    if first_run:
        save_seen(current_ids)
        print(f"Initialisation : {len(current_ids)} tournoi(s) mémorisé(s), aucune notification.")
        return 0

    new_cards = [card for card in tournaments if tournament_id(card) not in seen]
    new_cards.sort(key=lambda card: str(card.get("dateDebut", "")))

    sent_ids: set[str] = set()
    errors: list[str] = []
    for card in new_cards:
        try:
            send_to_discord(webhook_url, card)
            sent_ids.add(tournament_id(card))
            time.sleep(1)
        except requests.RequestException as exc:
            errors.append(f"{tournament_id(card)}: {exc}")

    # On garde l'historique et on ajoute uniquement les notifications réussies.
    save_seen(seen | sent_ids)
    print(
        f"{len(tournaments)} tournoi(s) trouvé(s), "
        f"{len(new_cards)} nouveau(x), {len(sent_ids)} notification(s) envoyée(s)."
    )

    if errors:
        raise BotError("Échec de certaines notifications : " + "; ".join(errors))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.RequestException as exc:
        print(f"Erreur réseau : {exc}", file=sys.stderr)
        sys.exit(1)
    except BotError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
