import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import requests
from rapidfuzz import fuzz, process


PROJECT_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_DIR / "data" / "reference" / "cities_ru.json"
CITIES_URL = "https://api.travelpayouts.com/data/ru/cities.json"

ALIASES = {
    "питер": "LED",
    "спб": "LED",
    "мск": "MOW",
}


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("ё", "е")
    text = re.sub(r"[-‐‑–—]", " ", text)
    return " ".join(text.split())


def validate_rows(rows):
    if not isinstance(rows, list):
        raise ValueError("Справочник городов имеет неверный формат")

    valid = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("code"), str)
        and isinstance(row.get("name"), str)
        and row["name"].strip()
    ]

    if not valid:
        raise ValueError("Справочник городов пуст")

    return valid


@lru_cache(maxsize=1)
def load_directory():
    rows = None

    if CACHE_FILE.exists():
        try:
            rows = validate_rows(
                json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError):
            rows = None

    if rows is None:
        response = requests.get(CITIES_URL, timeout=30)
        response.raise_for_status()
        rows = validate_rows(response.json())

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = CACHE_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(rows, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_file.replace(CACHE_FILE)

    by_code = {}
    name_index = {}

    for row in rows:
        code = row["code"].upper()
        city = {
            "code": code,
            "name": row["name"],
            "country_code": row.get("country_code") or "",
        }
        by_code[code] = city

        names = [row["name"]]
        translations = row.get("name_translations") or {}

        if isinstance(translations, dict):
            names.extend(
                value
                for value in translations.values()
                if isinstance(value, str)
            )

        for name in names:
            key = normalize(name)
            if key:
                name_index.setdefault(key, set()).add(code)

    for alias, code in ALIASES.items():
        if code in by_code:
            name_index.setdefault(normalize(alias), set()).add(code)

    return by_code, name_index


def city_label(city):
    country = city["country_code"]
    suffix = f", {country}" if country else ""
    return f"{city['name']}{suffix} — {city['code']}"


def find_cities(text):
    by_code, name_index = load_directory()
    query = normalize(text)

    if not query:
        return [], False

    code = text.strip().upper()

    if code in by_code:
        return [by_code[code]], True

    exact_codes = name_index.get(query)

    if exact_codes:
        matches = [
            by_code[item]
            for item in sorted(exact_codes)
        ]
        return matches[:5], len(matches) == 1

    # Не исправляем неизвестные трёхбуквенные коды автоматически.
    if re.fullmatch(r"[A-Z]{3}", code):
        return [], False

    if len(query) < 3:
        return [], False

    candidates = process.extract(
        query,
        list(name_index),
        scorer=fuzz.WRatio,
        score_cutoff=72,
        limit=20,
    )

    matches = []
    seen = set()

    for name, score, index in candidates:
        for candidate_code in sorted(name_index[name]):
            if candidate_code in seen:
                continue

            seen.add(candidate_code)
            matches.append(by_code[candidate_code])

            if len(matches) == 5:
                return matches, False

    return matches, False


if __name__ == "__main__":
    cities, names = load_directory()
    print(f"Справочник готов. Городов: {len(cities)}")

    for query in ("Москва", "Масква", "Санкт Петербруг", "NOW"):
        matches, exact = find_cities(query)
        print(f"\n{query!r}: точное совпадение — {exact}")

        for city in matches:
            print(" ", city_label(city))