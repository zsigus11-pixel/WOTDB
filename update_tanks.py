import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
import requests

# ============================================================
# WOTDB - WORLD OF TANKS DATABASE UPDATER
# ============================================================
#
# FONTOS:
# Az Application ID-t nem tároljuk nyilvánosan ebben a fájlban.
# Állítsd be Windowsban WOT_APPLICATION_ID néven, vagy írd be
# ide a saját ID-dat a PASTE... helyére.
#
# Példa PowerShell:
#   $env:WOT_APPLICATION_ID="SAJAT_APPLICATION_ID"
#
# ============================================================

APPLICATION_ID = os.environ.get(
    "WOT_APPLICATION_ID",
    "d7244866d929b2fe3df6b976ccb68ff8"
)

API_URL = "https://api.worldoftanks.eu/wot/encyclopedia/vehicles/"
OUTPUT_FILE = "tanks.json"
IMAGE_DIR = Path("images")

# A Wargaming API által támogatott nyelvek közül használunk.
# Magyar (hu) ezen az API végponton nem támogatott.
API_LANGUAGES = ["en", "de", "fr", "pl", "cs", "ru"]

REQUEST_TIMEOUT = 60
IMAGE_TIMEOUT = 30
IMAGE_DELAY = 0.03

session = requests.Session()
session.headers.update({
    "User-Agent": "WOTDB/1.0"
})


# ============================================================
# SEGÉDFÜGGVÉNYEK
# ============================================================

def number(value, default=0):
    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        return value

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def clean_number(value):
    value = number(value)

    try:
        if float(value).is_integer():
            return int(value)
    except (ValueError, TypeError):
        pass

    return round(value, 2)


def first_number(*values, default=0):
    for value in values:
        if value is None:
            continue

        result = number(value, None)

        if result is not None:
            return result

    return default


def middle_value(value, default=0):
    """
    A Wargaming API az ammo damage/penetration értékeket
    jellemzően [minimum, átlag, maximum] formában adja.
    A középső értéket használjuk.
    """
    if isinstance(value, (list, tuple)):
        if len(value) >= 3:
            return number(value[1], default)

        if len(value) == 2:
            return number(value[0], default)

        if len(value) == 1:
            return number(value[0], default)

        return default

    return number(value, default)


def safe_text(value):
    if value is None:
        return ""

    return str(value).strip()


# ============================================================
# API LEKÉRÉS
# ============================================================

def download_language(language):
    print(f"  API lekérés: {language}")

    params = {
        "application_id": APPLICATION_ID,
        "language": language
    }

    try:
        response = session.get(
            API_URL,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  HIBA ({language}): {exc}")
        return None

    try:
        result = response.json()
    except ValueError:
        print(f"  HIBA ({language}): az API nem JSON választ adott.")
        print(response.text[:1000])
        return None

    if result.get("status") != "ok":
        print(f"  Wargaming API hiba ({language}):")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:4000])
        return None

    data = result.get("data") or {}

    print(f"  OK: {len(data)} tank")

    return data


def download_all_languages():
    if not APPLICATION_ID or APPLICATION_ID == "PASTE_YOUR_APPLICATION_ID_HERE":
        print()
        print("=" * 60)
        print(" HIÁNYZÓ APPLICATION ID")
        print("=" * 60)
        print()
        print("Állítsd be a WOT_APPLICATION_ID környezeti változót.")
        print("PowerShell példa:")
        print('  $env:WOT_APPLICATION_ID="SAJAT_APPLICATION_ID"')
        print()
        return None

    all_data = {}

    for language in API_LANGUAGES:
        data = download_language(language)

        if data is None:
            print(f"  A(z) {language} nyelv kihagyva.")
        else:
            all_data[language] = data

        time.sleep(0.2)

    if "en" not in all_data:
        print()
        print("Az angol API-válasz nélkül nem készíthető adatbázis.")
        return None

    return all_data


# ============================================================
# KÉPEK
# ============================================================

def extract_image_url(tank):
    """
    Elsősorban a játékbeli/full preview képet keresi.
    Ha az API nem ad ilyet, biztonsági tartalékként a contour képet
    használja.

    A különböző API-változatok miatt több lehetséges kulcsot kezelünk.
    """

    images = tank.get("images") or {}

    if isinstance(images, dict):
        # Elsőként a teljes tankos preview / nagy kép.
        for key in (
            "preview",
            "big_icon",
            "large_icon",
            "icon",
            "contour_icon",
            "contour"
        ):
            value = images.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

    # Egyes válaszokban közvetlenül a tank objektumban lehet kép.
    for key in (
        "preview",
        "image",
        "image_url",
        "icon"
    ):
        value = tank.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # Végső tartalék: a Wargaming statikus contour kép.
    tag = safe_text(tank.get("tag"))

    if tag:
        return (
            "https://api.worldoftanks.eu/static/2.77.0/"
            "wot/encyclopedia/vehicle/contour/"
            f"{tag}.png"
        )

    return ""


def image_extension(url, content_type=""):
    path = urlparse(url).path.lower()

    for extension in (".png", ".jpg", ".jpeg", ".webp"):
        if path.endswith(extension):
            return extension

    content_type = (content_type or "").lower()

    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"

    if "webp" in content_type:
        return ".webp"

    return ".png"


def download_image(url, tank_id):
    if not url:
        return ""

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Az automatikus frissítésnél nem töltjük le újra a már meglévő
    # tankképeket. Új tankhoz (vagy hiányzó képhez) továbbra is letölti.
    for extension in (".png", ".jpg", ".jpeg", ".webp"):
        existing_path = IMAGE_DIR / f"{tank_id}{extension}"

        if existing_path.is_file() and existing_path.stat().st_size >= 100:
            return existing_path.as_posix()

    try:
        request = session.get(
            url,
            timeout=IMAGE_TIMEOUT
        )
        request.raise_for_status()

        content = request.content

        if not content or len(content) < 100:
            return ""

        extension = image_extension(
            url,
            request.headers.get("Content-Type", "")
        )

        output_path = IMAGE_DIR / f"{tank_id}{extension}"
        output_path.write_bytes(content)

        return output_path.as_posix()

    except requests.RequestException as exc:
        print(f"    Kép hiba {tank_id}: {exc}")
        return ""

    except OSError as exc:
        print(f"    Fájl hiba {tank_id}: {exc}")
        return ""


def build_image_map(english_data):
    print()
    print("=" * 60)
    print(" TANKKÉPEK LETÖLTÉSE")
    print("=" * 60)
    print()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    image_map = {}
    items = list(english_data.items())

    success = 0
    failed = 0

    for index, (tank_id, tank) in enumerate(items, start=1):
        url = extract_image_url(tank)

        local_path = download_image(url, tank_id)

        if local_path:
            image_map[str(tank_id)] = local_path
            success += 1
        else:
            image_map[str(tank_id)] = ""
            failed += 1

        if index % 25 == 0 or index == len(items):
            print(
                f"  Képek: {index}/{len(items)} "
                f"(sikeres: {success}, hibás: {failed})"
            )

        time.sleep(IMAGE_DELAY)

    print()
    print(f"  Letöltött képek: {success}")
    print(f"  Sikertelen képek: {failed}")

    return image_map


# ============================================================
# AMMO
# ============================================================

def extract_ammo(ammo):
    damage = 0
    penetration = 0
    shell_type = ""
    shell_velocity = 0

    if not isinstance(ammo, list):
        return {
            "damage": 0,
            "penetration": 0,
            "shellType": "",
            "shellVelocity": 0
        }

    preferred_types = [
        "ARMOR_PIERCING",
        "ARMOR_PIERCING_CR",
        "HIGH_EXPLOSIVE_ANTI_TANK",
        "HOLLOW_CHARGE",
        "HIGH_EXPLOSIVE"
    ]

    selected_shell = None

    for preferred in preferred_types:
        for shell in ammo:
            if not isinstance(shell, dict):
                continue

            if shell.get("type") == preferred:
                selected_shell = shell
                break

        if selected_shell is not None:
            break

    if selected_shell is None:
        for shell in ammo:
            if isinstance(shell, dict):
                selected_shell = shell
                break

    if isinstance(selected_shell, dict):
        damage = middle_value(
            selected_shell.get("damage"),
            0
        )

        penetration = middle_value(
            selected_shell.get("penetration"),
            0
        )

        shell_type = safe_text(
            selected_shell.get("type")
        )

        shell_velocity = first_number(
            selected_shell.get("speed"),
            selected_shell.get("velocity"),
            selected_shell.get("bullet_speed"),
            default=0
        )

    return {
        "damage": clean_number(damage),
        "penetration": clean_number(penetration),
        "shellType": shell_type,
        "shellVelocity": clean_number(shell_velocity)
    }


# ============================================================
# LÖVEG
# ============================================================

def extract_gun(profile):
    gun = profile.get("gun") or {}

    if not isinstance(gun, dict):
        gun = {}

    ammo = profile.get("ammo") or []

    ammo_data = extract_ammo(ammo)

    damage = ammo_data["damage"]
    penetration = ammo_data["penetration"]

    fire_rate = first_number(
        gun.get("fire_rate"),
        default=0
    )

    reload_time = first_number(
        gun.get("reload_time"),
        default=0
    )

    caliber = first_number(
        gun.get("caliber"),
        default=0
    )

    aim_time = first_number(
        gun.get("aim_time"),
        default=0
    )

    dispersion = first_number(
        gun.get("dispersion"),
        default=0
    )

    traverse_speed = first_number(
        gun.get("traverse_speed"),
        default=0
    )

    depression = first_number(
        gun.get("move_down_arc"),
        default=0
    )

    elevation = first_number(
        gun.get("move_up_arc"),
        default=0
    )

    if reload_time == 0 and fire_rate > 0:
        reload_time = 60 / fire_rate

    if fire_rate == 0 and reload_time > 0:
        fire_rate = 60 / reload_time

    dpm = 0

    if damage > 0 and fire_rate > 0:
        dpm = damage * fire_rate

    return {
        "name": safe_text(gun.get("name")),
        "damage": clean_number(damage),
        "penetration": clean_number(penetration),
        "reload": round(reload_time, 2),
        "fireRate": round(fire_rate, 2),
        "dpm": round(dpm),
        "caliber": clean_number(caliber),
        "aimTime": round(aim_time, 2),
        "dispersion": round(dispersion, 3),
        "traverseSpeed": round(traverse_speed, 2),
        "depression": round(depression, 2),
        "elevation": round(elevation, 2),
        "shellType": ammo_data["shellType"],
        "shellVelocity": clean_number(
            ammo_data["shellVelocity"]
        )
    }


# ============================================================
# MOTOR
# ============================================================

def extract_engine(profile):
    engine = profile.get("engine") or {}

    if not isinstance(engine, dict):
        engine = {}

    return {
        "name": safe_text(engine.get("name")),
        "power": clean_number(
            first_number(
                engine.get("power"),
                default=0
            )
        ),
        "fireChance": round(
            first_number(
                engine.get("fire_chance"),
                engine.get("fireChance"),
                default=0
            ),
            3
        )
    }


# ============================================================
# TORONY
# ============================================================

def extract_turret(profile):
    turret = profile.get("turret") or {}

    if not isinstance(turret, dict):
        turret = {}

    return {
        "name": safe_text(turret.get("name")),
        "health": clean_number(
            first_number(
                turret.get("health"),
                default=0
            )
        ),
        "viewRange": clean_number(
            first_number(
                turret.get("view_range"),
                default=0
            )
        ),
        "traverseSpeed": round(
            first_number(
                turret.get("traverse_speed"),
                default=0
            ),
            2
        ),
        "weight": clean_number(
            first_number(
                turret.get("weight"),
                default=0
            )
        )
    }


# ============================================================
# FUTÓMŰ
# ============================================================

def extract_suspension(profile):
    suspension = profile.get("suspension") or {}

    if not isinstance(suspension, dict):
        suspension = {}

    return {
        "traverseSpeed": round(
            first_number(
                suspension.get("traverse_speed"),
                default=0
            ),
            2
        ),
        "loadLimit": clean_number(
            first_number(
                suspension.get("load_limit"),
                default=0
            )
        )
    }


# ============================================================
# MOBILITÁS
# ============================================================

def extract_mobility(profile):
    return {
        "speedForward": clean_number(
            first_number(
                profile.get("speed_forward"),
                default=0
            )
        ),
        "speedBackward": clean_number(
            first_number(
                profile.get("speed_backward"),
                default=0
            )
        )
    }


# ============================================================
# RÁDIÓ
# ============================================================

def extract_radio(profile):
    radio = profile.get("radio") or {}

    if not isinstance(radio, dict):
        radio = {}

    return {
        "name": safe_text(radio.get("name")),
        "signalRange": clean_number(
            first_number(
                radio.get("signal_range"),
                default=0
            )
        )
    }


# ============================================================
# PÁNCÉL
# ============================================================

def extract_armor(profile):
    armor = profile.get("armor") or {}

    if not isinstance(armor, dict):
        armor = {}

    hull = armor.get("hull") or {}
    turret = armor.get("turret") or {}

    if not isinstance(hull, dict):
        hull = {}

    if not isinstance(turret, dict):
        turret = {}

    return {
        "hull": {
            "front": clean_number(
                first_number(
                    hull.get("front"),
                    default=0
                )
            ),
            "side": clean_number(
                first_number(
                    hull.get("side"),
                    default=0
                )
            ),
            "rear": clean_number(
                first_number(
                    hull.get("rear"),
                    default=0
                )
            )
        },
        "turret": {
            "front": clean_number(
                first_number(
                    turret.get("front"),
                    default=0
                )
            ),
            "side": clean_number(
                first_number(
                    turret.get("side"),
                    default=0
                )
            ),
            "rear": clean_number(
                first_number(
                    turret.get("rear"),
                    default=0
                )
            )
        }
    }


# ============================================================
# TANK ÁTALAKÍTÁSA
# ============================================================

def convert_tank(
    tank_id,
    english_tank,
    language_data,
    image_map
):
    profile = english_tank.get("default_profile") or {}

    if not isinstance(profile, dict):
        profile = {}

    name = safe_text(
        english_tank.get("name")
    )

    short_name = safe_text(
        english_tank.get("short_name")
        or name
    )

    nation = safe_text(
        english_tank.get("nation")
    )

    tier = int(
        number(
            english_tank.get("tier"),
            0
        )
    )

    tank_type = safe_text(
        english_tank.get("type")
    )

    premium = bool(
        english_tank.get("is_premium", False)
    )

    gift = bool(
        english_tank.get("is_gift", False)
    )

    description = safe_text(
        english_tank.get("description")
    )

    # --------------------------------------------------------
    # NYELVI ADATOK
    # --------------------------------------------------------

    names = {}
    descriptions = {}

    for language, data in language_data.items():
        localized = data.get(str(tank_id))

        if not isinstance(localized, dict):
            continue

        localized_name = safe_text(
            localized.get("name")
        )

        localized_description = safe_text(
            localized.get("description")
        )

        if localized_name:
            names[language] = localized_name

        if localized_description:
            descriptions[language] = localized_description

    if "en" not in names and name:
        names["en"] = name

    if "en" not in descriptions and description:
        descriptions["en"] = description

    # --------------------------------------------------------
    # KÉP
    # --------------------------------------------------------

    image = image_map.get(
        str(tank_id),
        ""
    )

    # A régi "icon" mezőt is megtartjuk kompatibilitás miatt.
    icon = image

    # --------------------------------------------------------
    # HP
    # --------------------------------------------------------

    health = first_number(
        profile.get("hp"),
        default=0
    )

    hull_health = first_number(
        profile.get("hull_hp"),
        default=health
    )

    # --------------------------------------------------------
    # STATOK
    # --------------------------------------------------------

    armor = extract_armor(profile)
    gun = extract_gun(profile)
    engine = extract_engine(profile)
    turret = extract_turret(profile)
    suspension = extract_suspension(profile)
    mobility = extract_mobility(profile)
    radio = extract_radio(profile)

    weight = first_number(
        profile.get("weight"),
        default=0
    )

    max_weight = first_number(
        profile.get("max_weight"),
        default=0
    )

    max_ammo = first_number(
        profile.get("max_ammo"),
        default=0
    )

    return {
        "id": int(tank_id),
        "name": name,
        "shortName": short_name,
        "names": names,
        "nation": nation,
        "tier": tier,
        "type": tank_type,
        "premium": premium,
        "gift": gift,
        "image": image,
        "icon": icon,
        "description": description,
        "descriptions": descriptions,
        "stats": {
            "health": clean_number(health),
            "hullHealth": clean_number(hull_health),
            "armor": armor,
            "gun": gun,
            "engine": engine,
            "turret": turret,
            "suspension": suspension,
            "mobility": mobility,
            "radio": radio,
            "weight": clean_number(weight),
            "maxWeight": clean_number(max_weight),
            "maxAmmo": clean_number(max_ammo)
        }
    }


# ============================================================
# TELJES ADATBÁZIS
# ============================================================

def convert_tanks(all_data, image_map):
    english_data = all_data["en"]

    print()
    print("=" * 60)
    print(" TANKOK FELDOLGOZÁSA")
    print("=" * 60)
    print()

    tanks = []

    items = list(
        english_data.items()
    )

    for index, (tank_id, english_tank) in enumerate(
        items,
        start=1
    ):
        try:
            converted = convert_tank(
                tank_id,
                english_tank,
                all_data,
                image_map
            )

            tanks.append(converted)

        except Exception as exc:
            print()
            print(f"Hiba tank feldolgozásakor: {tank_id}")
            print(str(exc))
            print()

        if index % 100 == 0 or index == len(items):
            print(
                f"  Feldolgozás: {index}/{len(items)}"
            )

    # Stabil sorrend ID alapján.
    tanks.sort(
        key=lambda tank: tank.get("id", 0)
    )

    return tanks


# ============================================================
# ELLENŐRZÉS
# ============================================================

def validate_tanks(tanks):
    print()
    print("=" * 60)
    print(" WOTDB ELLENŐRZÉS")
    print("=" * 60)
    print()

    total = len(tanks)

    image_count = sum(
        1
        for tank in tanks
        if tank.get("image")
    )

    stats_count = sum(
        1
        for tank in tanks
        if isinstance(tank.get("stats"), dict)
    )

    translation_count = sum(
        1
        for tank in tanks
        if isinstance(tank.get("names"), dict)
        and len(tank.get("names")) > 1
    )

    print(f"  Tankok száma:       {total}")
    print(f"  Képekkel:           {image_count}")
    print(f"  Stat blokkal:       {stats_count}")
    print(f"  Többnyelvű névvel:  {translation_count}")
    print()

    if total == 0:
        print("HIBA: 0 tank került az adatbázisba.")
        return False

    return True


# ============================================================
# MENTÉS
# ============================================================

def save_tanks(tanks):
    print()
    print("=" * 60)
    print(" JSON MENTÉSE")
    print("=" * 60)
    print()

    try:
        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                tanks,
                file,
                ensure_ascii=False,
                indent=2
            )

    except OSError as exc:
        print(f"Mentési hiba: {exc}")
        return False

    print(f"  Elkészült: {OUTPUT_FILE}")
    return True


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 60)
    print(" WOTDB - WORLD OF TANKS DATABASE")
    print(" Adatbázis frissítő")
    print("=" * 60)
    print()

    print("1/4 - Wargaming API lekérések...")
    all_data = download_all_languages()

    if all_data is None:
        print()
        print("A frissítés sikertelen.")
        sys.exit(1)

    english_data = all_data["en"]

    print()
    print("2/4 - Játékbeli tankképek letöltése...")
    image_map = build_image_map(
        english_data
    )

    print()
    print("3/4 - Tankadatok feldolgozása...")
    tanks = convert_tanks(
        all_data,
        image_map
    )

    if not validate_tanks(tanks):
        print()
        print("A frissítés megszakadt.")
        sys.exit(1)

    print()
    print("4/4 - tanks.json mentése...")

    if not save_tanks(tanks):
        sys.exit(1)

    print()
    print("=" * 60)
    print(" KÉSZ")
    print("=" * 60)
    print()
    print("Az index.html most már a helyi images/ mappából")
    print("fogja betölteni a tankképeket.")
    print()
    print("Készült:")
    print(f"  - {OUTPUT_FILE}")
    print(f"  - {IMAGE_DIR}/")
    print()


if __name__ == "__main__":
    main()
