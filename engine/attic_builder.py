import os
import json
import re
import time
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/attic-fan-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9").strip()
CUSTOM_ATTIC = os.environ.get("CUSTOM_ATTIC", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_attics.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

_CACHED_MODELS = None

# Format: (Model / Home Scenario, Home/Attic Sq Ft, Target Fan CFM, Running Watts, Ceiling Height Ft, Vent System Type)
SEED_ATTICS = [
    ("QuietCool CL-1500 Classic (1,472 CFM) Bedroom Whole-House Fan", 650, 1472, 117, 8, "Ducted R5 Damper Box"),
    ("QuietCool CL-2250 Classic (2,256 CFM) Whole-House Fan", 950, 2256, 250, 8, "Ducted R5 Damper Box"),
    ("QuietCool CL-3100 Classic (3,078 CFM) Whole-House Fan", 1300, 3078, 297, 8, "Ducted R5 Damper Box"),
    ("QuietCool CL-4700 Classic (4,685 CFM) Whole-House Fan", 1900, 4685, 525, 9, "Ducted R5 Damper Box"),
    ("QuietCool CL-5400 Classic (5,440 CFM) Whole-House Fan", 2200, 5440, 637, 9, "Ducted R5 Damper Box"),
    ("QuietCool CL-6000 Classic (5,876 CFM) Whole-House Fan", 2500, 5876, 728, 9, "Ducted R5 Damper Box"),
    ("QuietCool CL-7000 Classic (6,966 CFM) Estate Whole-House Fan", 3000, 6966, 995, 10, "Dual-Ducted R5 Damper"),
    ("QuietCool ES-5400 & ES-7000 Energy Saver ECM Brushless Fan", 2400, 5351, 415, 9, "ECM Brushless Motor"),
    ("QuietCool Trident Pro-4.8X & Pro-5.5X High-Airflow Fan", 2200, 5440, 550, 9, "Pro-Series Acoustical Duct"),
    ("QuietCool RM-WHF-4.0 Roof-Mount Ductless Whole-House Fan", 1700, 3810, 450, 8, "Roof-Mounted Curb WHF"),
    ("QuietCool AFR-SMT-2.0 Smart Attic Gable/Roof Exhaust Fan", 2000, 1945, 140, 8, "Smart Thermostat Attic Fan"),
    ("AirScape 2.5e & 3.5e (2,600 / 3,420 CFM) Whole-House Fan", 1400, 3420, 260, 8, "R-49 Insulated Door Box"),
    ("AirScape 4.4e & 5.3e (4,350 / 5,180 CFM) Whole-House Fan", 2100, 5180, 460, 9, "R-49 Insulated Door Box"),
    ("CentricAir 2.7 & 3.4 (2,700 / 3,400 CFM) Whole-House Fan", 1500, 3400, 310, 8, "Acoustical R-5 Damper"),
    ("CentricAir 4.0 & 5.2 (4,000 / 5,200 CFM) Dual-Speed Fan", 2200, 5200, 540, 9, "Acoustical R-5 Damper"),
    ("QA-Deluxe 4800 & 5500 Belt/Direct-Drive Whole-House Fan", 2000, 4800, 490, 9, "Insulated Ceiling Shutter"),
    ("Master Flow & Broan 1,500 CFM Powered Attic Gable Ventilator", 1800, 1500, 180, 8, "Thermostat Gable Fan"),
    ("Remington Solar 30-Watt & 40-Watt (2,250 CFM) Roof Attic Fan", 2200, 2250, 0, 8, "Brushless Solar Roof Vent"),
    (" Natural Light 35W & 65W Commercial Solar Attic Ventilator", 2500, 2460, 0, 9, "Solar Roof-Mount Vent"),
    ("GAF Cobra SnowCountry Ridge Vent & Undereave Soffit Sizing", 2000, 4500, 450, 8, "Balanced Ridge + Soffit"),
    ("1,200 Sq Ft Home & Attic Whole-House Fan & NFA Sizing", 1200, 3000, 290, 8, "4.0 Sq Ft Net Free Vent"),
    ("1,500 Sq Ft Home & Attic Whole-House Fan & NFA Sizing", 1500, 3750, 360, 8, "5.0 Sq Ft Net Free Vent"),
    ("1,800 Sq Ft Home & Attic Whole-House Fan & NFA Sizing", 1800, 4500, 480, 9, "6.0 Sq Ft Net Free Vent"),
    ("2,000 Sq Ft Home & Attic Whole-House Fan & NFA Sizing", 2000, 5000, 530, 9, "6.7 Sq Ft Net Free Vent"),
    ("2,400 Sq Ft Two-Story Home Whole-House Fan & NFA Sizing", 2400, 6000, 680, 9, "8.0 Sq Ft Net Free Vent"),
    ("2,800 Sq Ft Two-Story Home Whole-House Fan & NFA Sizing", 2800, 7000, 850, 9, "9.3 Sq Ft Net Free Vent"),
    ("3,500 Sq Ft Large Home Dual Whole-House Fan & NFA Sizing", 3500, 8750, 980, 10, "11.7 Sq Ft Net Free Vent"),
    ("IRC Section R806.2 1:150 vs 1:300 Attic Ventilation Calculator", 2000, 4800, 500, 8, "50% Soffit / 50% Ridge"),
    ("16\" × 8\" Undereave Soffit Vent Count & Baffle Calculator", 2000, 4800, 500, 8, "56 Sq In NFA per Vent"),
    ("1:750 CFM Whole-House Fan Attic Exhaust Louver & Screen Rule", 2200, 5440, 580, 9, "2x Gross Area for 1/8\" Mesh")
]


def load_json(filepath, default):
    """Self-healing JSON loader: otomatis pulih jika file korup atau kosong."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, type(default)) else default
        except Exception as e:
            print(f"[SELF-HEAL] Recovering {filepath} due to read notice: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=2000.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def get_active_gemini_model(api_key):
    """
    LAPIS 1: Mesin Pemindai Versi Otomatis berbasis Regex tanpa angka versi manual.
    Otomatis mendeteksi model Gemini Flash STABIL generasi tertinggi lintas tahun.
    """
    global _CACHED_MODELS
    if _CACHED_MODELS is not None:
        return _CACHED_MODELS

    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(list_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            scored_models = []

            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])

                if "generateContent" not in methods or "flash" not in name.lower():
                    continue

                if any(bad in name.lower() for bad in [
                    "preview", "exp", "thinking", "image", "tts", "audio", "vision", "8b"
                ]):
                    continue

                ver_match = re.search(r"gemini-(\d+(?:\.\d+)?)-flash", name.lower())
                if ver_match:
                    ver_num = float(ver_match.group(1))
                    if name.lower() == f"gemini-{ver_match.group(1)}-flash":
                        tier_score = 2
                    elif name.lower() == f"gemini-{ver_match.group(1)}-flash-lite":
                        tier_score = 1
                    else:
                        tier_score = 0
                    scored_models.append((ver_num, tier_score, name))
                elif name.lower() == "gemini-flash-latest":
                    scored_models.append((0.1, 0, name))

            if scored_models:
                scored_models.sort(key=lambda x: (x[0], x[1]), reverse=True)
                _CACHED_MODELS = [item[2] for item in scored_models[:2]]
                print(f"[GEMINI] Future-proof active models locked: {_CACHED_MODELS}")
                return _CACHED_MODELS
    except Exception as e:
        print(f"[WARN] Dynamic model discovery notice: {e}")

    _CACHED_MODELS = ["gemini-flash-latest"]
    return _CACHED_MODELS


def discover_google_attic_queries(published_slugs):
    """
    LAPIS 4: 3-Tier Infinite Keyword Supply:
    Tier A: Seed List -> Tier B: Google Suggest US -> Tier C: Combinatorial Home Sq Ft × ACH Permutator.
    """
    discovered = []
    seeds = [
        "what size whole house fan for ",
        "quietcool whole house fan ",
        "attic vent calculator ",
        "how many soffit vents for "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        if "what size" in pref or "how many" in pref or "calculator" in pref:
                            cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|cfm|chart|manual|review|reddit|for)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        sq_m = re.search(r"(\d{4})", cleaned)
                        sq_v = int(sq_m.group(1)) if sq_m else 2000
                        cfm_v = int(round(sq_v * 2.5, -1))
                        discovered.append((cleaned.title(), sq_v, cfm_v, int(cfm_v * 0.11), 9, "Ducted Whole-House Fan"))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")

    # Tier C Fallback: Combinatorial Permutator (Anti-Habis Lintas Tahun)
    home_sizes = [1000, 1300, 1600, 1900, 2100, 2300, 2600, 3000, 3400, 4000]
    climate_profiles = [
        ("Desert / Hot-Dry Climate (3.0 CFM/ft²)", 3.0),
        ("Warm / Coastal Climate (2.5 CFM/ft²)", 2.5),
        ("Moderate / Mountain Climate (2.0 CFM/ft²)", 2.0)
    ]
    for sq_ft in home_sizes:
        for clim_desc, cfm_mult in climate_profiles:
            combo_title = f"{sq_ft:,} Sq Ft Home in {clim_desc}"
            test_slug = slugify(f"{combo_title}-whole-house-fan-nfa-calculator")
            if test_slug not in published_slugs:
                t_cfm = int(round(sq_ft * cfm_mult, -1))
                w_est = int(round(t_cfm * 0.105))
                discovered.append((combo_title, sq_ft, t_cfm, w_est, 9, "Ducted R5 Whole-House Fan"))
                if len(discovered) >= 25:
                    return discovered
    return discovered


def build_deterministic_attic_data(attic_tuple):
    """
    LAPIS 3: Mesin Fisika Ventilasi Loteng HVI-916 & IRC Section R806.2 (100% Bebas Gagal).
    """
    item_name, home_sqft, fan_cfm, fan_watts, ceil_ft, sys_type = attic_tuple

    # 1. Volume Rumah & Air Changes Per Hour (ACH):
    home_vol_cuft = int(round(home_sqft * ceil_ft))
    ach_rate = round((fan_cfm * 60.0) / max(1000.0, float(home_vol_cuft)), 1)
    minutes_per_exchange = round(60.0 / max(1.0, ach_rate), 1)

    # 2. Kebutuhan Lubang Ventilasi Loteng untuk Whole-House Fan (Aturan 1 Sq Ft NFA per 750 CFM):
    whf_nfa_sqft = round(fan_cfm / 750.0, 1)
    whf_nfa_sqin = int(round(whf_nfa_sqft * 144.0))
    # Luas Lubang Kotor (Gross Cutout Area dengan kawat nyamuk 1/8" + kisi louver = 2.0x NFA):
    whf_gross_louver_sqft = round(whf_nfa_sqft * 2.0, 1)

    # 3. Aturan Kode Bangunan Pasif IRC Section R806.2 (1:150 Standard vs 1:300 Balanced):
    irc_150_nfa_sqin = int(round((home_sqft / 150.0) * 144.0))
    irc_300_nfa_sqin = int(round((home_sqft / 300.0) * 144.0))
    # 50% Soffit Intake (menggunakan 16"x8" vented soffit @ 56 sq. in. NFA/unit) & 50% Ridge Vent (@ 18 sq. in. NFA/linear ft)
    soffit_vents_16x8 = max(6, int(math.ceil((whf_nfa_sqin * 0.50) / 56.0)))
    ridge_vent_lin_ft = max(12, int(math.ceil((whf_nfa_sqin * 0.50) / 18.0)))

    return {
        "attic_name": item_name,
        "sys_type": sys_type,
        "seo_title": f"{item_name} CFM, Attic NFA Vent & IRC R806.2 Calculator (2026)",
        "meta_description": f"Calculate exact whole-house fan airflow ({fan_cfm:,} CFM / {ach_rate} ACH), 1:750 attic exhaust Net Free Area ({whf_nfa_sqft} sq ft / {whf_nfa_sqin:,} sq in NFA), and IRC R806.2 soffit/ridge vents for {item_name}.",
        "specs": {
            "home_floor_sqft": home_sqft,
            "ceiling_height_ft": ceil_ft,
            "recommended_fan_cfm": fan_cfm,
            "air_changes_per_hour": ach_rate,
            "minutes_per_air_change": minutes_per_exchange,
            "whf_required_nfa_sqft": whf_nfa_sqft,
            "whf_required_nfa_sqin": whf_nfa_sqin,
            "gross_screened_louver_sqft": whf_gross_louver_sqft,
            "irc_150_passive_nfa_sqin": irc_150_nfa_sqin,
            "soffit_vents_16x8_count": soffit_vents_16x8,
            "ridge_vent_linear_ft": ridge_vent_lin_ft,
            "running_watts": fan_watts,
            "sys_type": sys_type
        },
        "irc_verdict": f"Moving {fan_cfm:,} CFM across a {home_sqft:,} sq. ft. home ({home_vol_cuft:,} cu. ft. volume) delivers {ach_rate} complete Air Changes Per Hour (replacing all indoor air with cool outdoor air every {minutes_per_exchange} minutes while drawing just {fan_watts}W—90% less than central A/C). To prevent positive attic backpressure from blowing dust back into living spaces, HVI-916 and manufacturer rules require 1.0 sq. ft. of Net Free Vent Area (NFA) per 750 CFM = {whf_nfa_sqft} sq. ft. ({whf_nfa_sqin:,} sq. in. NFA, or {whf_gross_louver_sqft} sq. ft. gross screened louver area)—achievable via {soffit_vents_16x8}× 16\"×8\" soffit vents plus {ridge_vent_lin_ft} linear feet of high-NFA shingle-over ridge vent.",
        "hardware_bundle": [
            {
                "badge": f"{fan_cfm:,} CFM Ducted Fan",
                "title": f"{item_name} ({fan_cfm:,} CFM Acoustical Ducted Whole-House Fan w/ R-5 Damper Box)",
                "price_range": "$379 - $1,599",
                "amazon_query": f"QuietCool Whole House Fan {fan_cfm} CFM Ducted Damper",
                "vent_note": f"Suspended acoustical duct isolates motor hum in the rafters while pulling {ach_rate} ACH through open windows."
            },
            {
                "badge": f"{whf_nfa_sqft} ft² NFA Ridge & Soffit",
                "title": f"Shingle-Over High-Flow Ridge Vent Roll ({ridge_vent_lin_ft}+ Ft) + 16\"×8\" Aluminum Soffit Vents & Rafter Baffles",
                "price_range": "$79 - $249",
                "amazon_query": "Shingle Over Ridge Vent Roll 16x8 Aluminum Soffit Vent Rafter Baffles",
                "vent_note": f"Provides {whf_nfa_sqin:,} sq. in. of unobstructed Net Free Area so {fan_cfm:,} CFM exhausts freely out the roof peak."
            },
            {
                "badge": "Solar Roof Attic Ventilator",
                "title": "Brushless 35W–40W Solar Roof-Mount / Smart Gable Attic Exhaust Fan w/ Humidistat & Thermostat",
                "price_range": "$169 - $449",
                "amazon_query": "Solar Roof Attic Fan Brushless Thermostat Humidistat",
                "vent_note": "Purges 140°F daytime solar heat from roof decking at zero electric cost before you run your whole-house fan at dusk."
            },
            {
                "badge": "R-50 Hatch Cover & Timer",
                "title": "R-50 Zippered Foil Attic Stairs Insulation Tent Cover + Wi-Fi Smart Countdown Timer Wall Switch",
                "price_range": "$54 - $129",
                "amazon_query": "Attic Stairs Insulation Cover Tent R50 QuietCool Timer Switch",
                "vent_note": "Stops hot attic air from leaking back around pull-down attic ladders and automates 1–8 hour nighttime fan shutoff."
            }
        ],
        "roofer_checklist": [
            f"Never confuse Gross Vent Cutout Area with Net Free Area (NFA): 1/8-inch insect wire mesh and angled rain louvers block 45% to 50% of airflow—so getting {whf_nfa_sqft} sq. ft. ({whf_nfa_sqin:,} sq. in.) of true NFA requires ~{whf_gross_louver_sqft} sq. ft. of gross screened gable/dormer openings.",
            "Open 2 to 4 windows at least 4 to 6 inches BEFORE turning on a whole-house fan: running a 3,000+ CFM fan with all windows closed creates strong negative indoor pressure that can backdraft fireplace chimneys and gas water heaters.",
            "Install Polystyrene/Cardboard Rafter Insulation Baffles (ProVent) in every soffit bay so blown-in fiberglass or cellulose insulation never plugs your eave intake vents.",
            "Never mix two different exhaust types (e.g., powered gable fan next to a ridge vent) without sufficient low-eave soffit intake, or the fan will short-circuit and suck rain/snow backward through the ridge vent."
        ],
        "faqs": [
            {
                "q": f"How much attic venting (Net Free Area) do I need for {item_name} ({fan_cfm:,} CFM)?",
                "a": f"Divide your total whole-house fan airflow ({fan_cfm:,} CFM) by 750 to get {whf_nfa_sqft} square feet ({whf_nfa_sqin:,} square inches) of Net Free Vent Area (NFA). Because bug screens and louvers cut airflow in half, your gross cutout area across gable, dormer, O'Hagin, or ridge/soffit vents must be ~{whf_gross_louver_sqft} sq. ft."
            },
            {
                "q": f"How do I calculate passive attic ventilation under IRC Code R806.2 for a {home_sqft:,} sq ft attic?",
                "a": f"Under the International Residential Code (IRC R806.2), standard attics require a 1:150 ratio ({home_sqft:,} ÷ 150 = {round(home_sqft/150.0, 1)} sq. ft. / {irc_150_nfa_sqin} sq. in. NFA). If at least 40%–50% of the vents are high on the roof (ridge vents) and the remainder are low eave soffit vents, code allows a 1:300 ratio ({irc_300_nfa_sqin} sq. in. NFA)."
            },
            {
                "q": f"How many 16x8 soffit vents and feet of ridge vent equal {whf_nfa_sqin:,} sq in of NFA?",
                "a": f"A standard 16\"×8\" aluminum soffit vent provides ~56 sq. in. of NFA, and a high-profile shingle-over ridge vent provides ~18 sq. in. of NFA per linear foot. Splitting {whf_nfa_sqin:,} sq. in. 50/50 requires {soffit_vents_16x8} soffit vents and {ridge_vent_lin_ft} linear feet of ridge vent."
            }
        ]
    }


def generate_attic_data(attic_tuple):
    """
    LAPIS 2: Memanggil model Gemini stabil dengan proteksi Cooldown HTTP 429 & Fallback Otomatis.
    """
    if not GEMINI_API_KEY:
        return build_deterministic_attic_data(attic_tuple)

    item_name, home_sqft, fan_cfm, fan_watts, ceil_ft, sys_type = attic_tuple
    det_fallback = build_deterministic_attic_data(attic_tuple)
    sp = det_fallback["specs"]

    prompt = f"""
You are a Certified Building Performance Institute (BPI) Envelope Engineer & Master Roofing Ventilation Specialist (IRC Section R806.2 & HVI-916). Create an accurate 2026 whole-house fan CFM, Air Changes Per Hour (ACH), 1:750 attic Net Free Vent Area (NFA), and soffit/ridge vent sizing guide for: "{item_name}".
Baseline specs: Home Area={home_sqft} sq ft ({ceil_ft}ft ceiling), Fan Airflow={fan_cfm} CFM ({sp['air_changes_per_hour']} ACH / {sp['minutes_per_air_change']} min per exchange, {fan_watts}W), Required WHF Attic NFA={sp['whf_required_nfa_sqft']} sq ft ({sp['whf_required_nfa_sqin']} sq in NFA / {sp['gross_screened_louver_sqft']} sq ft gross screened), IRC 1:150 Passive NFA={sp['irc_150_passive_nfa_sqin']} sq in, Vent Split={sp['soffit_vents_16x8_count']}x 16x8 Soffit Vents + {sp['ridge_vent_linear_ft']} ft Ridge Vent.
Return ONLY a valid JSON object matching this exact schema:
{{
  "attic_name": "{item_name}",
  "sys_type": "{sys_type}",
  "seo_title": "{item_name} CFM, Attic NFA Vent & IRC R806.2 Calculator (2026)",
  "meta_description": "Calculate exact whole-house fan CFM, 1:750 attic Net Free Area (NFA), and IRC R806.2 soffit and ridge vent counts for {item_name}.",
  "specs": {{
    "home_floor_sqft": {home_sqft},
    "ceiling_height_ft": {ceil_ft},
    "recommended_fan_cfm": {fan_cfm},
    "air_changes_per_hour": {sp['air_changes_per_hour']},
    "minutes_per_air_change": {sp['minutes_per_air_change']},
    "whf_required_nfa_sqft": {sp['whf_required_nfa_sqft']},
    "whf_required_nfa_sqin": {sp['whf_required_nfa_sqin']},
    "gross_screened_louver_sqft": {sp['gross_screened_louver_sqft']},
    "irc_150_passive_nfa_sqin": {sp['irc_150_passive_nfa_sqin']},
    "soffit_vents_16x8_count": {sp['soffit_vents_16x8_count']},
    "ridge_vent_linear_ft": {sp['ridge_vent_linear_ft']},
    "running_watts": {fan_watts},
    "sys_type": "{sys_type}"
  }},
  "irc_verdict": "3-sentence technical summary stating CFM, ACH air exchange time, 1:750 CFM Net Free Area in sq ft and sq in, and required 16x8 soffit vents and linear feet of ridge vent.",
  "hardware_bundle": [
    {{
      "badge": "{fan_cfm:,} CFM Whole-House Fan",
      "title": "{item_name} ({fan_cfm:,} CFM Ducted Whole-House Fan w/ R-5 Damper)",
      "price_range": "$379 - $1,599",
      "amazon_query": "QuietCool Whole House Fan {fan_cfm} CFM Ducted",
      "vent_note": "1-sentence acoustical duct and ACH cooling note"
    }},
    {{
      "badge": "{sp['whf_required_nfa_sqft']} ft² NFA Ridge & Soffit",
      "title": "Shingle-Over Ridge Vent Roll + 16\"×8\" Aluminum Soffit Vents & Rafter Baffles",
      "price_range": "$79 - $249",
      "amazon_query": "Shingle Over Ridge Vent Roll 16x8 Aluminum Soffit Vent Rafter Baffles",
      "vent_note": "1-sentence 1:750 NFA backpressure prevention note"
    }},
    {{
      "badge": "Solar Roof Attic Fan",
      "title": "Brushless 40W Solar Roof-Mount Attic Exhaust Ventilator w/ Thermostat",
      "price_range": "$169 - $449",
      "amazon_query": "Solar Roof Attic Fan Brushless Thermostat",
      "vent_note": "1-sentence daytime solar heat purge note"
    }},
    {{
      "badge": "R-50 Hatch Tent & Timer",
      "title": "R-50 Zippered Attic Stairs Insulation Cover + Smart Countdown Timer Switch",
      "price_range": "$54 - $129",
      "amazon_query": "Attic Stairs Insulation Cover Tent R50 QuietCool Timer Switch",
      "vent_note": "1-sentence air-sealing and automated night timer note"
    }}
  ],
  "roofer_checklist": [
    "Step 1 regarding Net Free Area (NFA) vs 2x Gross Screened Louver area",
    "Step 2 regarding cracking windows 4-6 inches before operating the fan",
    "Step 3 regarding rafter insulation baffles to keep soffit intake open",
    "Step 4 regarding balancing low soffit intake and high ridge/gable exhaust"
  ],
  "faqs": [
    {{"q": "How much attic venting (NFA) is required for {item_name}?", "a": "Exact 1 sq ft per 750 CFM calculation in sq ft, sq in, and gross screened area."}},
    {{"q": "How many soffit vents and feet of ridge vent do I need for {home_sqft} sq ft?", "a": "Exact 16x8 soffit count and ridge linear feet for both WHF and IRC R806.2."}},
    {{"q": "How fast will {fan_cfm} CFM cool a {home_sqft} sq ft house?", "a": "Exact Air Changes Per Hour (ACH) and minutes per complete air exchange."}}
  ]
}}
"""

    for model_id in get_active_gemini_model(GEMINI_API_KEY):
        for attempt in range(2):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json"
                    }
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=40) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                    parsed = json.loads(raw_text)
                    if "specs" in parsed and "hardware_bundle" in parsed:
                        time.sleep(6)
                        return parsed
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    print(f"[RATE-LIMIT] HTTP 429 on {model_id} (attempt {attempt + 1}). Cooling down 20s...")
                    time.sleep(20)
                else:
                    print(f"[WARN] HTTP {he.code} on {model_id} for '{item_name}': {he}")
                    break
            except Exception as e:
                print(f"[WARN] Gemini ({model_id}) notice for '{item_name}': {e}")
                break

    return det_fallback


def build_attic_html_page(data, slug, mon_cfg):
    attic_name = data.get("attic_name", "Whole-House Fan & Attic Ventilation")
    sp = data.get("specs", {})
    home_sqft = int(safe_float(sp.get("home_floor_sqft", 2000), 2000))
    fan_cfm = int(safe_float(sp.get("recommended_fan_cfm", 5000), 5000))
    ach = round(safe_float(sp.get("air_changes_per_hour", 16.7), 16.7), 1)
    min_ex = round(safe_float(sp.get("minutes_per_air_change", 3.6), 3.6), 1)
    nfa_sqft = round(safe_float(sp.get("whf_required_nfa_sqft", 6.7), 6.7), 1)
    nfa_sqin = int(safe_float(sp.get("whf_required_nfa_sqin", 960), 960))
    gross_sqft = round(safe_float(sp.get("gross_screened_louver_sqft", 13.4), 13.4), 1)
    soffit_cnt = int(safe_float(sp.get("soffit_vents_16x8_count", 9), 9))
    ridge_ft = int(safe_float(sp.get("ridge_vent_linear_ft", 27), 27))
    watts = int(safe_float(sp.get("running_watts", 525), 525))

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "QuietCool+Whole+House+Fan+Solar+Attic+Vent"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{attic_name} CFM & Attic Net Free Area Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "QuietCool Whole House Fan")), mon_cfg)
        bundle_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-sky-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Attic Cooling')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$59+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">🌬️ {item.get('vent_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Home Sq Ft vs Whole-House Fan CFM, Attic NFA & Vent Count Matrix Table
    attic_tiers = [
        ("1,200 Sq Ft Home", "3,000 CFM Fan", "4.0 Sq Ft (576 sq in NFA)", "8.0 Sq Ft Screened", "6 Soffit + 16 ft Ridge"),
        ("1,600 Sq Ft Home", "4,000 CFM Fan", "5.3 Sq Ft (768 sq in NFA)", "10.6 Sq Ft Screened", "7 Soffit + 22 ft Ridge"),
        ("2,000 Sq Ft Home", "5,000 CFM Fan", "6.7 Sq Ft (960 sq in NFA)", "13.4 Sq Ft Screened", "9 Soffit + 27 ft Ridge"),
        ("2,400 Sq Ft Home", "6,000 CFM Fan", "8.0 Sq Ft (1,152 sq in NFA)", "16.0 Sq Ft Screened", "11 Soffit + 32 ft Ridge"),
        ("3,000 Sq Ft Home", "7,500 CFM (Dual Fan)", "10.0 Sq Ft (1,440 sq in NFA)", "20.0 Sq Ft Screened", "13 Soffit + 40 ft Ridge")
    ]
    matrix_rows_html = ""
    for h_lbl, c_lbl, n_lbl, g_lbl, v_lbl in attic_tiers:
        matrix_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40">
          <td class="py-3 px-4 font-bold text-white">{h_lbl}</td>
          <td class="py-3 px-4 font-bold text-sky-400">{c_lbl}</td>
          <td class="py-3 px-4 text-emerald-400 font-semibold">{n_lbl}</td>
          <td class="py-3 px-4 text-slate-300">{g_lbl}</td>
          <td class="py-3 px-4 text-xs text-slate-300">{v_lbl}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("roofer_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-sky-500 rounded cursor-pointer attic-check">
          <span class="text-sm text-slate-200 leading-relaxed"><strong>IRC R806.2 Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', attic_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', attic_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-sky-500 text-slate-950 px-2 py-0.5 rounded font-black">ATTIC</span>FanIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Whole-House Fans & Vents →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-sky-500 text-slate-950 px-3 py-1 rounded-full">{fan_cfm:,} CFM ({ach} ACH / {min_ex}m)</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">Need {nfa_sqft} ft² NFA ({nfa_sqin:,} sq in)</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">{soffit_cnt} Soffit + {ridge_ft}' Ridge | {watts}W</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', attic_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-sky-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>HVI-916 & IRC Section R806.2 Verdict:</strong> {data.get('irc_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE WHOLE-HOUSE FAN CFM, 1:750 ATTIC NFA & SOFFIT/RIDGE CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {attic_name} CFM & Attic Vent NFA Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust your home square footage, climate airflow multiplier (CFM/sq ft), and bug-screen louver restriction to compute exact Whole-House Fan CFM, required 1:750 Attic Net Free Area (NFA), and soffit/ridge vent counts.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="sqftSlider" class="text-slate-300">Conditioned Home & Attic Floor Area (Sq Ft)</label>
              <span class="text-sky-400 font-bold"><span id="sqftVal">{home_sqft:,}</span> sq ft</span>
            </div>
            <input id="sqftSlider" type="range" min="600" max="4500" step="100" value="{home_sqft}" class="w-full accent-sky-500 cursor-pointer">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="climSelect" class="block text-xs font-medium text-slate-400 mb-1">Climate Cooling Multiplier</label>
              <select id="climSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500">
                <option value="2.0">Mild Climate (2.0 CFM/ft² — 15 ACH)</option>
                <option value="2.5" selected>Warm Climate (2.5 CFM/ft² — 18 ACH)</option>
                <option value="3.0">Hot Desert Climate (3.0 CFM/ft² — 22 ACH)</option>
              </select>
            </div>
            <div>
              <label for="screenSelect" class="block text-xs font-medium text-slate-400 mb-1">Vent Bug-Screen Restriction</label>
              <select id="screenSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500">
                <option value="1.5">1/4" Hardware Cloth (1.5x Gross)</option>
                <option value="2.0" selected>1/8" Insect Mesh + Louvers (2.0x Gross)</option>
              </select>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-sky-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-sky-400 font-bold">Required Whole-House Fan</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="cfmOut">{fan_cfm:,}</span> <span class="text-xs font-normal text-slate-400">CFM</span></div>
            <p id="achNoteOut" class="text-xs text-sky-400 font-semibold mt-1">Exchanges Air Every {min_ex} Min</p>
          </div>

          <div class="bg-slate-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">Attic Net Free Area (1:750)</span>
            <div id="nfaOut" class="text-xl sm:text-2xl font-black text-emerald-400 mt-1">{nfa_sqft} ft² ({nfa_sqin:,} in²)</div>
            <p id="ventSplitOut" class="text-xs text-slate-300 font-semibold mt-1">{soffit_cnt} Soffit + {ridge_ft}' Ridge Vent</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-sky-950/40 border border-sky-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="atticAdviceBanner" class="text-sm text-sky-100 font-medium"></div>
        <a id="dynamicAtticBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched Whole-House Fan & Vents on Amazon →
        </a>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Complete {attic_name} Fan, Ridge Vent & Hatch Cover Bundle</h2>
        <span class="text-xs text-slate-400">HVI-916 & California Title 24 Compliant</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">Whole-House Fan CFM, 1:750 Attic Net Free Area (NFA) & Vent Count Chart</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-xs">
              <th class="py-3.5 px-4">Home Floor Area</th>
              <th class="py-3.5 px-4 text-sky-400">Target Fan CFM</th>
              <th class="py-3.5 px-4 text-emerald-400">Net Free Vent Area (NFA)</th>
              <th class="py-3.5 px-4">Gross Screened Cutout</th>
              <th class="py-3.5 px-4">50/50 Soffit + Ridge Split</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">BPI & IRC R806.2 Attic Ventilation, Baffle & Window Safety Checklist</h2>
        <span id="atticBadge" class="text-xs font-bold bg-slate-800 text-sky-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({attic_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} AtticFanIndex. Independent Whole-House Fan & IRC Section R806.2 Ventilation Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const sqftSlider = document.getElementById('sqftSlider');
    const climSelect = document.getElementById('climSelect');
    const screenSelect = document.getElementById('screenSelect');
    const sqftVal = document.getElementById('sqftVal');
    const cfmOut = document.getElementById('cfmOut');
    const achNoteOut = document.getElementById('achNoteOut');
    const nfaOut = document.getElementById('nfaOut');
    const ventSplitOut = document.getElementById('ventSplitOut');
    const atticAdviceBanner = document.getElementById('atticAdviceBanner');
    const dynamicAtticBtn = document.getElementById('dynamicAtticBtn');

    function recalculateAttic() {{
      const sqft = parseInt(sqftSlider.value, 10);
      const cfmPerSqft = parseFloat(climSelect.value);
      const screenMult = parseFloat(screenSelect.value);

      sqftVal.textContent = sqft.toLocaleString();

      const reqCfm = Math.round((sqft * cfmPerSqft) / 50) * 50;
      const volCuFt = sqft * 8.5;
      const ach = ((reqCfm * 60.0) / volCuFt).toFixed(1);
      const minPerEx = (60.0 / parseFloat(ach)).toFixed(1);

      const nfaSqFt = (reqCfm / 750.0).toFixed(1);
      const nfaSqIn = Math.round(parseFloat(nfaSqFt) * 144.0);
      const grossSqFt = (parseFloat(nfaSqFt) * screenMult).toFixed(1);

      const soffitCount = Math.max(6, Math.ceil((nfaSqIn * 0.50) / 56.0));
      const ridgeLinFt = Math.max(12, Math.ceil((nfaSqIn * 0.50) / 18.0));

      cfmOut.textContent = reqCfm.toLocaleString();
      achNoteOut.textContent = `${{ach}} ACH (Every ${{minPerEx}} Min)`;
      nfaOut.textContent = `${{nfaSqFt}} ft² (${{nfaSqIn.toLocaleString()}} in²)`;
      ventSplitOut.textContent = `${{soffitCount}} Soffit + ${{ridgeLinFt}}' Ridge Vent`;

      atticAdviceBanner.innerHTML = `🌬️ <strong>HVI-916 & IRC Spec:</strong> A ${{sqft.toLocaleString()}} sq ft home requires a <strong>${{reqCfm.toLocaleString()}} CFM Ducted Whole-House Fan</strong> paired with <strong>${{nfaSqFt}} sq ft (${{nfaSqIn.toLocaleString()}} sq in) of Net Free Attic Vent Area</strong> (${{grossSqFt}} sq ft gross screened area = ${{soffitCount}}× 16"×8" soffit vents + ${{ridgeLinFt}} ft of ridge vent).`;
      dynamicAtticBtn.href = `https://${{amzDomain}}/s?k=QuietCool+Whole+House+Fan+${{reqCfm}}+CFM+Ridge+Soffit+Vent&tag=${{amzTag}}`;
    }}

    sqftSlider.addEventListener('input', recalculateAttic);
    climSelect.addEventListener('change', recalculateAttic);
    screenSelect.addEventListener('change', recalculateAttic);
    recalculateAttic();

    const checks = document.querySelectorAll('.attic-check');
    const badge = document.getElementById('atticBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "QuietCool+Whole+House+Fan+Solar+Attic+Vent"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-sky-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-sky-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('cfm', 4685):,} CFM ({item.get('sqft', 1900):,} ft²)</span>
            <span class="text-xs text-slate-400">NFA: {item.get('nfa_sqft', 6.2)} ft² ({item.get('nfa_sqin', 900)} in²)</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-sky-400 transition">{item['attic_name']}</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-sky-400">Calculate CFM, NFA & Soffit/Ridge Vents →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AtticFanIndex — Whole-House Fan CFM, Attic Net Free Area (NFA) & IRC R806.2 Calculator (2026)</title>
  <meta name="description" content="Calculate exact whole-house fan CFM, 1:750 attic exhaust Net Free Vent Area (NFA), and IRC R806.2 1:150 / 1:300 soffit and ridge vent counts for QuietCool, AirScape, CentricAir, and solar roof ventilators.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="AtticFanIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-sky-500 text-slate-950 px-2 py-0.5 rounded font-black">ATTIC</span>FanIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Whole-House Fans & Vents →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Whole-House Fan CFM, Attic Net Free Area & Vent Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select your whole-house fan model or home square footage below to calculate 15–22 ACH cooling airflow, 1:750 Net Free Vent Area (NFA), and IRC R806.2 soffit/ridge vent balance.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search fan model or home size (e.g. QuietCool CL-4700, CL-5400, AirScape, 2000 Sq Ft Home, Soffit Vents, Solar Fan...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-sky-500">
      </div>
    </div>

    <div id="atticGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} AtticFanIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('atticGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>AtticFanIndex Whole-House Fan & Attic Ventilation Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Whole-House Fan CFM, Attic Net Free Area (NFA) & IRC R806.2 Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    """Multi-Endpoint Search Engine Pinger (IndexNow Global + Bing + Google WebSub)."""
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    for idx_endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]:
        try:
            req = urllib.request.Request(
                idx_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[INDEXNOW] Pushed {len(new_urls)} URLs to {idx_endpoint} (HTTP {resp.status})")
                break
        except Exception as e:
            print(f"[WARN] IndexNow ({idx_endpoint}) notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published if "slug" in item}

    candidates = []
    if CUSTOM_ATTIC:
        candidates.append((CUSTOM_ATTIC.strip(), 2000, 5000, 525, 9, "Ducted R5 Damper Box"))
    candidates.extend(SEED_ATTICS)
    candidates.extend(discover_google_attic_queries(published_slugs))

    new_urls = []
    count = 0

    for attic_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        a_name = attic_tuple[0]
        slug = slugify(f"{a_name}-whole-house-fan-nfa-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating whole-house fan CFM & attic NFA calculator for: {a_name}...")
        try:
            data = generate_attic_data(attic_tuple)
            build_attic_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "attic_name": data.get("attic_name", a_name),
                "slug": slug,
                "title": data.get("seo_title", f"{a_name} Whole-House Fan Calculator"),
                "description": data.get("meta_description", ""),
                "sqft": int(safe_float(sp.get("home_floor_sqft", attic_tuple[1]), attic_tuple[1])),
                "cfm": int(safe_float(sp.get("recommended_fan_cfm", attic_tuple[2]), attic_tuple[2])),
                "nfa_sqft": round(safe_float(sp.get("whf_required_nfa_sqft", 6.7), 6.7), 1),
                "nfa_sqin": int(safe_float(sp.get("whf_required_nfa_sqin", 960), 960)),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            if count < PAGES_PER_RUN:
                time.sleep(15)
        except Exception as e:
            print(f"[ERROR] Failed building {a_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new whole-house fan & attic NFA calculator pages.")


if __name__ == "__main__":
    main()
