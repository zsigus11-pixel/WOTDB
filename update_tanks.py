import json
import os
import sys
import requests


# ============================================================
# WOTDB - WORLD OF TANKS DATABASE UPDATER
# ============================================================

APPLICATION_ID = "d7244866d929b2fe3df6b976ccb68ff8"

API_URL = "https://api.worldoftanks.eu/wot/encyclopedia/vehicles/"
OUTPUT_FILE = "tanks.json"


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

    if float(value).is_integer():
        return int(value)

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
    három elemű listaként adja:

        [minimum, átlag, maximum]

    Példa:

        damage:      [83, 110, 138]
        penetration: [81, 108, 135]

    Ezért a középső értéket használjuk.
    """

    if isinstance(value, list):

        if len(value) >= 3:
            return number(value[1], default)

        if len(value) == 2:
            return number(value[0], default)

        if len(value) == 1:
            return number(value[0], default)

        return default

    if isinstance(value, tuple):

        if len(value) >= 3:
            return number(value[1], default)

        if len(value) == 2:
            return number(value[0], default)

        if len(value) == 1:
            return number(value[0], default)

        return default

    return number(value, default)


# ============================================================
# API LEKÉRÉS
# ============================================================

def download_tanks():

    print()
    print("=" * 40)
    print(" WARGAMING API")
    print("=" * 40)
    print()

    print("Tankadatok lekérése...")
    print()
    print("Ez most szándékosan fields paraméter nélkül fut.")
    print("Így elkerüljük az INVALID_FIELDS hibát.")
    print()

    params = {
        "application_id": APPLICATION_ID,
        "language": "en"
    }

    try:

        response = requests.get(
            API_URL,
            params=params,
            timeout=60
        )

    except requests.RequestException as e:

        print()
        print("=" * 40)
        print(" HÁLÓZATI HIBA")
        print("=" * 40)
        print()

        print(str(e))

        return None

    try:

        result = response.json()

    except ValueError:

        print()
        print("=" * 40)
        print(" API VÁLASZ HIBA")
        print("=" * 40)
        print()

        print(
            response.text[:3000]
        )

        return None

    if result.get("status") != "ok":

        print()
        print("=" * 40)
        print(" WARGAMING API HIBA")
        print("=" * 40)
        print()

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

        return None

    data = result.get("data") or {}

    print()
    print(
        "Tankok száma az API válaszban:",
        len(data)
    )
    print()

    return data


# ============================================================
# AMMO
# ============================================================

def extract_ammo(ammo):

    """
    Feldolgozza a Wargaming API ammo listáját.

    Példa:

    [
        {
            "penetration": [81, 108, 135],
            "type": "ARMOR_PIERCING",
            "damage": [83, 110, 138]
        }
    ]

    Visszatérés:

        damage = 110
        penetration = 108
    """

    damage = 0
    penetration = 0

    shell_type = ""
    shell_velocity = 0

    # --------------------------------------------------------
    # Nem lista
    # --------------------------------------------------------

    if not isinstance(ammo, list):

        return {
            "damage": 0,
            "penetration": 0,
            "shellType": "",
            "shellVelocity": 0
        }

    # --------------------------------------------------------
    # Elsődleges lövedék keresése
    #
    # Elsőként AP-t választunk.
    # Ha nincs, akkor APCR / HEAT / HE stb.
    # --------------------------------------------------------

    preferred_types = [
        "ARMOR_PIERCING",
        "ARMOR_PIERCING_CR",
        "HIGH_EXPLOSIVE_ANTI_TANK",
        "HIGH_EXPLOSIVE",
        "HOLLOW_CHARGE"
    ]

    selected_shell = None

    # Először próbáljuk az AP-t megtalálni.

    for preferred in preferred_types:

        for shell in ammo:

            if not isinstance(shell, dict):
                continue

            if shell.get("type") == preferred:

                selected_shell = shell

                break

        if selected_shell is not None:
            break

    # Ha valamiért nincs ismert típus,
    # használjuk az első érvényes lövedéket.

    if selected_shell is None:

        for shell in ammo:

            if isinstance(shell, dict):

                selected_shell = shell

                break

    # --------------------------------------------------------
    # Adatok kiolvasása
    # --------------------------------------------------------

    if isinstance(selected_shell, dict):

        damage = middle_value(
            selected_shell.get("damage"),
            0
        )

        penetration = middle_value(
            selected_shell.get("penetration"),
            0
        )

        shell_type = (
            selected_shell.get("type")
            or ""
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

    # --------------------------------------------------------
    # AMMO
    # --------------------------------------------------------

    ammo_data = extract_ammo(ammo)

    damage = ammo_data["damage"]
    penetration = ammo_data["penetration"]

    shell_type = ammo_data["shellType"]
    shell_velocity = ammo_data["shellVelocity"]

    # --------------------------------------------------------
    # GUN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # GUN ELEVATION / DEPRESSION
    # --------------------------------------------------------

    depression = first_number(
        gun.get("move_down_arc"),
        default=0
    )

    elevation = first_number(
        gun.get("move_up_arc"),
        default=0
    )

    # --------------------------------------------------------
    # RELOAD / FIRE RATE
    # --------------------------------------------------------

    if reload_time == 0 and fire_rate > 0:

        reload_time = 60 / fire_rate

    if fire_rate == 0 and reload_time > 0:

        fire_rate = 60 / reload_time

    # --------------------------------------------------------
    # DPM
    # --------------------------------------------------------

    dpm = 0

    if damage > 0 and fire_rate > 0:

        dpm = damage * fire_rate

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {
        "name": gun.get("name", ""),

        "damage": clean_number(damage),
        "penetration": clean_number(penetration),

        "reload": round(
            reload_time,
            2
        ),

        "fireRate": round(
            fire_rate,
            2
        ),

        "dpm": round(
            dpm
        ),

        "caliber": clean_number(
            caliber
        ),

        "aimTime": round(
            aim_time,
            2
        ),

        "dispersion": round(
            dispersion,
            3
        ),

        "traverseSpeed": round(
            traverse_speed,
            2
        ),

        "depression": round(
            depression,
            2
        ),

        "elevation": round(
            elevation,
            2
        ),

        "shellType": shell_type,

        "shellVelocity": clean_number(
            shell_velocity
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
        "name": engine.get(
            "name",
            ""
        ),

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
        "name": turret.get(
            "name",
            ""
        ),

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
        "name": radio.get(
            "name",
            ""
        ),

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

def convert_tank(tank_id, tank):

    profile = tank.get(
        "default_profile"
    ) or {}

    if not isinstance(profile, dict):
        profile = {}

    # --------------------------------------------------------
    # ALAPADATOK
    # --------------------------------------------------------

    name = tank.get(
        "name",
        ""
    )

    short_name = (
        tank.get("short_name")
        or name
    )

    nation = tank.get(
        "nation",
        ""
    )

    tier = tank.get(
        "tier",
        0
    )

    tank_type = tank.get(
        "type",
        ""
    )

    premium = bool(
        tank.get(
            "is_premium",
            False
        )
    )

    gift = bool(
        tank.get(
            "is_gift",
            False
        )
    )

    # --------------------------------------------------------
    # KÉP
    # --------------------------------------------------------

    images = tank.get(
        "images"
    ) or {}

    icon = ""

    if isinstance(images, dict):

        icon = images.get(
            "contour_icon",
            ""
        )

    # --------------------------------------------------------
    # LEÍRÁS
    # --------------------------------------------------------

    description = tank.get(
        "description",
        ""
    )

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

    armor = extract_armor(
        profile
    )

    gun = extract_gun(
        profile
    )

    engine = extract_engine(
        profile
    )

    turret = extract_turret(
        profile
    )

    suspension = extract_suspension(
        profile
    )

    mobility = extract_mobility(
        profile
    )

    radio = extract_radio(
        profile
    )

    # --------------------------------------------------------
    # TÖMEG
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {
        "id": int(tank_id),

        "name": name,
        "shortName": short_name,

        "nation": nation,
        "tier": int(
            number(tier)
        ),

        "type": tank_type,

        "premium": premium,
        "gift": gift,

        "icon": icon,

        "description": description,

        "stats": {

            "health": clean_number(
                health
            ),

            "hullHealth": clean_number(
                hull_health
            ),

            "armor": armor,

            "gun": gun,

            "engine": engine,

            "turret": turret,

            "suspension": suspension,

            "mobility": mobility,

            "radio": radio,

            "weight": clean_number(
                weight
            ),

            "maxWeight": clean_number(
                max_weight
            ),

            "maxAmmo": clean_number(
                max_ammo
            )
        }
    }


# ============================================================
# TELJES ADATBÁZIS
# ============================================================

def convert_tanks(data):

    print(
        "Tankok feldolgozása..."
    )

    tanks = []

    items = list(
        data.items()
    )

    for index, (tank_id, tank) in enumerate(
        items,
        start=1
    ):

        try:

            converted = convert_tank(
                tank_id,
                tank
            )

            tanks.append(
                converted
            )

        except Exception as e:

            print()

            print(
                "Hiba tank feldolgozásakor:"
            )

            print(
                "ID:",
                tank_id
            )

            print(
                "Hiba:",
                str(e)
            )

            print()

        if (
            index % 100 == 0
            or
            index == len(items)
        ):

            print(
                f"  {index}/{len(items)}"
            )

    return tanks


# ============================================================
# ELLENŐRZÉS
# ============================================================

def validate_tanks(tanks):

    print()
    print("=" * 40)
    print(" WOTDB ELLENŐRZÉS")
    print("=" * 40)
    print()

    total = len(
        tanks
    )

    stats_count = 0
    hp_count = 0
    gun_count = 0
    armor_count = 0
    dpm_count = 0

    for tank in tanks:

        stats = tank.get(
            "stats"
        ) or {}

        if stats:

            stats_count += 1

        if number(
            stats.get(
                "health"
            )
        ) > 0:

            hp_count += 1

        gun = stats.get(
            "gun"
        ) or {}

        if (
            number(
                gun.get(
                    "damage"
                )
            ) > 0
            and
            number(
                gun.get(
                    "penetration"
                )
            ) > 0
        ):

            gun_count += 1

        armor = stats.get(
            "armor"
        ) or {}

        if armor:

            armor_count += 1

        if number(
            gun.get(
                "dpm"
            )
        ) > 0:

            dpm_count += 1

    print(
        f"Összes tank:       {total}"
    )

    print(
        f"Stats objektum:    {stats_count}"
    )

    print(
        f"HP adat:           {hp_count}"
    )

    print(
        f"Löveg adat:        {gun_count}"
    )

    print(
        f"Páncél adat:       {armor_count}"
    )

    print(
        f"DPM adat:          {dpm_count}"
    )

    # --------------------------------------------------------
    # MINTA
    # --------------------------------------------------------

    print()
    print(
        "MINTA TANK:"
    )

    if tanks:

        print(
            json.dumps(
                tanks[0],
                indent=2,
                ensure_ascii=False
            )
        )


# ============================================================
# MENTÉS
# ============================================================

def save_tanks(tanks):

    print()
    print("=" * 40)
    print(" JSON MENTÉS")
    print("=" * 40)
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

    except OSError as e:

        print(
            "Mentési hiba:"
        )

        print(
            str(e)
        )

        return False

    file_size = os.path.getsize(
        OUTPUT_FILE
    )

    print(
        "Sikeres mentés!"
    )

    print()

    print(
        "Fájl:",
        os.path.abspath(
            OUTPUT_FILE
        )
    )

    print(
        "Méret:",
        round(
            file_size / 1024,
            1
        ),
        "KB"
    )

    print(
        "Tankok:",
        len(tanks)
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 40)
    print(" WOTDB TANK DATABASE UPDATER")
    print("=" * 40)
    print()

    # --------------------------------------------------------
    # APPLICATION ID ELLENŐRZÉS
    # --------------------------------------------------------

    if (
        not APPLICATION_ID
        or
        APPLICATION_ID
        == "IDE_JON_A_SAJAT_APPLICATION_ID"
    ):

        print(
            "HIBA:"
        )

        print()

        print(
            "Az APPLICATION_ID nincs beállítva."
        )

        print()

        print(
            "Nyisd meg az update_tanks.py fájlt,"
        )

        print(
            "és írd be a saját Wargaming Application ID-det."
        )

        sys.exit(1)

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    data = download_tanks()

    if not data:

        print()

        print(
            "Az adatlekérés sikertelen."
        )

        sys.exit(1)

    # --------------------------------------------------------
    # ÁTALAKÍTÁS
    # --------------------------------------------------------

    tanks = convert_tanks(
        data
    )

    # --------------------------------------------------------
    # ELLENŐRZÉS
    # --------------------------------------------------------

    validate_tanks(
        tanks
    )

    # --------------------------------------------------------
    # MENTÉS
    # --------------------------------------------------------

    success = save_tanks(
        tanks
    )

    if not success:

        sys.exit(1)

    print()
    print("=" * 40)
    print(" KÉSZ!")
    print("=" * 40)
    print()

    print(
        "A tanks.json elkészült."
    )

    print()


# ============================================================
# INDÍTÁS
# ============================================================

if __name__ == "__main__":

    main()
