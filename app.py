# app.py — fixed: skill use identical to glroy.py

# ---- equip.py MUST import first (same folder as this script) ----
import os
import sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

try:
    import equip
except ImportError as _e:
    print(f"  X equip.py import nahi hua: {_e}")
    print(f"    equip.py ko is script wale folder me rakho: {_BASE_DIR}")
    print("    aur httpx install karo:  pip install httpx")
    sys.exit(1)

import re
import ssl
import json
import time
import uuid
import hmac
import string
import base64
import random
import hashlib
import asyncio
import socket
import struct
import threading
import traceback
import math
from datetime import datetime

import aiohttp
import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

import MajorloginReqBuild_pb2
import PorTs_pb2
from MajorloginResp_pb2 import MajorLoginRes as MajorLoginResponse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from protobuf_decoder.protobuf_decoder import Parser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False
    Parser = None

REGION_LIST = ["IND", "ID", "TH", "ME", "EUROPE", "VN", "BD", "PK", "TW", "RU", "NA", "SAC", "BR", "SG", "US"]

REGION_LANG = {
    "ME": "ar", "IND": "hi", "ID": "id", "VN": "vi", "TH": "th",
    "BD": "bn", "PK": "ur", "TW": "zh", "EUROPE": "fr", "RU": "ru",
    "NA": "na", "SAC": "es", "BR": "pt", "SG": "ms", "US": "us",
}

REGION_GROUP = {
    "IND": "IND",
    "BR": "AMERICA", "US": "AMERICA", "NA": "AMERICA", "SAC": "AMERICA",
    "ID": "OTHERS", "TH": "OTHERS", "ME": "OTHERS", "EUROPE": "OTHERS",
    "VN": "OTHERS", "BD": "OTHERS", "PK": "OTHERS", "TW": "OTHERS",
    "RU": "OTHERS", "SG": "OTHERS",
}

REGION_URLS = {
    "IND": {"server": "https://loginbp.ppmainecoonghj.com/", "client": "https://client.ind.freefiremobile.com/"},
    "AMERICA": {"server": "https://loginbp.ppmainecoonghj.com/", "client": "https://client.us.freefiremobile.com/"},
    "OTHERS": {"server": "https://loginbp.ppmainecoonghj.com/", "client": "https://clientbp.ggpolarbear.com/"},
}

APP_ID = 100067
CLIENT_TYPE = 2
SOURCE = 2
SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"


USER_AGENT_MSDK = "GarenaMSDK/4.0.44(V2538 ;Android 16;en;US;app 1.132.1 2019121227;)"
USER_AGENT_UNITY = "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"
USER_AGENT_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

_KEYSTREAM = bytes([
    0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37,
    0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30,
])

SESSION_HASH = "1ac4b80ecf0478a44203bf8fac6120f5"

ACCOUNTS_FILE = os.environ.get("RBC_ACCOUNTS_FILE", "accounts.json")
UDP_LOG_FILE = "udp_logs.txt"

REGION = "IND"
LANG_CODE = "hi"

SETTLE_AFTER_ALL_JOIN = 1.5
SQUAD_PLAYERS = 4
SQUAD_TIMEOUT = 600
# main.py "CS + BR" mode: run exactly ONE match, wait for it to finish, then exit
ONE_MATCH = os.environ.get("RBC_ONE_MATCH") == "1"
ONE_MATCH_WAIT = 800
try:
    START_CYCLE = int(os.environ.get("RBC_START_CYCLE", "0") or 0)
except ValueError:
    START_CYCLE = 0
MODE_LABEL = "BR"
REGION_ROTATION_LIST   = ["IND", "ID", "TH", "ME", "VN", "BD", "PK", "SG"]
REGION_ROTATE_EVERY_N  = 2
NEW_MATCH_DELAY        = 1.0
START_REPEAT_INTERVAL  = 1.5
JWT_CACHE_FILE         = "jwt.json"
JWT_TTL                = 7 * 3600

_PLAY_VERSION = "1.132.13"
_OB_VERSION = "OB55"

HARDCODED_CONFIG = {
    "latest_release_version": "OB55",
    "remote_version": "1.132.13",
    "cdn_url": "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/",
    "abhotupdate_cdn_url": "https://core-bs.ggpolarbear.com/live/ABHotUpdates/",
    "client_ip": "103.200.36.133",
    "vercfg_sign": "1.f46ddde8bb35d74e",
    "region": REGION,
    "lang": LANG_CODE,
    "country_code": REGION,
    "server_url": "https://loginbp.ppmainecoonghj.com/",
    "client_url": "https://client.ind.freefiremobile.com/",
}

_print_lock = threading.Lock()
_file_lock = threading.Lock()
_gate_lock = threading.Lock()
_dd_lock = threading.Lock()
_count_lock = threading.Lock()

_last_register_time = 0.0
_success_count = 0
_failure_count = 0

_dd_session_cookie = None
_dd_expires_at = 0.0

_log_lock = threading.Lock()

MOVE_HZ = 5.0
MOVE_INTERVAL = 1.0 / MOVE_HZ
DASH_VEL = 501
STEP_PER_TICK = DASH_VEL / (MOVE_HZ * 0.1)
STICK_DIST = 150.0
CHASE_Y_LERP = 0.5
POSE_STANDING = 0
POSE_DASHING = 2
CMD_PLAYER_STATE_UPLOAD = 2001
CHAT_FOLLOW_TRIGGERS = (1, 2)

# ---- SKILL USE ----
SKILL_ENABLED = True
SKILL_EVERY = 1.0
SKILL_COOLDOWN_SEC = 60.0
SKILL_COOLDOWN_RESET_ON_ROUND = True
ACTIVE_SKILL_ID = 5506
SKILL_MAX_DIST = 70000.0
DRONE_TARGET_MAX = 70000.0
SKILL_NO_REPLY_SEC = 2.5
SKILL_RETRY_FAIL = 1.0
KNOWN_ACTIVE_SKILLS = (5506,)

CMD_ACTIVE_SKILL = 248
CMD_ACTIVE_SKILL_STATE = 250
CMD_PRESET_INFO = 1658
CMD_USE_SKILL_FAIL = 823
CMD_AUTOFLIGHTBOMB = 538
CMD_AUTOFLIGHTBOMB_STATE = 542
CMD_PUSH_AUTOFLIGHT_ENEMY = 543
CMD_DRONE_HIT = 168

SKILL_GOOD = {"id": None, "variant": None}

STUCK_TRIGGER = 2.0
SLOW_DURATION = 8.0
SLOW_HZ = 1.5
SLOW_INTERVAL = 1.0 / SLOW_HZ

BLOCKED_TICKS = 4
SIDESTEP_DIST = 180.0
SIDESTEP_HOLD = 0.8

REGROUP_RADIUS = 700.0
REGROUP_WEIGHT = 0.6

JHUND_MAX_AGE = 10.0
JHUND_DASH_DIST = 6000.0
JHUND_SLOT_MIN = 120.0
JHUND_SLOT_MAX = 260.0
LEADER_DEADZONE = 220.0
WANDER_MIN = 500.0
WANDER_MAX = 1400.0
STRAFE_FRAC = 0.45
SEED_POS_AFTER = 4.0

# ---- NEW MOVEMENT (server-authoritative base + client offset, zigzag, pauses, safezone aware) ----
# "new" = new movement, "old" = the original _BotBrain movement (still fully in the file). Change here or via env RBC_MOVEMENT.
MOVEMENT_MODE = os.environ.get("RBC_MOVEMENT", "new").strip().lower()
NEW_SEND_HZ = 15.0
NEW_WALK_SPEED = 1600.0
NEW_STEP_PER_TICK = NEW_WALK_SPEED / NEW_SEND_HZ
NEW_CHASE_MIN_DIST = 100.0
NEW_TARGET_MIN = 50.0
NEW_TARGET_MAX = 100000.0
NEW_ZONE_SCALE = 1000.0
NEW_USE_ZONE = True
NEW_PAUSE_CHANCE = 0.05
NEW_JUMP_CHANCE = 0.03
NEW_SLIDE_CHANCE = 0.01
NEW_MSG_KEY = 0x6B


def _log(line):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with _log_lock:
        print(f"[{ts}] {line}", flush=True)
        try:
            with open(UDP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {line}\n")
        except Exception:
            pass


def _tag(i, n):
    return f"{i:>2}/{n}"


def enc_aes(data):
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(data, 16))


def dec_aes(data):
    try:
        return unpad(AES.new(KEY, AES.MODE_CBC, IV).decrypt(data), 16)
    except ValueError:
        return AES.new(KEY, AES.MODE_CBC, IV).decrypt(data)


def sign_body(body):
    return hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()


def encode_open_id(open_id):
    return bytes(ord(open_id[i]) ^ _KEYSTREAM[i % len(_KEYSTREAM)] for i in range(len(open_id)))


def decode_jwt_payload(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        p2 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(p2))
    except Exception:
        return {}


def enc_varint(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def read_varint(data, off):
    v, s = 0, 0
    while True:
        b = data[off]
        off += 1
        v |= (b & 0x7F) << s
        if not (b & 0x80):
            return v, off
        s += 7


def ptag(f, wt):
    return enc_varint((f << 3) | wt)


def f_vint(f, n):
    return ptag(f, 0) + enc_varint(n)


def f_bytes(f, b):
    return ptag(f, 2) + enc_varint(len(b)) + b


def f_str(f, s):
    b = s.encode("utf-8")
    return ptag(f, 2) + enc_varint(len(b)) + b


def parse_proto(data):
    fields = {}
    i = 0
    while i < len(data):
        try:
            key, i = read_varint(data, i)
        except Exception:
            break
        fn, wt = key >> 3, key & 7
        try:
            if wt == 0:
                v, i = read_varint(data, i)
                fields.setdefault(fn, []).append(("varint", v))
            elif wt == 1:
                v = int.from_bytes(data[i:i+8], "little")
                i += 8
                fields.setdefault(fn, []).append(("u64", v))
            elif wt == 2:
                ln, i = read_varint(data, i)
                raw = data[i:i+ln]
                i += ln
                s_ok = False
                try:
                    s = raw.decode("utf-8")
                    if s.isprintable():
                        fields.setdefault(fn, []).append(("string", s))
                        s_ok = True
                except UnicodeDecodeError:
                    pass
                if not s_ok:
                    fields.setdefault(fn, []).append(("bytes", raw.hex()))
            elif wt == 5:
                v = int.from_bytes(data[i:i+4], "little")
                i += 4
                fields.setdefault(fn, []).append(("u32", v))
            else:
                break
        except Exception:
            break
    return fields


def first_value(fields, field_num, want_kind=None):
    for kind, v in fields.get(field_num, []):
        if want_kind is None or kind == want_kind:
            return v
    return None


def _load_json_dict(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_accounts():
    """accounts.json se accounts load karta hai.

    Format (list):
      [
        {"uid": "123456789", "pass": "PASSWORD"},
        {"uid": "123456790", "pass": "PASSWORD"},
        ...
      ]
    Optional keys: "name", "region" (default IND).
    Dict format {"uid": "pass", ...} bhi chalega.
    """
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"  X {ACCOUNTS_FILE} nahi mila")
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  X {ACCOUNTS_FILE} read error: {e}")
        return []

    if isinstance(data, dict):
        data = [{"uid": k, "pass": v} for k, v in data.items()]
    if not isinstance(data, list):
        print(f"  X {ACCOUNTS_FILE} list hona chahiye")
        return []

    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("uid", "")).strip()
        pwd = str(item.get("pass") or item.get("password") or "").strip()
        if not uid or not pwd:
            continue
        out.append({
            "uid": uid,
            "pass": pwd,
            "name": item.get("name") or uid,
            "region": (item.get("region") or REGION).upper(),
            "open_id": None,
            "access_token": None,
            "jwt": "",
            "ingame_id": 0,
            "game_url": "",
        })
    return out


def _normalize_uid(uid):
    s = str(uid).strip()
    if s.isdigit():
        return int(s)
    return s


# =====================================================================
# SKILL EQUIPPER (port of idc.py)
# =====================================================================


def build_major_login_pb2(open_id, access_token, platform, client_version, region="IND",
                          country="IND", lang="en"):
    p = MajorloginReqBuild_pb2.MajorLogin()
    p.open_id = open_id
    p.access_token = access_token
    p.client_version = client_version
    p.event_time = str(int(time.time()))
    p.game_name = "free fire"
    p.platform_id = 1
    p.system_software = "Android OS 16 / API-36 (BP4A.251205.006/M066BXXS8CZI1)"
    p.system_hardware = "Handheld"
    p.telecom_operator = "WIFI"
    p.network_type = "WIFI"
    p.screen_width = 1600
    p.screen_height = 720
    p.screen_dpi = "300"
    p.processor_details = "ARM64 FP ASIMD AES | 2400 | 8"
    p.memory = 3507
    p.gpu_renderer = "Mali-G57 MC2"
    p.gpu_version = "OpenGL ES 3.2 v1.r38p1"
    p.unique_device_id = "Google|6acc6a56-b955-42d6-9920-7c3faa8992e3"
    p.client_ip = "122.174.21.30"
    p.language = lang
    p.open_id_type = "4"
    p.device_type = "Handheld"
    p.device_model = "samsung SM-M066B"
    p.country_code = country
    p.platform_sdk_id = 1
    p.network_operator_a = "WIFI"
    p.network_type_a = "WIFI"
    p.client_using_version = SESSION_HASH
    p.external_storage_total = 47195
    p.external_storage_available = 19418
    p.internal_storage_total = 5135
    p.internal_storage_available = 5135
    p.game_disk_storage_available = 19546
    p.game_disk_storage_total = 47195
    p.external_sdcard_avail_storage = 19546
    p.external_sdcard_total_storage = 47195
    p.field_70 = 4
    p.login_by = 3
    p.library_path = "/data/app/~~bsxEK2UVui2u9YoL_QKi_w==/com.garena.game.ffi-p7Uh_JDc-8hCjRgLvsaRqg==/lib/arm64"
    p.reg_avatar = 3
    p.library_token = ("dd9d4c174e0472d34b7fd34bd5924bc9|"
                       "/data/app/~~bsxEK2UVui2u9YoL_QKi_w==/com.garena.game.ffi-p7Uh_JDc-8hCjRgLvsaRqg==/base.apk")
    p.channel_type = 3
    p.cpu_type = 2
    p.cpu_architecture = "64"
    p.client_version_code = "2019121269"
    p.field_85 = 3
    p.graphics_api = "OpenGLES2"
    p.supported_astc_bitset = 8191
    p.login_open_id_type = 4
    p.loading_time = 13070
    p.release_channel = "android"
    p.extra_info = ("KqsHT3kf8XDT3vqFEnlSSQFMl5SRiWL2SxIxcx47LozWRI7AqvwWJ9eJ/"
                    "fXX0amawG9xA6DLOyWSJCij9Fp7M5o3bzp7/MjO1jDqX8PwDD8qq5vO")
    p.android_engine_init_flag = 111107
    p.field_96 = json.dumps({"cur_rate": [90, 60], "support_etc2": False},
                            separators=(",", ":"))
    p.if_push = 1
    p.is_vpn = 1
    p.origin_platform_type = "4"
    p.primary_platform_type = "4"
    p.field_102 = b""
    p.field_104 = 80395
    p.field_105 = 1
    p.field_106 = ("https://dl-tata.freefireind.in/live/ABHotUpdates/"
                   "|https://core-tata.freefireind.in/live/ABHotUpdates/"
                   "|dff941d41e6e3a9e76f05ed71fdc8d87")
    p.field_107 = "1.6168622e0868ddbd"
    return enc_aes(p.SerializeToString())


def build_get_login_data_pb2(open_id, access_token, platform, client_version, jwt,
                             server_url, region="IND", country="IND", lang="en"):
    p = MajorloginReqBuild_pb2.MajorLogin()
    p.open_id = open_id
    p.access_token = access_token
    p.client_version = client_version
    p.event_time = str(int(time.time()))
    p.game_name = "free fire"
    p.platform_id = 1
    p.system_software = "Android OS 16 / API-36 (BP4A.251205.006/M066BXXS8CZI1)"
    p.system_hardware = "Handheld"
    p.telecom_operator = "WIFI"
    p.network_type = "WIFI"
    p.screen_width = 1600
    p.screen_height = 720
    p.screen_dpi = "300"
    p.processor_details = "ARM64 FP ASIMD AES | 2400 | 8"
    p.memory = 3507
    p.gpu_renderer = "Mali-G57 MC2"
    p.gpu_version = "OpenGL ES 3.2 v1.r38p1"
    p.unique_device_id = "Google|6acc6a56-b955-42d6-9920-7c3faa8992e3"
    p.client_ip = "122.174.21.30"
    p.language = lang
    p.open_id_type = "4"
    p.device_type = "Handheld"
    p.device_model = "samsung SM-M066B"
    p.country_code = country
    p.platform_sdk_id = 1
    p.network_operator_a = "WIFI"
    p.network_type_a = "WIFI"
    p.client_using_version = SESSION_HASH
    p.external_storage_total = 47195
    p.external_storage_available = 19418
    p.internal_storage_total = 5135
    p.internal_storage_available = 5135
    p.game_disk_storage_available = 19546
    p.game_disk_storage_total = 47195
    p.external_sdcard_avail_storage = 19546
    p.external_sdcard_total_storage = 47195
    p.field_70 = 4
    p.login_by = 3
    p.library_path = "/data/app/~~bsxEK2UVui2u9YoL_QKi_w==/com.garena.game.ffi-p7Uh_JDc-8hCjRgLvsaRqg==/lib/arm64"
    p.reg_avatar = 3
    p.library_token = ("dd9d4c174e0472d34b7fd34bd5924bc9|"
                       "/data/app/~~bsxEK2UVui2u9YoL_QKi_w==/com.garena.game.ffi-p7Uh_JDc-8hCjRgLvsaRqg==/base.apk")
    p.channel_type = 3
    p.cpu_type = 2
    p.cpu_architecture = "64"
    p.client_version_code = "2019121269"
    p.field_85 = 3
    p.graphics_api = "OpenGLES2"
    p.supported_astc_bitset = 8191
    p.login_open_id_type = 4
    p.loading_time = 13070
    p.release_channel = "android"
    p.extra_info = ("KqsHT3kf8XDT3vqFEnlSSQFMl5SRiWL2SxIxcx47LozWRI7AqvwWJ9eJ/"
                    "fXX0amawG9xA6DLOyWSJCij9Fp7M5o3bzp7/MjO1jDqX8PwDD8qq5vO")
    p.android_engine_init_flag = 111107
    p.field_96 = json.dumps({"cur_rate": [90, 60], "support_etc2": False},
                            separators=(",", ":"))
    p.if_push = 1
    p.is_vpn = 1
    p.origin_platform_type = "4"
    p.primary_platform_type = "4"
    p.field_102 = b""
    p.field_104 = 80395
    p.field_105 = 1
    p.field_106 = ("https://dl-tata.freefireind.in/live/ABHotUpdates/"
                   "|https://core-tata.freefireind.in/live/ABHotUpdates/"
                   "|dff941d41e6e3a9e76f05ed71fdc8d87")
    p.field_107 = "1.6168622e0868ddbd"
    return enc_aes(p.SerializeToString())


def major_login(tag, open_id, access_token, cfg, platform, region=None):
    url = cfg["server_url"].rstrip("/") + "/MajorLogin"
    plain = build_major_login_pb2(open_id, access_token, platform,
                                  cfg["remote_version"], cfg.get("region", "IND"),
                                  cfg.get("country_code", "IN"), cfg.get("lang", "en"))
    headers = {
        "User-Agent": USER_AGENT_UNITY,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "X-GA-SV": str(int(time.time())),
        "ReleaseVersion": cfg["latest_release_version"],
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = requests.post(url, data=plain, headers=headers, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"MajorLogin HTTP {r.status_code}")
    body = r.content

    def _try(blob):
        if len(blob) < 10:
            return None
        try:
            m = MajorLoginResponse()
            m.ParseFromString(blob)
            if getattr(m, "token", "") and getattr(m, "account_id", 0):
                return m
        except Exception:
            return None

    cand = _try(body)
    if not cand and len(body) > 64:
        cand = _try(body[64:])
    if not cand:
        for off in range(1, min(128, len(body))):
            cand = _try(body[off:])
            if cand:
                break
    if not cand:
        raise RuntimeError("MajorLogin parse failed")
    return {
        "account_id": cand.account_id,
        "jwt": cand.token,
        "game_url": getattr(cand, "server_url", "") or cfg["server_url"],
        "region": getattr(cand, "lock_region", "") or cfg.get("region", "IND"),
        "aes_key": getattr(cand, "ak", b""),
        "aes_iv": getattr(cand, "aiv", b""),
        "server_time": getattr(cand, "kts", 0),
    }


def get_login_data(tag, open_id, access_token, cfg, platform, jwt):
    url = cfg["client_url"].rstrip("/") + "/GetLoginData"
    plain = build_get_login_data_pb2(open_id, access_token, platform,
                                     cfg["remote_version"], jwt,
                                     cfg["client_url"], cfg.get("region", "IND"),
                                     cfg.get("country_code", "IN"), cfg.get("lang", "en"))
    headers = {
        "User-Agent": USER_AGENT_UNITY,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": f"Bearer {jwt}",
        "X-GA": "v1 1",
        "X-GA-SV": str(int(time.time())),
        "ReleaseVersion": cfg["latest_release_version"],
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = requests.post(url, data=plain, headers=headers, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"GetLoginData HTTP {r.status_code}")
    body = r.content

    def _try(blob):
        try:
            m = PorTs_pb2.GetLoginData()
            m.ParseFromString(blob)
            if getattr(m, "AccountUID", 0) or getattr(m, "Online_IP_Port", ""):
                return m
        except Exception:
            return None

    cand = _try(body)
    if not cand and len(body) > 64:
        cand = _try(body[64:])
    if not cand:
        for off in range(1, min(128, len(body))):
            cand = _try(body[off:])
            if cand:
                break
    if not cand:
        raise RuntimeError("GetLoginData parse failed")
    return {
        "account_id": getattr(cand, "AccountUID", 0),
        "region": getattr(cand, "Region", "") or cfg.get("region", "IND"),
        "nickname": getattr(cand, "Nickname", ""),
        "game_server": getattr(cand, "Online_IP_Port", ""),
        "chat_server": getattr(cand, "Chat_IP_Port", ""),
        "event_url": getattr(cand, "Event_URL", ""),
    }


def build_region_cfg(region):
    region = region.upper()
    grp = REGION_GROUP.get(region, "OTHERS")
    cfg = dict(HARDCODED_CONFIG)
    cfg["region"] = region
    cfg["lang"] = REGION_LANG.get(region, "en")
    cfg["country_code"] = region
    cfg["server_url"] = REGION_URLS[grp]["server"]
    cfg["client_url"] = REGION_URLS[grp]["client"]
    return cfg


async def EnC_Vr(N):
    if N < 0:
        return b''
    H = []
    while True:
        BesTo = N & 0x7F
        N >>= 7
        if N:
            BesTo |= 0x80
        H.append(BesTo)
        if not N:
            break
    return bytes(H)


async def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return await EnC_Vr(field_header) + await EnC_Vr(value)


async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return await EnC_Vr(field_header) + await EnC_Vr(len(encoded_value)) + encoded_value


async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = await CrEaTe_ProTo(item)
                    packet.extend(await CrEaTe_LenGTh(field, nested))
                elif isinstance(item, int):
                    packet.extend(await CrEaTe_VarianT(field, item))
                elif isinstance(item, (str, bytes)):
                    packet.extend(await CrEaTe_LenGTh(field, item))
        elif isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet


def _to_bytes(v):
    if isinstance(v, bytes):
        return v
    if isinstance(v, str):
        try:
            return bytes.fromhex(v)
        except ValueError:
            return v.encode()
    if v is None:
        raise ValueError("cannot convert None")
    return bytes(v)


AUTH_AES_KEY = bytes([0x19, 0x47, 0xB9, 0x74, 0xD9, 0x73, 0xF3, 0x7F,
                      0x42, 0x06, 0x01, 0x38, 0x42, 0x00, 0x10, 0x30])
AUTH_AES_IV = bytes([0x28, 0x7F, 0xCA, 0x7A, 0xF9, 0x67, 0xF3, 0x7A,
                     0x65, 0x02, 0x01, 0x10, 0x40, 0x40, 0x00, 0x30])
AUTH_CMD = 0x65


def _auth_region_byte(region):
    reg = str(region or "IND").upper()
    if reg == "IND":
        return 0x14
    if reg == "BD":
        return 0x19
    if reg == "ME":
        return 0x15
    return 0x15


async def build_auth_datagram(token, account_id, region=REGION):
    payload = token.encode("utf-8") if isinstance(token, str) else token
    p = 16 - (len(payload) % 16)
    data = AES.new(AUTH_AES_KEY, AES.MODE_CBC, AUTH_AES_IV).encrypt(
        payload + bytes([p]) * p)
    out = bytearray()
    out.append(AUTH_CMD & 0xFF)
    out.append(_auth_region_byte(region) & 0xFF)
    out += struct.pack(">Q", int(account_id) & 0xFFFFFFFFFFFFFFFF)
    out += struct.pack(">I", int(time.time()) & 0xFFFFFFFF)
    out += struct.pack(">i", len(data))
    out += data
    return bytes(out)


async def build_auth_packet(account_id, token, server_time, key, iv, region=REGION, typ="OnLine"):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(token.encode(), 16)).hex()
    enc_len = f"{len(enc) // 2:08x}"
    reg = str(region).upper()
    if reg == "BD":
        pre_on, pre_chat = "7119", "9219"
    elif reg == "IND":
        pre_on, pre_chat = "7114", "9214"
    else:
        pre_on, pre_chat = "7115", "9215"
    if typ == "OnLine":
        return bytes.fromhex(pre_on + uid_hex + ts_hex + "00000000" + enc_len + enc)
    return bytes.fromhex(pre_chat + uid_hex + ts_hex + enc_len + enc)


async def send_keep_alive(region=REGION):
    reg = str(region).upper()
    return bytes.fromhex("0214" if reg == "IND" else ("0219" if reg == "BD" else "0215"))


CRC7_TABLE = bytes([
    0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,
    81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,
    76,69,43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,
    64,73,82,91,44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,
    46,17,24,3,10,86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,
    93,84,107,98,121,112,7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,
    9,0,27,18,45,36,63,54,88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,
    47,115,122,97,104,87,94,69,76,59,50,41,32,31,22,13,4,106,99,120,113,78,
    71,92,85,34,43,48,57,6,15,20,29,37,44,55,62,1,8,19,26,109,100,127,118,73,
    64,91,82,60,53,46,39,24,17,10,3,116,125,102,111,80,89,66,75,23,30,5,12,
    51,58,33,40,95,86,77,68,123,114,105,96,14,7,28,21,42,35,56,49,70,79,84,
    93,98,107,112,121,
])

_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0: 1, 1: 2, 2: 2, 3: 1, 4: 2}
_FIELD_NAMES = {0: "sendOption", 1: "cmd", 2: "orderId", 3: "flags", 4: "length"}

HDR_RELIABLE = 10
UDP_HEAD_AND_ENCRY_SIZE = 40
MTU_LIMIT = 1300
_SALT_LEN, _ZERO_LEN = 2, 7


def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
    except Exception:
        pass


async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf:
        c = CRC7_TABLE[((2 * (c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F


async def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^ ((v1 + s) & 0xFFFFFFFF) ^ (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^ ((v0 + s) & 0xFFFFFFFF) ^ (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1


async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^ ((v0 + s) & 0xFFFFFFFF) ^ (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^ ((v1 + s) & 0xFFFFFFFF) ^ (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1


async def tea_cbc_encrypt(padded, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(padded))
    prev_cipher = bytearray(8)
    prev_intermediate = bytearray(8)
    for i in range(0, len(padded), 8):
        xored = bytearray(8)
        for j in range(8):
            xored[j] = padded[i + j] ^ prev_cipher[j]
        e0, e1 = await tea_enc(struct.unpack_from("<I", xored, 0)[0],
                               struct.unpack_from("<I", xored, 4)[0], k0, k1, k2, k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0)
        struct.pack_into("<I", enc, 4, e1)
        for j in range(8):
            out[i + j] = enc[j] ^ prev_intermediate[j]
        prev_cipher[:] = out[i:i + 8]
        prev_intermediate[:] = xored
        if i % 64 == 0:
            await asyncio.sleep(0)
    return bytes(out)


async def tea_cbc_decrypt(body, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(body))
    prev_intermediate = bytearray(8)
    prev_cipher = bytearray(8)
    xored = bytearray(8)
    dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8):
            xored[j] = body[i + j] ^ prev_intermediate[j]
        d0, d1 = await tea_dec(struct.unpack_from("<I", xored, 0)[0],
                               struct.unpack_from("<I", xored, 4)[0], k0, k1, k2, k3)
        struct.pack_into("<I", dec, 0, d0)
        struct.pack_into("<I", dec, 4, d1)
        for j in range(8):
            out[i + j] = dec[j] ^ prev_cipher[j]
        prev_cipher[:] = body[i:i + 8]
        prev_intermediate[:] = dec
        if i % 64 == 0:
            await asyncio.sleep(0)
    return bytes(out)


async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7


async def oicq_unpad(padded):
    if not padded or len(padded) < 8:
        return None
    if not all(padded[-1 - i] == 0 for i in range(7)):
        return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len
    e = len(padded) - 7
    return padded[s:e] if s < e else b""


async def encode_header(layout, so, cmd, oid, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        value = {0: so, 1: cmd, 2: oid, 3: flags, 4: length}[code]
        if _FIELD_SIZES[code] == 1:
            out.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF)
            out.append((v >> 8) & 0xFF)
    return bytes(out)


async def layouts_from_mask(mask):
    s = str(mask).strip()
    try:
        ru = [int(c) for c in s]
    except ValueError:
        ru = [0, 1, 2, 3, 4]
    if sorted(ru) != [0, 1, 2, 3, 4]:
        ru = [0, 1, 2, 3, 4]
    return ru, [c for c in ru if c != 2]


async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        value = {0: so, 1: cmd, 2: oid, 3: flags, 4: len(body)}[code]
        if _FIELD_SIZES[code] == 1:
            hdr.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF)
            hdr.append((v >> 8) & 0xFF)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)


async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")[:25]
    content = len(data).to_bytes(4, "little") + data + b"\x00" * 9
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    layout = [int(c) for c in str(layout).strip()]
    enc_body = await tea_cbc_encrypt(await build_padded(content), key)
    header_bytes = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    packet = bytearray([0x63, 0x00]) + header_bytes + enc_body
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet).hex()


def _put_varint(out, v):
    v = int(v)
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)


def _put_zigvarint(out, v):
    z = (int(v) << 1) ^ (int(v) >> 63)
    _put_varint(out, z & 0xFFFFFFFFFFFFFFFF)


def _put_string(out, s):
    raw = s.encode("utf-8") if isinstance(s, str) else s
    _put_zigvarint(out, len(raw))
    out += raw


def _rd_varint(b, p):
    v = i = 0
    while True:
        c = b[p + i]
        v |= (c & 0x7F) << (7 * i)
        i += 1
        if not c & 0x80:
            return v, p + i


def _zag(v):
    return (v >> 1) ^ -(v & 1)


def _tea_encrypt_len(n):
    t = 1 + _SALT_LEN + n + _ZERO_LEN
    r = t % 8
    return t + (8 - r if r else 0)


def _dg_size(token_len, reliable=True):
    zv = bytearray()
    _put_zigvarint(zv, token_len)
    body = len(zv) + token_len
    return (HDR_RELIABLE if reliable else 8) + _tea_encrypt_len(body)


def split_token_bytes(token_bytes):
    n = len(token_bytes)
    raw = int(n * 0.85)
    p1 = raw - (raw % 40)
    while UDP_HEAD_AND_ENCRY_SIZE + _dg_size(p1) > MTU_LIMIT and p1 > 40:
        p1 -= 40
    return token_bytes[:p1], token_bytes[p1:]


def build_join_info_head(account_id, game_mode=15, match_mode=1, map_id=1,
                         country="IN", client_version="1.132.16",
                         client_version_code="2019121229",
                         client_url=("csoversea.stronghold.freefiremobile.com;"
                                     "0.0.0.0;34.126.76.45;34.87.177.14;"
                                     "34.87.170.230;35.185.183.57"),
                         room_id=0, match_id=0,
                         drift_bottle_owner_id=0, drift_bottle_owner_name="",
                         enable_antihack_tick=1, friend_count=0,
                         client_ip="", client_fingerprint="",
                         session_tag=0, is_emulator=0):
    room = int(match_id or room_id)
    b = bytearray()
    _put_varint(b, int(account_id))
    _put_varint(b, room)
    b.append(1)
    b.append(int(game_mode) & 0xFF)
    _put_varint(b, room)
    b.append(int(map_id) & 0xFF)
    b.append(0)
    _put_varint(b, 0)
    _put_varint(b, 0)
    b.append(0)
    b.append(int(is_emulator) & 0xFF)
    b.append(0)
    b.append(1)
    b.append(2)
    b.append(3)
    b.append(int(enable_antihack_tick) & 0xFF)
    b.append(1)
    _put_string(b, country)
    _put_varint(b, 0)
    b.append(1)
    b.append(3)
    b.append(0)
    b.append(3)
    b.append(1)
    b.append(0)
    b.append(4)
    _put_string(b, client_version)
    _put_string(b, client_version_code)
    _put_string(b, client_url)
    b.append(0)
    b.append(0)
    _put_varint(b, int(friend_count))
    b.append(0)
    _put_varint(b, int(drift_bottle_owner_id))
    _put_string(b, drift_bottle_owner_name or "")
    b.append(1)
    _put_string(b, "")
    _put_string(b, "")
    b.append(0)
    _put_varint(b, 0)
    _put_varint(b, 0)
    b.append(0)
    b.append(0)
    b.append(0)
    _put_varint(b, 0)
    _put_string(b, "")
    _put_varint(b, 0)
    b.append(0)
    b.append(1)
    b.append(0)
    b.append(0)
    _put_varint(b, 0)
    _put_varint(b, 0)
    b.append(0)
    b.append(1)
    _put_string(b, "")
    _put_varint(b, 0)
    b.append(0)
    b.append(0)
    b.append(0)
    b.append(int(match_mode) & 0xFF)
    b.append(0)
    _put_varint(b, int(session_tag))
    b.append(2)
    b.append(0)
    _put_string(b, client_ip or "")
    _put_string(b, client_fingerprint or "")
    return bytes(b)


def build_join_post_body(account_id, token_part2, **kw):
    body = bytearray()
    body += build_join_info_head(account_id, **kw)
    _put_string(body, token_part2)
    return bytes(body)


async def build_join_match_startup(join_token, udp_key, match_code, account_id, block_val,
                                   server_ip="", region="BD",
                                   client_version="1.132.16",
                                   client_version_code="2019121229",
                                   access_token="",
                                   match_id=0, country="IN",
                                   map_id=1, game_mode=15, match_mode=1):
    join_token = join_token.strip()
    udp_key_b = bytes.fromhex(udp_key)
    match_code = [int(c) for c in str(match_code).strip()]
    enc_token = join_token.encode("utf-8") if isinstance(join_token, str) else join_token
    part1, part2 = split_token_bytes(enc_token)
    prepare_body = bytearray()
    _put_string(prepare_body, part1)
    prepare_pkt = (await build_packet(0x5E, match_code, 2, 447, 0, 1,
                                      bytes(prepare_body), udp_key_b)).hex()
    post_body = build_join_post_body(
        account_id, part2,
        game_mode=game_mode, match_mode=match_mode, map_id=map_id,
        country=country,
        client_version=client_version,
        client_version_code=client_version_code,
        match_id=int(match_id or block_val),
        client_ip="10.0.2.15",
        client_fingerprint="0",
        session_tag=0,
        is_emulator=0,
    )
    post_pkt = await build_packet(0x5A, match_code, 2, 448, 1, 1, post_body, udp_key_b)
    return [prepare_pkt], post_pkt.hex()


async def decode_packet(packet, key, mask=None):
    import itertools
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8:
        return None
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0, 1, 2, 3, 4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0, 1, 3, 4])]
    cands = []
    for kind, layout in layouts:
        off = 2
        f = {}
        ok = True
        for code in layout:
            size = _FIELD_SIZES[code]
            if off + size > len(data):
                ok = False
                break
            f[_FIELD_NAMES[code]] = (data[off] ^ k) if size == 1 else \
                ((data[off] | (data[off + 1] << 8)) ^ v80) & 0xFFFF
            off += size
        if not ok:
            continue
        if f["flags"] > 7 or f["sendOption"] > 7:
            continue
        if f["length"] != len(data) - off:
            continue
        body = data[off:off + f["length"]]
        content = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0:
                continue
            content = await oicq_unpad(await tea_cbc_decrypt(body, key))
            if content is None:
                continue
        else:
            content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        cands.append({"kind": kind, "layout": layout, "headerLen": off, "msgKey": data[0],
                      "cmd": f["cmd"], "flags": f["flags"], "sendOrder": f["sendOption"],
                      "orderId": f.get("orderId"), "length": f["length"],
                      "content": content, "crcOk": crc_ok, "score": score})
    if not cands:
        return None
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands[0]


PROTOCOL = {0: "NONE", 1: "INIT", 2: "HEARTBEAT", 3: "MATCHMAKING", 4: "STATS", 5: "GROUP",
            6: "FRIEND", 7: "MAIL", 8: "INVENTORY", 9: "BACKPACK", 10: "ACTIVITY", 11: "ACCOUNT",
            12: "CLAN", 13: "PROFILE", 14: "ROOM", 15: "PRESENCE", 16: "ELITEPASS",
            17: "RECONNECTION", 18: "CHANNEL", 19: "STORE", 21: "PET", 22: "MANUAL",
            23: "CHAMPIONSHIP", 24: "ANTIADDICTION", 25: "FRESH", 26: "LINKAGE", 27: "ATTENDANCE",
            28: "LIMITEDEVENT", 29: "FFANTI", 30: "CHAT", 31: "CUP", 32: "VIPCARD", 34: "CREDITSCORE",
            35: "GAMESERVERMANAGER", 36: "MINIGAME", 37: "WORKSHOP", 38: "CUSTOMEVENT",
            39: "ACHIEVEMENT", 40: "GIN", 41: "WEAPONPOWER", 42: "CSRANKINGMATCH",
            43: "BRRANKINGMATCH", 44: "OCCUPATION", 45: "MODESTATS", 46: "HIPPOINVENTORY",
            47: "PRIME", 48: "TEAMTOPUP", 49: "RELAYMART", 50: "REMATCH", 51: "GOOGLE_PLAY",
            52: "LBS", 53: "SHAREDGACHA", 54: "ESPORTS", 55: "SOCIALHALL"}

GROUP_CMD = {0: "NONE", 1: "CREATE", 2: "INVITE", 3: "INVITE_NTF", 4: "ACCEPT", 5: "REFUSE",
             6: "JOIN_NTF", 7: "LEAVE", 8: "LEAVE_NTF", 9: "START", 10: "START_NTF", 11: "STOP",
             12: "STOP_NTF", 13: "DISMISS_NTF", 14: "GROUPINFO", 15: "READY", 16: "READY_NTF",
             17: "CHANGE", 18: "CHANGE_NTF", 19: "JOINROOM", 20: "SPECTATEROOM",
             21: "SHOWEMOTE", 22: "SHOWEMOTE_NTF", 33: "JOIN", 34: "JOINREQUEST_NTF",
             35: "KICKOUT", 44: "ACCEPTJOIN_NTF", 45: "START_ROOM_MATCHMAKING",
             46: "STOP_ROOM_MATCHMAKING", 47: "START_ROOM_MATCHMAKING_NTF",
             48: "STOP_ROOM_MATCHMAKING_NTF", 49: "CREATE_ROOM", 55: "MIGRATE_GROUP",
             56: "MIGRATE_GROUP_NTF", 57: "TRANSFER_LEADER", 58: "TRANSFER_LEADER_NTF",
             102: "GROUP_NOTIFY_102"}

MATCHMAKING_CMD = {0: "NONE", 1: "START", 2: "CANCEL", 3: "GROUPSTART", 4: "GROUPCANCEL",
                   5: "MATCHMAKINGSUSS_NTF", 6: "DROPMATCH", 7: "GAMEOPENINGINFO",
                   8: "CHECKINGAMEPLAYER", 9: "CLEARINGAMEPLAYER", 10: "ANTIADDICTION_NTF",
                   11: "START_NTF", 14: "STOP_NTF", 15: "RANKING_BANNED",
                   16: "TEAMMATE_RANKING_BANNED", 17: "CDT_HACKER_NTF",
                   18: "GETMATCHMAKINGINFO", 19: "PUNISHINGAMEPLAYER", 23: "SPECTATE"}

RECONNECTION_CMD = {0: "NONE", 1: "RECONNECT", 2: "TIMEOUT", 3: "MATCHMAKINGSUSS_NTF",
                    4: "CANCEL", 5: "GROUPINFO", 6: "LEAVEMATCH_NTF"}

STATS_CMD = {0: "NONE", 1: "MATCHSTATS_NTF", 2: "UPDATEMMR_NTF"}

CMD_TABLES = {3: MATCHMAKING_CMD, 4: STATS_CMD, 5: GROUP_CMD, 17: RECONNECTION_CMD}

UDP_CMD = {1: "UDP_HELLO", 2: "UDP_ACK", 3: "UDP_PING", 4: "UDP_BYEBYE", 5: "UDP_LONGTIMENOSEE",
           6: "MUDP_CONNECT_ACK", 100: "RUDP_JOIN_MATCH", 101: "RUDP_PLAYER_JOIN",
           102: "RUDP_PLAYER_QUIT", 103: "RUDP_MATCH_END", 107: "RUDP_DEAD",
           110: "RUDP_BATTLE_START", 116: "RUDP_SYNC_SCENE_INFO", 117: "RUDP_SAFE_ZONE",
           130: "RUDP_JOIN_MATCH_FINISHED", 248: "RUDP_USE_ACTIVE_SKILL",
           250: "RUDP_ACTIVE_SKILL_STATE", 551: "RUDP_QUICK_CHAT",
           1901: "RUDP_GRI_SYNC", 2000: "RUDP_SERVER_TIME",
           2001: "RUDP_MY_STATE", 2012: "RUDP_OTHER_STATES",
           447: "RUDP_JOIN_MATCH_PREPARE", 448: "RUDP_JOIN_MATCH_POST",
           538: "RUDP_AUTOFLIGHTBOMB", 542: "RUDP_AUTOFLIGHTBOMB_STATE",
           543: "RUDP_PUSH_AUTOFLIGHT_ENEMY", 823: "RUDP_USE_ACTIVE_SKILL_FAIL",
           1658: "RUDP_PRESET_INFO"}

LEAVE_REASONS = {0: "NORMAL", 1: "OFFLINE", 2: "DROPMATCH", 3: "ALLJOINROOM",
                 4: "SOLOJOINROOM", 5: "KICKOUT", 6: "MERGEGROUP", 7: "TIMEOUT"}


def describe(ptype, cmd):
    p = PROTOCOL.get(ptype, f"UNKNOWN_{ptype}")
    if isinstance(cmd, int):
        return f"{p}/{CMD_TABLES.get(ptype, {}).get(cmd, f'CMD_{cmd}')}"
    return p


def udp_cmd_name(cmd):
    return UDP_CMD.get(cmd, f"CMD_{cmd}")


def _rbyte(region):
    reg = str(region or "IND").upper()
    return 0x14 if reg == "IND" else (0x19 if reg == "BD" else 0x15)


def _idc_entries(region):
    reg = str(region or REGION).upper()
    return [{1: "IDC1", 2: 75, 3: reg}, {1: "IDC2", 2: 123, 3: reg}]


def _vi(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _one(field, v):
    if isinstance(v, dict):
        body = _pb(v)
        return _vi((field << 3) | 2) + _vi(len(body)) + body
    if isinstance(v, int):
        return _vi(field << 3) + _vi(v)
    if isinstance(v, (str, bytes)):
        b = v.encode() if isinstance(v, str) else v
        return _vi((field << 3) | 2) + _vi(len(b)) + b
    raise TypeError(type(v))


def _pb(fields):
    out = bytearray()
    for f, v in fields.items():
        if isinstance(v, list):
            for it in v:
                out += _one(f, it)
        else:
            out += _one(f, v)
    return bytes(out)


def _br_rbyte(region):
    r = str(region or "BD").upper()
    return 0x19 if r == "BD" else (0x14 if r == "IND" else 0x15)


def _br_frame(ptype, region, proto, key, iv):
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(proto, 16))
    return bytes([ptype, _br_rbyte(region)]) + len(enc).to_bytes(4, "big") + enc


def _br_idc(reg, pings=(75, 123)):
    return [{1: "IDC1", 2: pings[0], 3: reg},
            {1: "IDC2", 2: pings[1], 3: reg}]


_C_S1="0200044B122D3B02010000000000000000000000000000E3172CED00"
_C_14_1 = b"\x32" + bytes([len(_C_S1)]) + _C_S1.encode() + b"\x30\x30" * 3
_C_14_3 = bytes.fromhex(
    "7e585c521207074f5d030c5c545104570455070f0a555a085201095701025b560601545606010f07100802487d5c4043481e07"
    "1f081a1709034c0757787500566b45627e7a6548407565577a700e7708627a047e7e041005447b5d655070547e437c607f7656"
    "5675704e5877525b5a5b515662410a105f5c5a4c1e637f1c7147430b4f6c557778605b67416b50635850500056575e005a7606"
    "057005067e0c15060045455e56447a665a6672694b5046524b057b79427c715560577b575f0a120e4b470e631b536262186b0f"
    "73406359475343795c481d7918564b47790c13054d1d714b5d75451740515f7e586d414e40595a03000e654e0741507a091b08"
    "4c6668777b1c4c676517505d6e7a4c4e7d7c791f5269057f42440207041005004d7e5c5977037d4a631f560255026b7a647e6b"
    "0007015503746353500e1a0048701a0153626506774f18065e0558610457421856007313771b60010b140745554d7f50477d68"
    "770662600646696876026242541c4a49037f74750a1204074f487402135059457f517b415266604a434506064e79004c5a7b4f"
    "700d14044a58454a5a7c5e5f5b764354425e1267735041537d6041180a6d694305"
)
_C_14_7 = bytes.fromhex("1d02474b420204030506171d677c716374687d5f557051565753")
_C_14_11 = b"\x03" + (
    "bbSQ69i8H3F5AdV2KyoVlWj2cgPtsEL3Pi8QcWkc/NJiGxtxXsmeZDDwFPKPbvd56sULGeaD3qha9S6hKIkIb3oXVAAFErlI76uU2p2AqNdJyaucxz1ba5ecHPCBohQR6E5Y1UzpsgpxutURpI8pbqY0tCpeL1bOT+F5UaysgFmTeoIalHxxEYPQx7OVJHElCV5el0vpIs98JSA3nB8FWin6ckz5Fd0sG4n2g0B7OUOvcreqilCT737xI24wPxLdidSr1AJ2MK0/m3ugV1iqzPXhttKyvfmMNVY8DoXBBUcYt3vpK7mgbnietrOqJIbJC3O4ygX6IWl/hkp+ngsjfeOZSornpzFnxM/kkqZgZjVOweXe61FRU6JsGSeTeY63kqA/mbCPfdwodSYJE2hXfVJofxRG1644gFPYRkCPUjJazd2l9WAh9kd86kYbjphbxwz55ciWvZ3sDJR11W96ezyxJPhJPD8FQoQVmno6BP4e7QI1xe+h35bkS1epZq6K6xUP5YtHFvqbhARMNQKUYYzXQWRFMNL1JgAeMJNO0+eCPL57+RXzRKtlgM/rVsIWhNw8Oo9SdP+7wsGrMK+HIOJaF1apAXNRQ9mCqxI="
).encode()


def br_create_squad_pkt(region, client_version, key, iv):
    reg = str(region or "IND").upper()
    f = {
        1: 1,
        2: {
            2: b"\x01", 3: 1, 4: SQUAD_PLAYERS - 1, 5: "en",
            8: _br_idc(reg), 9: 2,
            10: bytes.fromhex("01090a0b12191a202729"),
            11: 1, 13: 1,
            14: {1: _C_14_1, 2: 40, 3: _C_14_3, 4: "w\\Z]", 6: 12, 7: _C_14_7,
                 8: client_version or "1.132.13", 9: 6, 10: 2, 11: _C_14_11},
            19: 329, 21: bytes.fromhex("374f521955"),
            24: [{1: 3, 2: 360}, {1: 4, 2: 391}, {1: 5, 2: 156},
                 {1: 29, 2: 204}, {1: 22, 2: 118}, {1: 14, 2: 139}, {1: 21}],
            30: "https://dl-ind-production.freefiremobile.com/2832022628717E276054_7104117490_107_1767713981_0",
        },
    }
    return _br_frame(0x05, reg, _pb(f), key, iv)


def br_join_team_pkt(code, region, client_version, key, iv):
    reg = str(region or "IND").upper()
    field9 = {1: _C_14_1, 2: 40, 3: _C_14_3, 4: "w\\Z]", 6: 12, 7: _C_14_7,
              8: client_version or "1.132.13", 9: 6, 10: 2, 11: _C_14_11}
    f = {1: 4, 2: {
        4: bytes.fromhex("01090a0b121619201d2729"),
        5: str(code), 6: 6, 8: 1,
        9: field9,
        11: _br_idc(reg, (99, 136)),
        13: "en", 16: bytes.fromhex("374f521955"),
        20: [{1: 3, 2: 360}, {1: 4, 2: 391}, {1: 5, 2: 156},
             {1: 29, 2: 204}, {1: 22, 2: 118}, {1: 14, 2: 139}, {1: 21}],
        27: {1: 2, 2: 4}}}
    return _br_frame(0x05, reg, _pb(f), key, iv)


def br_start_squad_pkt(uid, region, key, iv):
    reg = str(region or "IND").upper()
    return _br_frame(0x05, reg,
                     _pb({1: 9, 2: {1: int(uid), 7: _br_idc(reg)}}),
                     key, iv)


async def send_op31(group_id, region, key, iv):
    fields = {1: 31, 2: {1: int(group_id)}}
    pkt = f"05{_rbyte(region):02x}"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), pkt, key, iv)


async def GeneRaTePk(Pk, N, K, V):
    PkEnc = await EnC_PacKeT(Pk, K, V)
    _ = await DecodE_HeX(int(len(PkEnc) // 2))
    if len(_) == 2:
        HeadEr = N + "000000"
    elif len(_) == 3:
        HeadEr = N + "00000"
    elif len(_) == 4:
        HeadEr = N + "0000"
    elif len(_) == 5:
        HeadEr = N + "000"
    else:
        HeadEr = N + "0000"
    return bytes.fromhex(HeadEr + _ + PkEnc)


async def EnC_PacKeT(HeX, K, V):
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()


async def DecodE_HeX(H):
    R = hex(H)
    F = str(R)[2:]
    if len(F) == 1:
        F = "0" + F
        return F
    else:
        return F


async def _build_state_header(msg_key, cmd, body, key_bytes, layout):
    k = key_bytes[0]
    v80 = ((k << 8) | k) & 0xFFFF
    h = bytearray()
    h.append(msg_key & 0xFF)
    h.append(0x00)
    for code in layout:
        value = {0: 0, 1: cmd, 3: 0, 4: len(body)}[code]
        if _FIELD_SIZES[code] == 1:
            h.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            h.append(v & 0xFF)
            h.append((v >> 8) & 0xFF)
    h[1] = await crc7_buff(0, bytes(h[2:]) + body) & 0x7F
    return bytes(h)


def _decode_frame_payload(payload):
    if not HAS_PARSER:
        return None
    try:
        parsed = Parser().parse(payload.hex())
        decoded = {}
        for r in parsed:
            wt = r.wire_type
            if wt == "length_delimited":
                try:
                    sub = r.data.results
                    nested = {}
                    for sr in sub:
                        if sr.wire_type == "length_delimited":
                            try:
                                inner = sr.data.results
                                nested_inner = {}
                                for ir in inner:
                                    if ir.wire_type == "length_delimited":
                                        nested_inner[str(ir.field)] = {"data": "nested"}
                                    else:
                                        nested_inner[str(ir.field)] = {"data": ir.data}
                                nested[str(sr.field)] = nested_inner
                            except Exception:
                                nested[str(sr.field)] = {"data": str(sr.data)}
                        else:
                            nested[str(sr.field)] = {"data": sr.data}
                    decoded[str(r.field)] = nested
                except Exception:
                    decoded[str(r.field)] = {"data": str(r.data)}
            else:
                decoded[str(r.field)] = {"data": r.data}
        return decoded
    except Exception:
        return None


def _extract_team_code(decoded, master_id):
    if not isinstance(decoded, dict):
        return None
    candidates = []
    r5 = decoded.get("5")
    if isinstance(r5, dict):
        for k in ("1", "2", "3", "4", "5", "6", "11"):
            v = r5.get(k)
            if isinstance(v, dict):
                v = v.get("data")
            if isinstance(v, (str, int)):
                candidates.append(str(v))
    for k in ("1", "2", "3"):
        v = decoded.get(k)
        if isinstance(v, dict):
            v = v.get("data")
        if isinstance(v, (str, int)):
            candidates.append(str(v))
    for c in candidates:
        if not c or c == str(master_id):
            continue
        if c.isdigit() and len(c) >= 12 and c != str(master_id):
            continue
        return c
    for c in candidates:
        if c and c != str(master_id):
            return c
    return None


def _match_info_from_frame(ptype, cmd, decoded, payload=None):
    is_matchmaking = (ptype == 0x03 and cmd == 5)
    is_reconnect = (ptype == 0x11 and cmd == 3)
    if not (is_matchmaking or is_reconnect):
        return None

    def _extract(d):
        if not isinstance(d, dict):
            return None
        r5 = d.get("5") or d.get(5) or {}
        if not isinstance(r5, dict):
            return None
        ip_port = r5.get("2") or r5.get(2)
        udp_key = r5.get("3") or r5.get(3)
        token = r5.get("4") or r5.get(4)
        mcode = r5.get("42") or r5.get(42)
        if isinstance(ip_port, dict):
            ip_port = ip_port.get("data")
        if isinstance(udp_key, dict):
            udp_key = udp_key.get("data")
        if isinstance(token, dict):
            token = token.get("data")
        if isinstance(mcode, dict):
            mcode = mcode.get("data")
        if (isinstance(ip_port, str) and ":" in ip_port
                and isinstance(udp_key, str)
                and isinstance(token, str) and mcode is not None):
            r5_clean = dict(r5)
            r5_clean["2"] = ip_port
            r5_clean["3"] = udp_key
            r5_clean["4"] = token
            r5_clean["42"] = str(mcode)
            return r5_clean
        return None

    result = _extract(decoded)
    if result:
        return result

    if payload is not None:
        try:
            alt = parse_proto(payload)
            alt_norm = {}
            for k, vals in alt.items():
                for kind, v in vals:
                    if kind == "bytes":
                        try:
                            nested = parse_proto(bytes.fromhex(v))
                            alt_norm[str(k)] = {
                                str(nk): [{"data": nv} for _, nv in nv_list]
                                for nk, nv_list in nested.items()
                            }
                            break
                        except Exception:
                            pass
                    else:
                        alt_norm.setdefault(str(k), []).append({"data": v})
            return _extract(alt_norm)
        except Exception:
            pass
    return None


def _pput_varint(out, v):
    v = int(v)
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)


def _pput_zig(out, v):
    z = (int(v) << 1) ^ (int(v) >> 63)
    _pput_varint(out, z & 0xFFFFFFFFFFFFFFFF)


def _pput_float(o, f):
    bits = struct.unpack("<I", struct.pack("<f", f))[0]
    _pput_varint(o, bits)


def _prd_varint(b, p):
    v = i = 0
    while True:
        c = b[p + i]
        v |= (c & 0x7F) << (7 * i)
        i += 1
        if not c & 0x80:
            return v, p + i


def _pzag(v):
    return (v >> 1) ^ -(v & 1)


def _decode_other_states(body):
    players = {}
    if body is None or len(body) < 4:
        return players
    try:
        count = struct.unpack_from(">H", body, 0)[0]
    except struct.error:
        return players
    if count == 0 or count > 64:
        return players
    p = 2
    for _ in range(count):
        if p >= len(body):
            break
        try:
            sid = body[p]; p += 1
            x, p = _prd_varint(body, p); y, p = _prd_varint(body, p); z, p = _prd_varint(body, p)
            vx, p = _prd_varint(body, p); vy, p = _prd_varint(body, p); vz, p = _prd_varint(body, p)
            yr = body[p]; p += 1; ay = body[p]; p += 1; axz = body[p]; p += 1
            ps = body[p]; p += 1; pp = body[p]; p += 1
            plat, p = _prd_varint(body, p); cus = body[p]; p += 1
        except (IndexError, ValueError):
            break
        pos = (_pzag(x), _pzag(y), _pzag(z))
        if not (1 <= sid <= 64) or any(abs(v) > 4000000 for v in pos):
            break
        players[sid] = {
            "pos": pos,
            "vel": (_pzag(vx), _pzag(vy), _pzag(vz)),
            "yrot": yr, "aim_y": ay, "aim_xz": axz,
            "physx_state": ps, "physx_pose": pp,
            "platform": plat, "custom": cus,
        }
    return players


def _decode_my_state(body):
    if body is None or len(body) < 4:
        return None
    try:
        if body[:2] == b"\x00\x02":
            p = 3
        else:
            p = 0
            _pid, p = _prd_varint(body, p)
        x, p = _prd_varint(body, p)
        y, p = _prd_varint(body, p)
        z, p = _prd_varint(body, p)
    except (IndexError, ValueError):
        return None
    return (_pzag(x), _pzag(y), _pzag(z))


def _decode_player_join(body):
    if body is None or len(body) < 4:
        return None
    try:
        p = 0
        uid, p = _prd_varint(body, p); _s, p = _prd_varint(body, p)
        pid, p = _prd_varint(body, p); rl, p = _prd_varint(body, p)
        n = _pzag(rl)
        name = body[p:p+n].decode("utf-8", "replace")
    except (IndexError, ValueError):
        return None
    return uid, pid, name


def _decode_quick_chat(body):
    if body is None or len(body) < 3:
        return None
    try:
        p = 0
        cid, p = _prd_varint(body, p)
        _iid, p = _prd_varint(body, p)
        sender, p = _prd_varint(body, p)
    except (IndexError, ValueError):
        return None
    return cid, sender & 0xFF, sender


def _decode_server_time(body):
    if body is None or len(body) < 1:
        return None
    try:
        tick, _ = _prd_varint(body, 0)
    except (IndexError, ValueError):
        return None
    return tick


def _build_player_state(pid, pos, rot, tdir, vel, aim, ps=0, pp=0, plat=0, ping=0, jump=0, slide=0):
    o = bytearray()
    _pput_varint(o, pid)
    _pput_zig(o, pos[0]); _pput_zig(o, pos[1]); _pput_zig(o, pos[2])
    _pput_zig(o, rot[0]); _pput_zig(o, rot[1]); _pput_zig(o, rot[2])
    _pput_zig(o, tdir[0]); _pput_zig(o, tdir[1])
    _pput_zig(o, vel[0]); _pput_zig(o, vel[1]); _pput_zig(o, vel[2])
    o.append(ps & 0xFF); o.append(pp & 0xFF)
    _pput_float(o, aim[0]); _pput_float(o, aim[1]); _pput_float(o, aim[2])
    _pput_varint(o, plat); o.append(0); _pput_varint(o, ping)
    o.append(jump & 0xFF); _pput_varint(o, slide); o.append(0)
    return bytes(o)


def _build_c2s_state(pid, pos, rot, tdir, vel, aim, server_time, ps=0, pp=0, ping=0, jump=0, slide=0):
    o = bytearray()
    o += _build_player_state(pid, pos, rot, tdir, vel, aim, ps=ps, pp=pp, ping=ping, jump=jump, slide=slide)
    _pput_varint(o, server_time & 0xFFFFFFFF)
    return bytes(o)


def _parse_preset_skills(body):
    try:
        p = 0
        vals = []
        while p < len(body):
            v, p = _rd_varint(body, p)
            vals.append(v)
    except (IndexError, ValueError):
        return []
    for i in range(1, len(vals) - 1):
        if vals[i - 1] == 0 and 100 <= vals[i] <= 99999 and vals[i + 1] == 1:
            out = []
            j = i
            while j + 1 < len(vals) and 100 <= vals[j] <= 99999 and 1 <= vals[j + 1] <= 9:
                out.append((vals[j], vals[j + 1]))
                j += 2
            return out
    return []


def _parse_join_skills(body):
    out = []
    n = len(body)
    for i in range(n):
        if i > 0 and body[i - 1] >= 0x80:
            continue
        try:
            v, p = _rd_varint(body, i)
        except (IndexError, ValueError):
            continue
        if p - i < 2 or not (100 <= v <= 99999 and v % 100 == 6):
            continue
        chain = [v]
        q = p
        while q < n:
            try:
                v2, q2 = _rd_varint(body, q)
            except (IndexError, ValueError):
                break
            if q2 - q >= 2 and 100 <= v2 <= 99999 and v2 % 100 == 6:
                chain.append(v2)
                q = q2
            else:
                break
        if q < n and body[q] == 0x00 and (i == 0 or body[i - 1] in (0x00, 0x02, 0x08)):
            for c in chain:
                if c not in out:
                    out.append(c)
    return out


async def _send_position(loop, sock, remote, udp_key_b, nr, pid, old_pos, new_pos,
                         server_time, aim_yaw=0.0, speed=500, ping=90,
                         order_id=0, encrypted=True):
    new_pos = (int(new_pos[0]), int(new_pos[1]), int(new_pos[2]))
    old_pos = (int(old_pos[0]), int(old_pos[1]), int(old_pos[2]))
    dx = new_pos[0] - old_pos[0]; dz = new_pos[2] - old_pos[2]
    dist = math.sqrt(dx * dx + dz * dz)
    if dist >= 1:
        ux, uz = dx / dist, dz / dist
        velocity = (int(ux * speed), 0, int(uz * speed))
        heading = math.degrees(math.atan2(ux, uz))
        heading = ((heading + 180.0) % 360.0) - 180.0
        rot_c = int(heading * 100)
        tdir = (int(ux * 100), int(uz * 100))
        aim = (ux, 0.0, uz)
        pose = POSE_DASHING
    else:
        velocity = (0, 0, 0)
        rad = math.radians(aim_yaw)
        fx, fz = math.sin(rad), math.cos(rad)
        heading = ((aim_yaw + 180.0) % 360.0) - 180.0
        rot_c = int(heading * 100)
        tdir = (int(fx * 100), int(fz * 100))
        aim = (fx, 0.0, fz)
        pose = POSE_STANDING
    rotation = (rot_c, 0, 0)
    body = _build_c2s_state(pid, new_pos, rotation, tdir, velocity, aim,
                            server_time, ps=0, pp=pose, ping=ping)
    flags = 1 if encrypted else 0
    pkt = await build_packet(0x6A, nr, 0, CMD_PLAYER_STATE_UPLOAD, order_id, flags,
                             body, udp_key_b, encrypted=encrypted)
    try:
        await loop.sock_sendto(sock, pkt, remote)
    except Exception:
        pass


def _decode_safezone(body):
    """CMD 117 safezone: stage, outer(cx,cz,r), inner(cx,cz,r), start, end. Returns None if it does not look sane."""
    if not body or len(body) < 8:
        return None
    try:
        p = 1
        v = []
        for _ in range(8):
            x, p = _rd_varint(body, p)
            v.append(x)
    except (IndexError, ValueError):
        return None
    oc, orad = (_zag(v[0]), _zag(v[1])), v[2]
    ic, irad = (_zag(v[3]), _zag(v[4])), v[5]
    for c, r in ((ic, irad), (oc, orad)):
        if 0 < r <= 2000 and abs(c[0]) <= 4000000 and abs(c[1]) <= 4000000:
            return {"center": (c[0], 0, c[1]), "radius": r * NEW_ZONE_SCALE}
    return None


class _NewMover:
    """New movement. Server position (CMD 2001) is the base, our own steps are an offset on top of it
    (offset is reset every time the server confirms our position). Priorities: stay inside the safezone,
    chase the target / nearest enemy, else patrol in a circle. Zigzag, random pauses, jitter."""

    def __init__(self, brain):
        self.brain = brain
        self.base = None
        self.off = [0.0, 0.0, 0.0]
        self.step = float(NEW_STEP_PER_TICK)
        self.max_step = float(NEW_STEP_PER_TICK * 1.2)
        self.time_offset = random.uniform(0, 1000)
        self.pause_until = 0.0
        self.zig_phase = random.uniform(0, 2 * math.pi)
        self.zig_freq = random.uniform(1.5, 3.5)
        self.zig_amp = random.uniform(10.0, 25.0)
        self.zone_center = None
        self.zone_radius = 0.0

    def seed(self, pos):
        self.base = (int(pos[0]), int(pos[1]), int(pos[2]))
        self.off = [0.0, 0.0, 0.0]

    def set_zone(self, z):
        if z and NEW_USE_ZONE:
            self.zone_center = z["center"]
            self.zone_radius = float(z["radius"])

    def render(self):
        if self.base is None:
            return None
        return (int(self.base[0] + self.off[0]), int(self.base[1] + self.off[1]),
                int(self.base[2] + self.off[2]))

    def advance(self, ddx, ddz):
        self.off[0] += ddx
        self.off[2] += ddz

    def _target(self, now, pos):
        b = self.brain
        tp = None
        if (b.target_short is not None and b.target_pos is not None
                and (now - b.target_seen) <= JHUND_MAX_AGE):
            tp = b.target_pos
        else:
            sid = b.nearest_enemy()
            if sid is not None:
                tp = b.enemies.get(sid)
        if tp is None:
            return None
        d = math.hypot(tp[0] - pos[0], tp[2] - pos[2])
        if d < NEW_TARGET_MIN or d > NEW_TARGET_MAX:
            return None
        return tp

    def plan(self, now):
        if self.base is None and self.brain.my_pos is not None:
            self.seed(self.brain.my_pos)
        pos = self.render()
        if pos is None:
            return None
        if now < self.pause_until:
            return pos, 0.0, 0.0, 0.0
        if random.random() < NEW_PAUSE_CHANCE:
            self.pause_until = now + random.uniform(0.5, 1.5)
            return pos, 0.0, 0.0, 0.0

        aim = None
        if self.zone_center and self.zone_radius > 0:
            zx = pos[0] - self.zone_center[0]
            zz = pos[2] - self.zone_center[2]
            if math.sqrt(zx * zx + zz * zz) > self.zone_radius * 0.90:
                aim = self.zone_center
        if aim is None:
            tp = self._target(now, pos)
            if tp is not None and math.hypot(tp[0] - pos[0], tp[2] - pos[2]) > NEW_CHASE_MIN_DIST:
                aim = tp
        if aim is None:
            rad = math.radians((now * 20.0 + self.time_offset) % 360.0)
            aim = (pos[0] + 2000.0 * math.cos(rad), pos[1], pos[2] + 2000.0 * math.sin(rad))

        dx = aim[0] - pos[0]
        dz = aim[2] - pos[2]
        dist = math.sqrt(dx * dx + dz * dz)
        if dist < 50.0:
            return pos, 0.0, 0.0, dist
        ux, uz = dx / dist, dz / dist
        self.brain.yaw = math.degrees(math.atan2(ux, uz))
        self.zig_phase += 0.15
        za = math.sin(self.zig_phase * self.zig_freq) * math.radians(self.zig_amp)
        ca, sa = math.cos(za), math.sin(za)
        fx = ux * ca - uz * sa
        fz = ux * sa + uz * ca
        step = self.step if dist < 5000.0 else self.max_step
        move = min(step, dist) * random.uniform(0.95, 1.05)
        ddx, ddz = fx * move, fz * move
        return (int(pos[0] + ddx), pos[1], int(pos[2] + ddz)), ddx, ddz, dist


async def _send_new_position(loop, sock, remote, udp_key_b, nr, pid, pos, yaw, ddx, ddz,
                             server_time, jump=0, slide=0, ping=50):
    rad = math.radians(yaw)
    sx, sz = math.sin(rad), math.cos(rad)
    aim = (sx, 0.0, sz)
    rot = (int(sx * 100), 0, int(sz * 100))
    d = math.sqrt(ddx * ddx + ddz * ddz)
    if d >= 0.5:
        ux, uz = ddx / d, ddz / d
        vel = (int(ux * 500), 0, int(uz * 500))
        tdir = (int(ux * 100), int(uz * 100))
        pose = POSE_DASHING
    else:
        vel = (0, 0, 0)
        tdir = (int(sx * 100), int(sz * 100))
        pose = POSE_STANDING
    body = _build_c2s_state(pid, pos, rot, tdir, vel, aim, server_time, ps=0, pp=pose,
                            ping=ping, jump=jump, slide=slide)
    pkt = await build_packet(NEW_MSG_KEY, nr, 0, CMD_PLAYER_STATE_UPLOAD, None, 1,
                             body, udp_key_b, encrypted=True)
    try:
        await loop.sock_sendto(sock, pkt, remote)
    except Exception:
        pass


async def _send_active_skill(loop, sock, remote, udp_key_b, ru_layout, rel_oid,
                             pid, skill_id, my_pos, enemy_pos, yaw):
    """cmd 248 USE_ACTIVE_SKILL — matches Bot.py body layout exactly.
    
    Body fields:
      1: player_id (varint)
      2: skill_id (varint)
      3: enemy_x (zigzag varint)
      4: enemy_y (zigzag varint)
      5: enemy_z (zigzag varint)
      6: dir_x   (varint, unsigned — cos(atan2(dz,dx)) * 100)
      7: 0       (varint)
      8: dir_z   (varint, unsigned — sin(atan2(dz,dx)) * 100)
      9: 0       (varint)
    """
    oid = rel_oid[0]
    rel_oid[0] = (oid + 1) & 0xFFFF

    # Direction: unit vector from MY pos to ENEMY pos in XZ * 100 (Bot.py style)
    edx = int(enemy_pos[0]) - int(my_pos[0])
    edz = int(enemy_pos[2]) - int(my_pos[2])
    enemy_yaw = math.atan2(edz, edx)
    dir_x = int(round(math.cos(enemy_yaw) * 100))
    dir_z = int(round(math.sin(enemy_yaw) * 100))

    sb = bytearray()
    _pput_varint(sb, int(pid))
    _pput_varint(sb, int(skill_id))
    _pput_zig(sb, int(enemy_pos[0]))
    _pput_zig(sb, int(enemy_pos[1]))
    _pput_zig(sb, int(enemy_pos[2]))
    _pput_varint(sb, dir_x)      # unsigned!
    _pput_varint(sb, 0)
    _pput_varint(sb, dir_z)      # unsigned!
    _pput_varint(sb, 0)
    pkt = await build_packet(random.randint(0x5A, 0x63), ru_layout, 2,
                             CMD_ACTIVE_SKILL, oid, 1, bytes(sb), udp_key_b)
    await loop.sock_sendto(sock, pkt, remote)
    return oid


class _BotBrain:
    def __init__(self, pid, squad_ids, squad_count):
        self.pid = pid
        self.squad_ids = set(squad_ids)
        self.squad_count = max(1, squad_count)
        self.slot_index = 0
        idx = 0
        for sid in sorted(self.squad_ids):
            if sid == pid:
                self.slot_index = idx
                break
            idx += 1

        slot_ang = (2 * math.pi / self.squad_count) * self.slot_index
        er = random.uniform(JHUND_SLOT_MIN, JHUND_SLOT_MAX)
        self.enemy_off = (math.cos(slot_ang) * er, math.sin(slot_ang) * er)

        lead_ang = (2 * math.pi / self.squad_count) * self.slot_index + math.pi
        lr = random.uniform(120.0, 260.0)
        self.leader_off = (math.cos(lead_ang) * lr, math.sin(lead_ang) * lr)

        self.my_pos = None
        self.server_time_ms = 0
        self.server_kts = 0
        self.joined_at = time.time()
        self.target_short = None
        self.target_pos = None
        self.target_vel = (0.0, 0.0)
        self.target_seen = 0.0
        self.teammates = {}
        self.enemies = {}
        self.roster_full = {}   # short_id -> full_id
        self.yaw = 0.0
        self.my_short = pid & 0xFF
        self.my_team = (pid >> 24) & 0xFF
        self.random_goal = None
        self.random_until = 0.0
        self.wander_goal = None
        self.wander_until = 0.0
        self.strafe_dir = 1
        self.strafe_until = 0.0
        self.leader_pos = None
        self.identity_set = False

        # SKILL STATE
        self.join_skills = None
        self.active_skill_id = None
        self.skill_good_id = None
        self.skill_cd_until = 0.0
        self.last_skill_sent = 0.0
        self.last_skill_id = None
        self.skill_resp = []
        self.skill_reported = True
        self.skill_ok = False
        self.skill_failed_at = None
        self.my_bombs = set()
        self.drone_pending = None
        self.own_skill_seen = None
        self.seen_skills = []
        self.skill_candidates = []
        self.skill_idx = 0
        self.fight_started_at = 0.0

    def set_identity(self, full_id):
        self.my_short = full_id & 0xFF
        self.my_team = (full_id >> 24) & 0xFF
        self.pid = int(full_id)
        self.identity_set = True

    def is_teammate(self, short_id, roster):
        if short_id == self.my_short:
            return False
        ent = roster.get(short_id)
        if not ent:
            return False
        return ((ent[0] >> 24) & 0xFF) == self.my_team

    def update_positions(self, players, roster):
        self.teammates.clear()
        self.enemies.clear()
        self.roster_full = {}
        for sid, ent in roster.items():
            self.roster_full[sid] = ent[0]
        for sid, info in players.items():
            if sid == self.my_short:
                continue
            pos = info.get("pos")
            if not pos:
                continue
            if self.is_teammate(sid, roster):
                self.teammates[sid] = pos
            else:
                if info.get("physx_pose") != 8:
                    self.enemies[sid] = pos
                    if self.fight_started_at == 0.0:
                        self.fight_started_at = time.time()
        if self.teammates:
            sx = sz = sy = 0.0
            n = 0
            for p in self.teammates.values():
                sx += p[0]; sy += p[1]; sz += p[2]
                n += 1
            if self.my_pos is not None:
                sx += self.my_pos[0]; sy += self.my_pos[1]; sz += self.my_pos[2]
                n += 1
            if n > 0:
                self.leader_pos = (int(sx / n), int(sy / n), int(sz / n))
            else:
                self.leader_pos = None
        else:
            self.leader_pos = None

    def set_target(self, short_id):
        if short_id == self.my_short:
            return
        if short_id != self.target_short:
            self.target_pos = None
            self.target_seen = 0.0
            self.target_vel = (0.0, 0.0)
        self.target_short = short_id

    def clear_target(self):
        self.target_short = None
        self.target_pos = None
        self.target_seen = 0.0
        self.target_vel = (0.0, 0.0)

    def update_target_pos(self, info, now):
        prev = self.target_pos
        prev_seen = self.target_seen
        self.target_pos = info["pos"]
        self.target_seen = now
        if prev is not None and prev_seen > 0:
            dt = now - prev_seen
            if 0.01 < dt < 2.0:
                vx = (info["pos"][0] - prev[0]) / dt
                vz = (info["pos"][2] - prev[2]) / dt
                if abs(vx) < 30000 and abs(vz) < 30000:
                    self.target_vel = (vx, vz)

    def nearest_enemy(self):
        if self.my_pos is None or not self.enemies:
            return None
        my = self.my_pos
        best_sid = None
        best_d = 1e18
        for sid, pos in self.enemies.items():
            dx = pos[0] - my[0]; dz = pos[2] - my[2]
            d = dx * dx + dz * dz
            if d < best_d:
                best_d = d
                best_sid = sid
        return best_sid

    def server_time_now(self, now):
        if self.server_kts:
            return (self.server_kts + int((now - self.joined_at) * 1000.0)) & 0xFFFFFFFF
        if self.server_time_ms:
            return (self.server_time_ms + int((now - self.joined_at) * 1000.0)) & 0xFFFFFFFF
        return int((now - self.joined_at) * 1000.0) & 0xFFFFFFFF

    def plan(self, now):
        if self.my_pos is None:
            return None
        my = self.my_pos
        eox, eoz = self.enemy_off
        lox, loz = self.leader_off

        if (self.target_short is None
                or self.target_pos is None
                or (now - self.target_seen) > JHUND_MAX_AGE):
            auto = self.nearest_enemy()
            if auto is not None:
                self.set_target(auto)

        if (self.target_short is not None
                and self.target_pos is not None
                and (now - self.target_seen) <= JHUND_MAX_AGE):
            tx, ty, tz = self.target_pos
            age = now - self.target_seen
            if 0.05 < age < 1.0:
                vx, vz = self.target_vel
                tx += vx * age
                tz += vz * age
            tx += eox
            tz += eoz
            dx = tx - my[0]; dz = tz - my[2]
            dist = math.sqrt(dx * dx + dz * dz)
            new_y = int(my[1] + (ty - my[1]) * CHASE_Y_LERP)
            if dist <= STICK_DIST:
                if dist >= 1:
                    ux, uz = dx / dist, dz / dist
                    self.yaw = math.degrees(math.atan2(dx, dz))
                else:
                    rad = math.radians(self.yaw)
                    ux, uz = math.sin(rad), math.cos(rad)
                if now >= self.strafe_until:
                    self.strafe_dir = -self.strafe_dir
                    self.strafe_until = now + random.uniform(0.8, 1.6)
                sstep = STEP_PER_TICK * STRAFE_FRAC
                sx = -uz * self.strafe_dir
                sz = ux * self.strafe_dir
                return (int(my[0] + sx * sstep), new_y, int(my[2] + sz * sstep)), dist, True
            step = STEP_PER_TICK
            if dist > JHUND_DASH_DIST:
                step = DASH_VEL * (MOVE_INTERVAL / 0.1)
            move = step if dist > step else dist
            self.yaw = math.degrees(math.atan2(dx, dz))
            nx = int(my[0] + dx / dist * move)
            nz = int(my[2] + dz / dist * move)
            return (nx, new_y, nz), dist, True

        if self.leader_pos is not None:
            cx, cy, cz = self.leader_pos
            tx = cx + lox
            tz = cz + loz
            ty = cy
            dx = tx - my[0]; dz = tz - my[2]
            dist = math.sqrt(dx * dx + dz * dz)

            if dist > REGROUP_RADIUS:
                new_y = int(my[1] + (ty - my[1]) * CHASE_Y_LERP)
                step = STEP_PER_TICK
                move = step if step < dist else dist
                self.yaw = math.degrees(math.atan2(dx, dz))
                nx = int(my[0] + dx / dist * move)
                nz = int(my[2] + dz / dist * move)
                return (nx, new_y, nz), dist, True

            if dist > LEADER_DEADZONE:
                pull = dist * REGROUP_WEIGHT
                step = min(STEP_PER_TICK, pull)
                new_y = int(my[1] + (ty - my[1]) * CHASE_Y_LERP)
                self.yaw = math.degrees(math.atan2(dx, dz))
                nx = int(my[0] + dx / dist * step)
                nz = int(my[2] + dz / dist * step)
                return (nx, new_y, nz), dist, True

            # grouped, no enemy: keep moving (wander around the squad centre)
            if self.wander_goal is None or now >= self.wander_until:
                ang = random.uniform(0, 2 * math.pi)
                r = random.uniform(WANDER_MIN, WANDER_MAX)
                self.wander_goal = (int(cx + math.cos(ang) * r), cy,
                                    int(cz + math.sin(ang) * r))
                self.wander_until = now + random.uniform(1.5, 3.0)
            wx, wy, wz = self.wander_goal
            wdx = wx - my[0]; wdz = wz - my[2]
            wdist = math.sqrt(wdx * wdx + wdz * wdz)
            if wdist < 80.0:
                self.wander_goal = None
                return (my[0], my[1], my[2]), dist, False
            wmove = STEP_PER_TICK if wdist > STEP_PER_TICK else wdist
            self.yaw = math.degrees(math.atan2(wdx, wdz))
            return (int(my[0] + wdx / wdist * wmove), my[1],
                    int(my[2] + wdz / wdist * wmove)), dist, True

        if self.random_goal is None or now >= self.random_until:
            ang = random.uniform(0, 2 * math.pi)
            r = random.uniform(1500.0, 3000.0)
            self.random_goal = (int(my[0] + math.cos(ang) * r),
                                my[1],
                                int(my[2] + math.sin(ang) * r))
            self.random_until = now + random.uniform(1.0, 2.0)
        tx, ty, tz = self.random_goal
        dx = tx - my[0]; dz = tz - my[2]
        dist = math.sqrt(dx * dx + dz * dz)
        if dist < 50.0:
            self.random_goal = None
            return (my[0], my[1], my[2]), 0.0, False
        step = STEP_PER_TICK
        move = step if dist > step else dist
        self.yaw = math.degrees(math.atan2(dx, dz))
        nx = int(my[0] + dx / dist * move)
        nz = int(my[2] + dz / dist * move)
        return (nx, my[1], nz), dist, True


async def slave_loop(acct, holder, match_infos, stop_evt):
    tag = acct["tag"]
    region = acct.get("region", REGION)
    ip, port = acct["game_server"].split(":")
    key, iv = acct["key"], acct["iv"]
    jwt = acct["jwt"]
    ingame_id = int(acct["ingame_id"])
    ts = acct["ts"]
    auth_online = await build_auth_packet(ingame_id, jwt, ts, key, iv, region, "OnLine")
    ka_bytes = await send_keep_alive(region)
    remote_version = acct["cfg"].get("remote_version", _PLAY_VERSION)

    while not stop_evt.is_set():
        writer = None
        ka_task = None
        ka_stop = asyncio.Event()
        try:
            reader, writer = await asyncio.open_connection(ip, int(port))
            acct["writer"] = writer
            writer.write(auth_online)
            await writer.drain()
            writer.write(ka_bytes)
            await writer.drain()
            _log(f"Tcp Connected => {acct.get('name', tag)}")

            async def ka_loop():
                while not ka_stop.is_set():
                    try:
                        await asyncio.sleep(15)
                        if writer.is_closing():
                            return
                        writer.write(ka_bytes)
                        await writer.drain()
                    except Exception:
                        return
            ka_task = asyncio.create_task(ka_loop())

            try:
                await asyncio.wait_for(holder["team_code_ready"].wait(), 30)
            except asyncio.TimeoutError:
                continue

            team_code = holder["team_code"]
            if not team_code:
                await asyncio.sleep(1.0)
                continue

            j = br_join_team_pkt(team_code, region, remote_version, key, iv)
            writer.write(j)
            await writer.drain()

            joined = False
            join_sent_at = time.time()
            buf = bytearray()
            last_start = 0.0

            while not stop_evt.is_set():
                try:
                    chunk = await asyncio.wait_for(reader.read(65536), timeout=1.0)
                except asyncio.TimeoutError:
                    if not joined and time.time() - join_sent_at > 3:
                        joined = True
                        holder["slave_joined"].add(ingame_id)
                        print(f"  Bot Joined The Team => {acct.get('name', tag)}")
                    if joined and tag not in match_infos:
                        if holder["slave_joined"] >= holder["expected_ids"]:
                            if (time.time() - last_start) > START_REPEAT_INTERVAL:
                                try:
                                    s = br_start_squad_pkt(ingame_id, region, key, iv)
                                    writer.write(s)
                                    await writer.drain()
                                    last_start = time.time()
                                except Exception:
                                    pass
                    continue
                except Exception:
                    break

                if not chunk:
                    break
                buf.extend(chunk)

                while len(buf) >= 5:
                    ptype = buf[0]
                    plen = int.from_bytes(buf[1:5], "big")
                    if plen > 100_000 or len(buf) < 5 + plen:
                        break
                    payload = bytes(buf[5:5 + plen])
                    del buf[:5 + plen]

                    decoded = _decode_frame_payload(payload)
                    cmd = None
                    if isinstance(decoded, dict):
                        v = decoded.get("4")
                        if isinstance(v, dict):
                            v = v.get("data")
                        if isinstance(v, int):
                            cmd = v

                    if ptype == 0x05 and plen >= 200 and not joined:
                        joined = True
                        holder["slave_joined"].add(ingame_id)
                        print(f"  Bot Joined The Team => {acct.get('name', tag)}")

                    minfo = _match_info_from_frame(ptype, cmd, decoded, payload)
                    if minfo is not None and tag not in match_infos:
                        match_infos[tag] = minfo

                if joined and tag not in match_infos:
                    if holder["slave_joined"] >= holder["expected_ids"]:
                        if (time.time() - last_start) > START_REPEAT_INTERVAL:
                            try:
                                s = br_start_squad_pkt(ingame_id, region, key, iv)
                                writer.write(s)
                                await writer.drain()
                                last_start = time.time()
                            except Exception:
                                pass

        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(2.0)
        finally:
            ka_stop.set()
            if ka_task:
                ka_task.cancel()
                try:
                    await ka_task
                except Exception:
                    pass
            if writer is not None:
                try:
                    if not writer.is_closing():
                        writer.close()
                        await writer.wait_closed()
                except Exception:
                    pass
            acct["writer"] = None

        if stop_evt.is_set():
            break


async def master_loop(acct, slave_ids, holder, match_infos):
    tag = acct["tag"]
    region = acct.get("region", REGION)
    ip, port = acct["game_server"].split(":")
    key, iv = acct["key"], acct["iv"]
    jwt = acct["jwt"]
    ingame_id = int(acct["ingame_id"])
    ts = acct["ts"]
    slave_set = {int(x) for x in slave_ids}
    remote_version = acct["cfg"].get("remote_version", _PLAY_VERSION)
    auth_online = await build_auth_packet(ingame_id, jwt, ts, key, iv, region, "OnLine")
    ka_bytes = await send_keep_alive(region)

    writer = None
    ka_task = None
    ka_stop = asyncio.Event()
    try:
        reader, writer = await asyncio.open_connection(ip, int(port))
        acct["writer"] = writer
        writer.write(auth_online)
        await writer.drain()
        writer.write(ka_bytes)
        await writer.drain()
        _log(f"Tcp Connected => {acct.get('name', tag)}")

        async def ka_loop():
            while not ka_stop.is_set():
                try:
                    await asyncio.sleep(15)
                    if writer.is_closing():
                        return
                    writer.write(ka_bytes)
                    await writer.drain()
                except Exception:
                    return
        ka_task = asyncio.create_task(ka_loop())

        await asyncio.sleep(1.0)
        c = br_create_squad_pkt(region, remote_version, key, iv)
        writer.write(c)
        await writer.drain()
        print(f"  Team Created")

        created = False
        op31_sent = False
        buf = bytearray()
        last_start = 0.0

        while True:
            try:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=1.0)
            except asyncio.TimeoutError:
                if (holder["slave_joined"] >= slave_set
                        and holder["team_code"]
                        and tag not in match_infos):
                    if (time.time() - last_start) > START_REPEAT_INTERVAL:
                        try:
                            s = br_start_squad_pkt(ingame_id, region, key, iv)
                            writer.write(s)
                            await writer.drain()
                            last_start = time.time()
                        except Exception:
                            pass
                continue
            except Exception:
                break

            if not chunk:
                break
            buf.extend(chunk)

            while len(buf) >= 5:
                ptype = buf[0]
                plen = int.from_bytes(buf[1:5], "big")
                if plen > 100_000 or len(buf) < 5 + plen:
                    break
                payload = bytes(buf[5:5 + plen])
                del buf[:5 + plen]

                decoded = _decode_frame_payload(payload)
                cmd = None
                if isinstance(decoded, dict):
                    v = decoded.get("4")
                    if isinstance(v, dict):
                        v = v.get("data")
                    if isinstance(v, int):
                        cmd = v

                if ptype == 0x05 and isinstance(decoded, dict):
                    data = decoded.get("5", {})
                    if cmd == 1 and not created and plen >= 100:
                        gid = None
                        if isinstance(data, dict):
                            g = data.get("1")
                            if isinstance(g, dict):
                                g = g.get("data")
                            if isinstance(g, int):
                                gid = g
                        if gid is None:
                            gid = ingame_id
                        created = True
                        holder["group_id"] = gid
                    elif cmd == 32 and not holder["team_code"]:
                        tc_val = _extract_team_code(decoded, ingame_id)
                        if tc_val:
                            holder["team_code"] = tc_val
                            holder["team_code_ready"].set()
                            print(f"  Teamcode => {tc_val}")
                    if created and not op31_sent and holder["group_id"]:
                        op31_sent = True
                        try:
                            p31 = await send_op31(holder["group_id"], region, key, iv)
                            writer.write(p31)
                            await writer.drain()
                        except Exception:
                            pass
                    if cmd == 10:
                        print(f"  Match Started")

                minfo = _match_info_from_frame(ptype, cmd, decoded, payload)
                if minfo is not None and tag not in match_infos:
                    match_infos[tag] = minfo

            if (holder["slave_joined"] >= slave_set
                    and holder["team_code"]
                    and tag not in match_infos):
                if (time.time() - last_start) > START_REPEAT_INTERVAL:
                    try:
                        s = br_start_squad_pkt(ingame_id, region, key, iv)
                        writer.write(s)
                        await writer.drain()
                        last_start = time.time()
                    except Exception:
                        pass
    finally:
        ka_stop.set()
        if ka_task:
            ka_task.cancel()
            try:
                await ka_task
            except Exception:
                pass
        if writer is not None:
            try:
                if not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()
            except Exception:
                pass
        acct["writer"] = None


async def play_game_idle(server_ip_port, prepare_packets, post_packet, udp_key, match_code,
                        account_id, player_region, client_version, tag="[?]",
                        account_jwt="", sleep_ms=0, squad_done=None, name="",
                        squad_ids=None, server_kts=0):
    match_start = time.time()
    ping_task = hello_task = move_task = sock = None
    ping_stop = asyncio.Event()
    brain = _BotBrain(int(account_id),
                      squad_ids or [int(account_id)],
                      len(squad_ids or [int(account_id)]))
    if server_kts:
        brain.server_kts = int(server_kts)
        brain.server_time_ms = int(server_kts)
    roster = {}
    mover = _NewMover(brain) if MOVEMENT_MODE == "new" else None
    probe = {"mode": None}

    try:
        ip, port = server_ip_port.split(":")
        port = int(port)
        resolved_ip = socket.gethostbyname(ip)
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        optimize_udp_socket(sock)
        sock.setblocking(False)
        udp_key_b = bytes.fromhex(udp_key)
        remote = (resolved_ip, port)
        gap = sleep_ms / 1000.0 if sleep_ms else 0.02

        rel_oid = [2]
        ru_layout, nr = await layouts_from_mask(match_code)

        async def send_reliable(cmd, content):
            oid = rel_oid[0]
            rel_oid[0] = (oid + 1) & 0xFFFF
            pkt = await build_packet(random.randint(0x5A, 0x63), ru_layout, 2, cmd, oid, 1,
                                     content, udp_key_b)
            await loop.sock_sendto(sock, pkt, remote)
            return pkt

        if account_jwt:
            auth_pkt = await build_auth_datagram(account_jwt, account_id)
            await loop.sock_sendto(sock, auth_pkt, remote)

        hello_hex = await build_hello_packet(f"{account_id}_2585", udp_key_b, match_code)
        hello_bytes = bytes.fromhex(hello_hex)
        await loop.sock_sendto(sock, hello_bytes, remote)

        ack_state = "waiting_for_hello_reply"
        startup_sent = False
        local_closed = False
        send_lock = asyncio.Lock()
        nr = (await layouts_from_mask(match_code))[1]
        ack_state_dict = {"last_ack_t": time.time()}

        async def ka_loop():
            pklist = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
            i = 0
            while not ping_stop.is_set():
                if ack_state != "waiting_for_hello_reply":
                    break
                try:
                    await asyncio.wait_for(ping_stop.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
            while not ping_stop.is_set():
                pk = pklist[i % len(pklist)]
                cnt = int(time.time() * 1000) & 0xFFFFFFFF
                pkt = await build_packet(pk, nr, 0, 3, None, 0,
                                         cnt.to_bytes(4, "little") + b"\x00\x00\x00",
                                         udp_key_b, encrypted=False)
                try:
                    await loop.sock_sendto(sock, pkt, remote)
                except Exception:
                    pass
                i += 1
                try:
                    await asyncio.wait_for(ping_stop.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass

        async def hello_retry_loop():
            for _ in range(8):
                if ping_stop.is_set() or ack_state != "waiting_for_hello_reply":
                    return
                try:
                    await asyncio.wait_for(ping_stop.wait(), timeout=0.8)
                except asyncio.TimeoutError:
                    pass
                if ping_stop.is_set() or ack_state != "waiting_for_hello_reply":
                    return
                try:
                    await loop.sock_sendto(sock, hello_bytes, remote)
                except Exception:
                    pass

        async def move_loop():
            start_t = time.time()
            next_tick = time.time()
            ticks = 0
            order_id = 0
            probe_done = False
            anchor_every = 3

            last_seen_pos = None
            last_change_t = time.time()
            blocked_ticks = 0
            sidestep_dir = 1
            sidestep_until = 0.0

            cur_hz = NEW_SEND_HZ if mover is not None else MOVE_HZ
            MIN_HZ = cur_hz
            MAX_HZ = cur_hz
            RAMP_STEP = 0.5
            RAMP_AFTER = 5.0
            ramp_t = time.time()

            last_progress_t = time.time()
            forced_plain = False
            WATCHDOG_SEC = 15.0

            next_skill_at = 0.0
            skills_sent = 0
            active_skill_id = None

            while not ping_stop.is_set():
                try:
                    now = time.time()

                    cur = brain.my_pos
                    if cur is not None:
                        if last_seen_pos is None:
                            last_seen_pos = cur
                            last_change_t = now
                            last_progress_t = now
                            ramp_t = now
                        elif cur != last_seen_pos:
                            last_seen_pos = cur
                            last_change_t = now
                            last_progress_t = now
                            blocked_ticks = 0
                            if now - ramp_t > RAMP_AFTER and cur_hz < MAX_HZ:
                                cur_hz = min(MAX_HZ, cur_hz + RAMP_STEP)
                                ramp_t = now
                        else:
                            blocked_ticks += 1
                            if (now - last_change_t) > STUCK_TRIGGER:
                                if cur_hz > MIN_HZ:
                                    cur_hz = max(MIN_HZ, cur_hz - RAMP_STEP)
                                last_change_t = now
                                order_id = 0

                            if (now - last_progress_t) > 10.0 and not forced_plain:
                                forced_plain = True

                            if (now - last_progress_t) > WATCHDOG_SEC:
                                try:
                                    await loop.sock_sendto(sock, hello_bytes, remote)
                                    if account_jwt:
                                        auth_pkt2 = await build_auth_datagram(
                                            account_jwt, account_id)
                                        await loop.sock_sendto(sock, auth_pkt2, remote)
                                except Exception:
                                    pass
                                last_progress_t = now
                                order_id = 0

                    if time.time() - ack_state_dict["last_ack_t"] > 4.0:
                        order_id = 0
                        ack_state_dict["last_ack_t"] = time.time()

                    interval = (1.0 / cur_hz) * (random.uniform(0.92, 1.08) if mover is not None else 1.0)

                    if now < next_tick:
                        await asyncio.sleep(min(0.02, next_tick - now))
                        continue
                    next_tick += interval
                    if next_tick < now:
                        next_tick = now + interval

                    if brain.my_pos is None:
                        if now - start_t > SEED_POS_AFTER and brain.teammates:
                            tp = next(iter(brain.teammates.values()))
                            brain.my_pos = (int(tp[0]) + random.randint(-150, 150),
                                            int(tp[1]),
                                            int(tp[2]) + random.randint(-150, 150))
                            print(f"  [MOVE] {tag} no own-state from server, seeded pos from teammate")
                        else:
                            continue

                    if mover is not None:
                        # ---- NEW MOVEMENT ----
                        planned_n = mover.plan(now)
                        if planned_n is None:
                            continue
                        _np, ddx, ddz, _dist = planned_n
                        mover.advance(ddx, ddz)
                        render = mover.render()
                        brain.my_pos = render
                        jump = 1 if random.random() < NEW_JUMP_CHANCE else 0
                        slide = 1 if (not jump and random.random() < NEW_SLIDE_CHANCE) else 0
                        await _send_new_position(
                            loop, sock, remote, udp_key_b, nr, brain.pid, render,
                            random.uniform(0, 360), ddx, ddz, brain.server_time_now(now),
                            jump=jump, slide=slide)
                        ticks += 1
                    else:
                        planned = brain.plan(now)
                        if planned is None:
                            continue
                        new_pos, _dist, moving = planned
                        old_pos = brain.my_pos
                        if old_pos is None:
                            brain.my_pos = new_pos
                            continue

                        if blocked_ticks >= BLOCKED_TICKS and now >= sidestep_until:
                            if (blocked_ticks // BLOCKED_TICKS) % 2 == 1:
                                sidestep_dir = -sidestep_dir
                            sidestep_until = now + SIDESTEP_HOLD
                            blocked_ticks = 0

                        if now < sidestep_until:
                            nx = int(new_pos[0] + sidestep_dir * SIDESTEP_DIST)
                            nz = int(new_pos[2])
                            new_pos = (nx, new_pos[1], nz)

                        brain.my_pos = new_pos
                        speed = DASH_VEL if moving else 0

                        if not probe_done:
                            probe_done = True
                            await _send_position(
                                loop, sock, remote, udp_key_b, nr, brain.pid,
                                old_pos, new_pos, brain.server_time_now(now),
                                aim_yaw=brain.yaw, speed=speed, ping=90,
                                order_id=order_id, encrypted=True,
                            )
                            order_id = (order_id + 1) & 0xFFFF
                            await asyncio.sleep(0.15)
                            await _send_position(
                                loop, sock, remote, udp_key_b, nr, brain.pid,
                                old_pos, new_pos, brain.server_time_now(now),
                                aim_yaw=brain.yaw, speed=speed, ping=90,
                                order_id=order_id, encrypted=False,
                            )
                            order_id = (order_id + 1) & 0xFFFF
                            continue

                        enc_flag = (probe["mode"] != "plain")
                        if ticks % anchor_every == 0:
                            await _send_position(
                                loop, sock, remote, udp_key_b, nr, brain.pid,
                                new_pos, new_pos, brain.server_time_now(now),
                                aim_yaw=brain.yaw, speed=0, ping=90,
                                order_id=order_id, encrypted=enc_flag,
                            )
                        else:
                            await _send_position(
                                loop, sock, remote, udp_key_b, nr, brain.pid,
                                old_pos, new_pos, brain.server_time_now(now),
                                aim_yaw=brain.yaw, speed=speed, ping=90,
                                order_id=order_id, encrypted=enc_flag,
                            )
                        order_id = (order_id + 1) & 0xFFFF
                        ticks += 1


                    # ---- HOMER SKILL (Bot.py semantics) ----
                    if brain.skill_failed_at is not None:
                        brain.skill_failed_at = None
                        brain.skill_reported = True
                        next_skill_at = min(next_skill_at, now + SKILL_RETRY_FAIL)

                    if brain.skill_good_id is None and SKILL_GOOD["id"]:
                        brain.skill_good_id = SKILL_GOOD["id"]

                    if (not brain.skill_reported and not brain.skill_ok
                            and now - brain.last_skill_sent > SKILL_NO_REPLY_SEC):
                        brain.skill_reported = True

                    now_t = time.time()
                    can_skill = (SKILL_ENABLED
                                 and now_t >= brain.skill_cd_until
                                 and now_t - brain.last_skill_sent >= 0.5
                                 and brain.my_pos is not None
                                 and (now_t >= brain.fight_started_at + 1.0))

                    if can_skill:
                        own = list(brain.join_skills or [])
                        known = [k for k in KNOWN_ACTIVE_SKILLS if (not own or k in own)]
                        sk_id = brain.skill_good_id or (known[0] if known else ACTIVE_SKILL_ID)

                        # Nearest live enemy
                        best = None
                        for sid_, pos_ in brain.enemies.items():
                            d_ = math.hypot(pos_[0] - brain.my_pos[0],
                                            pos_[2] - brain.my_pos[2])
                            if d_ <= SKILL_MAX_DIST and (best is None or d_ < best[0]):
                                best = (d_, sid_, pos_)

                        if best is not None:
                            _d, esid, epos = best
                            brain.last_skill_sent = now_t
                            brain.skill_cd_until = now_t + 5.0   # quick retry window
                            brain.last_skill_id = sk_id
                            active_skill_id = sk_id
                            brain.skill_resp = []
                            brain.skill_reported = False
                            try:
                                await _send_active_skill(
                                    loop, sock, remote, udp_key_b, ru_layout,
                                    rel_oid, brain.pid, sk_id,
                                    brain.my_pos, epos, brain.yaw)
                                skills_sent += 1
                                _log(f"{tag} HOMER SPAWN #{skills_sent} id={sk_id} "
                                     f"enemy=short{esid} dist={int(_d)}")
                            except Exception as e:
                                _log(f"{tag} homer err: {e!r}")

                    # ---- drone target follow-up (543) — Bot.py body ----
                    pd_ = brain.drone_pending
                    if pd_ is not None:
                        brain.drone_pending = None
                        try:
                            t_now = time.time()
                            if t_now - pd_[4] > 2.0:
                                pass  # expired
                            else:
                                best = None
                                for sid_, pos_ in brain.enemies.items():
                                    d_ = math.hypot(pos_[0] - pd_[1], pos_[2] - pd_[3])
                                    if d_ <= DRONE_TARGET_MAX and (best is None or d_ < best[0]):
                                        best = (d_, sid_, pos_)
                                if best is not None:
                                    esid = best[1]
                                    target_full = brain.roster_full.get(esid)
                                    if target_full is not None:
                                        brain.my_bombs.discard(pd_[0])
                                        pb = bytearray()
                                        _pput_varint(pb, int(pd_[0]))       # bomb id
                                        _pput_varint(pb, int(target_full))  # FULL enemy id
                                        _pput_zig(pb, int(pd_[1]))          # bomb x
                                        _pput_zig(pb, int(pd_[2]))          # bomb y
                                        _pput_zig(pb, int(pd_[3]))          # bomb z
                                        await send_reliable(CMD_PUSH_AUTOFLIGHT_ENEMY, bytes(pb))
                                        brain.skill_cd_until = (
                                            brain.last_skill_sent + SKILL_COOLDOWN_SEC)
                                        _log(f"{tag} HOMER ATTACK -> 0x{target_full:08X} "
                                             f"short{esid}")
                                    else:
                                        # roster not resolved yet, keep waiting
                                        brain.drone_pending = pd_
                                else:
                                    # no live enemy near bomb, keep waiting
                                    brain.drone_pending = pd_
                        except Exception:
                            pass

                    if ticks % 15 == 0:
                        print(f"  [MOVE] {tag} tick={ticks} pos={brain.my_pos} "
                              f"enemies={len(brain.enemies)} mates={len(brain.teammates)} "
                              f"hz={cur_hz:.1f} mode={probe['mode']} "
                              f"skills={skills_sent}")
                except Exception as e:
                    print(f"  [MOVE] {tag} err: {e}")
                    await asyncio.sleep(0.5)

        ping_task = asyncio.create_task(ka_loop())
        hello_task = asyncio.create_task(hello_retry_loop())

        last_activity = time.time()

        async def send_join_match():
            nonlocal ack_state, startup_sent
            if startup_sent:
                return
            async with send_lock:
                if startup_sent:
                    return
                for p in prepare_packets:
                    await loop.sock_sendto(sock, bytes.fromhex(p), remote)
                    await asyncio.sleep(gap)
                await asyncio.sleep(gap)
                await loop.sock_sendto(sock, bytes.fromhex(post_packet), remote)
                startup_sent = True
                ack_state = "startup_sent"
                print(f"  Match Prepared")

        while not local_closed:
            if time.time() - match_start > 700:
                break
            try:
                resp, sa = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if resp:
                    last_activity = time.time()
                    frame = await decode_packet(resp, udp_key_b, match_code)
                    if frame:
                        cmd = frame.get('cmd')
                        oid = frame.get('orderId')
                        msg_key = frame.get('msgKey', 0)
                        content = frame.get('content')

                        if cmd == 4:
                            local_closed = True
                        if cmd == 2:
                            ack_state_dict["last_ack_t"] = time.time()
                        if msg_key < 100 and oid is not None:
                            da = await build_packet(0x68, nr, 0, 2, None, 1,
                                                    ((oid + 1) & 0xFFFF).to_bytes(2, "little"),
                                                    udp_key_b)
                            await loop.sock_sendto(sock, da, sa)
                        if cmd == 1:
                            if ack_state == "waiting_for_hello_reply":
                                ack_state = "ready_to_send_startup"
                        elif cmd == 3:
                            c = content or b""
                            cnt = c[:4] if len(c) >= 4 else c
                            rp = await build_packet(0x6D, nr, 0, 3, None, 0,
                                                    cnt + b"\x00\x00\x00", udp_key_b,
                                                    encrypted=False)
                            await loop.sock_sendto(sock, rp, sa)
                        elif cmd == 101:
                            info = _decode_player_join(content)
                            if info:
                                uid, full_id, pname = info
                                roster[full_id & 0xFF] = (full_id, pname)
                                if uid == int(account_id):
                                    brain.set_identity(full_id)
                                    if content:
                                        brain.join_skills = _parse_join_skills(content)
                                        if brain.join_skills:
                                            act = [k for k in KNOWN_ACTIVE_SKILLS
                                                   if k in brain.join_skills]
                                            brain.active_skill_id = act[0] if act else brain.join_skills[0]
                                            _log(f"{tag} equipped skills={brain.join_skills} "
                                                 f"active={brain.active_skill_id}")
                                    print(f"  Bot Joined => {pname} "
                                          f"(player_id=0x{full_id:08X})")
                                else:
                                    print(f"  Player Join => {pname}")
                        elif cmd == 2001:
                            mp = _decode_my_state(content)
                            if mp is not None:
                                brain.my_pos = mp
                                if mover is not None:
                                    mover.seed(mp)
                                if probe["mode"] is None:
                                    probe["mode"] = "enc"
                                if (ack_state == "startup_sent"
                                        and (move_task is None or move_task.done())):
                                    move_task = asyncio.create_task(move_loop())
                                    print(f"  [MOVE] started (own state) for {tag}")
                        elif cmd == 2012:
                            players = _decode_other_states(content)
                            if players:
                                brain.update_positions(players, roster)
                                if brain.target_short is None:
                                    auto = brain.nearest_enemy()
                                    if auto is not None:
                                        brain.set_target(auto)
                                if brain.target_short is not None:
                                    if brain.target_short in players:
                                        brain.update_target_pos(
                                            players[brain.target_short], time.time()
                                        )
                                    else:
                                        brain.clear_target()
                        elif cmd == 551:
                            qc = _decode_quick_chat(content)
                            if qc:
                                cid, sid, _raw = qc
                                if cid in CHAT_FOLLOW_TRIGGERS:
                                    brain.set_target(sid)
                        elif cmd == 130:
                            print(f"  Bot In Match")
                            if move_task is None or move_task.done():
                                move_task = asyncio.create_task(move_loop())
                                print(f"  [MOVE] started for {tag}")
                        elif cmd == 117:
                            if mover is not None:
                                mover.set_zone(_decode_safezone(content))
                        elif cmd == 103:
                            local_closed = True
                        elif cmd == CMD_PRESET_INFO:
                            pairs = _parse_preset_skills(content or b"")
                            if pairs:
                                brain.skill_candidates = [sid for sid, _slot in
                                                          sorted(pairs, key=lambda x: x[1])]
                                act = [k for k in KNOWN_ACTIVE_SKILLS
                                       if k in brain.skill_candidates]
                                brain.active_skill_id = (act[0] if act
                                                         else brain.skill_candidates[0])
                                _log(f"{tag} preset skills={pairs} active={brain.active_skill_id}")
                        elif cmd == CMD_ACTIVE_SKILL_STATE:
                            vals = []
                            try:
                                q = 0
                                while q < len(content or b""):
                                    v_, q = _rd_varint(content, q)
                                    vals.append(v_)
                            except (IndexError, ValueError):
                                pass
                            pid_, sid_ = (vals[0], vals[1]) if len(vals) > 1 else (None, None)
                            mine = (brain.pid is not None and pid_ == brain.pid)
                            if sid_ and 100 <= sid_ <= 99999:
                                if mine:
                                    brain.own_skill_seen = sid_
                            if (mine and time.time() - brain.last_skill_sent < 3.0
                                    and brain.last_skill_id):
                                brain.skill_ok = True
                                brain.skill_good_id = brain.last_skill_id
                                SKILL_GOOD["id"] = brain.last_skill_id
                                _log(f"{tag} ★ skill accepted id={brain.last_skill_id}")
                        elif cmd == CMD_AUTOFLIGHTBOMB:
                            if time.time() - brain.last_skill_sent < 3.0:
                                if brain.last_skill_id:
                                    brain.skill_ok = True
                                    brain.skill_good_id = brain.last_skill_id
                                    SKILL_GOOD["id"] = brain.last_skill_id
                            try:
                                q = 0
                                _bid, q = _rd_varint(content, q)
                                _owner, q = _rd_varint(content, q)
                                if brain.pid is not None and _owner == brain.pid:
                                    brain.my_bombs.add(_bid)
                                    brain.skill_cd_until = (
                                        brain.last_skill_sent + SKILL_COOLDOWN_SEC)
                                    _log(f"{tag} drone {_bid} created -> cooldown "
                                         f"{SKILL_COOLDOWN_SEC:.0f}s")
                            except (IndexError, ValueError):
                                pass
                        elif cmd == CMD_AUTOFLIGHTBOMB_STATE:
                            try:
                                q = 0
                                _bid, q = _rd_varint(content, q)
                                _stt, q = _rd_varint(content, q)
                                _bx, q = _rd_varint(content, q)
                                _by, q = _rd_varint(content, q)
                                _bz, q = _rd_varint(content, q)
                                if _bid in brain.my_bombs and _stt == 2:
                                    brain.drone_pending = (_bid, _pzag(_bx), _pzag(_by),
                                                           _pzag(_bz), time.time())
                                    _log(f"{tag} drone {_bid} find nearby enemy")
                            except (IndexError, ValueError):
                                pass
                        elif cmd == CMD_USE_SKILL_FAIL:
                            brain.skill_failed_at = time.time()
                            _log(f"{tag} skill refused id={brain.last_skill_id}")
                        elif cmd == CMD_DRONE_HIT:
                            vals = []
                            try:
                                q = 0
                                while q < len(content or b"") and len(vals) < 6:
                                    v_, q = _rd_varint(content, q)
                                    vals.append(v_)
                            except (IndexError, ValueError):
                                pass
                            if (len(vals) >= 5 and brain.pid is not None
                                    and vals[0] == brain.pid and vals[4] == 61):
                                _log(f"{tag} ★ drone hit: {vals[2]} damage on "
                                     f"0x{vals[1]:08X}")
            except asyncio.TimeoutError:
                pass
            except Exception:
                await asyncio.sleep(0.5)
            if ack_state == "ready_to_send_startup" and not startup_sent:
                await send_join_match()
            elif ack_state == "startup_sent":
                if (time.time() - last_activity) > 120:
                    break
                if (move_task is None or move_task.done()) and time.time() - match_start > 10:
                    move_task = asyncio.create_task(move_loop())
                    print(f"  [MOVE] fallback started for {tag}")
    except Exception:
        pass
    finally:
        ping_stop.set()
        for t in (ping_task, hello_task, move_task):
            if t:
                t.cancel()
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        if squad_done is not None:
            squad_done["count"] = squad_done.get("count", 0) + 1
            if squad_done["count"] >= squad_done["total"]:
                squad_done["event"].set()


def _load_jwt_cache():
    return _load_json_dict(JWT_CACHE_FILE)


def _save_jwt_cache(cache):
    with _file_lock:
        with open(JWT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)


def _get_cached_jwt(uid):
    cache = _load_jwt_cache()
    entry = cache.get(str(uid))
    if not entry:
        return None
    if time.time() - float(entry.get("saved_at", 0)) > JWT_TTL:
        return None
    return entry


def _set_cached_jwt(uid, data):
    cache = _load_jwt_cache()
    cache[str(uid)] = {
        "jwt": data["jwt"],
        "key": data["key"].hex() if isinstance(data["key"], (bytes, bytearray)) else data["key"],
        "iv":  data["iv"].hex()  if isinstance(data["iv"],  (bytes, bytearray)) else data["iv"],
        "ts": data["ts"],
        "game_server": data.get("game_server", ""),
        "chat_server": data.get("chat_server", ""),
        "server_url": data.get("server_url", ""),
        "region": data.get("region", ""),
        "ingame_id": data.get("ingame_id", 0),
        "saved_at": time.time(),
    }
    _save_jwt_cache(cache)


async def _try_login_with_region(rec, account_region, tag):
    uid = rec.get("uid")
    password = rec.get("pass") or rec.get("password")
    open_id = rec.get("open_id")
    access_token = rec.get("access_token")
    platform = rec.get("platform")

    cached = _get_cached_jwt(uid)
    if cached and cached.get("region") == account_region:
        cfg_local = build_region_cfg(account_region)
        return {
            "tag": tag, "uid": uid, "ingame_id": cached.get("ingame_id", 0),
            "open_id": open_id, "access_token": access_token,
            "jwt": cached["jwt"],
            "key": bytes.fromhex(cached["key"]),
            "iv":  bytes.fromhex(cached["iv"]),
            "ts": cached["ts"],
            "game_server": cached.get("game_server", ""),
            "chat_server": cached.get("chat_server", ""),
            "server_url": cached.get("server_url") or cfg_local["server_url"],
            "name": rec.get("name", "?"),
            "cfg": cfg_local,
            "region": account_region,
        }

    if not open_id or not access_token:
        open_id, access_token, platform = await get_guest_token(uid, password)
        rec["open_id"] = open_id
        rec["access_token"] = access_token
        rec["platform"] = platform
    platform = int(platform or 4)

    cfg_local = build_region_cfg(account_region)

    login = None
    last_err = None
    for attempt in range(1, 5):
        try:
            login = await asyncio.to_thread(major_login, tag, open_id,
                                            access_token, cfg_local, platform, account_region)
            break
        except Exception as e:
            last_err = e
            await asyncio.sleep(min(2.0 * attempt, 10.0))
    if login is None:
        raise RuntimeError(f"{tag} major_login gave up: {last_err}")

    payload = decode_jwt_payload(login["jwt"]) if login.get("jwt") else {}
    lock_reg = (payload.get("lock_region") or "").upper()

    if lock_reg and lock_reg != account_region:
        account_region = lock_reg
        cfg_local = build_region_cfg(lock_reg)
        login = await asyncio.to_thread(major_login, tag, open_id,
                                        access_token, cfg_local, platform, lock_reg)

    ld = await asyncio.to_thread(get_login_data, tag, open_id, access_token,
                                 cfg_local, platform, login["jwt"])

    result = {
        "tag": tag, "uid": uid, "ingame_id": login["account_id"],
        "open_id": open_id, "access_token": access_token, "jwt": login["jwt"],
        "key": _to_bytes(login.get("aes_key") or b""),
        "iv":  _to_bytes(login.get("aes_iv") or b""),
        "ts": login.get("server_time", 0),
        "game_server": ld["game_server"], "chat_server": ld["chat_server"],
        "server_url": login.get("game_url"), "name": rec.get("name", "?"),
        "cfg": cfg_local,
        "region": account_region,
    }
    _set_cached_jwt(uid, result)
    return result


async def login_account(rec, cfg, tag):
    stored_region = (rec.get("region") or REGION).upper()
    cycle_region = (cfg.get("region") or stored_region).upper()

    attempts = [stored_region]
    if cycle_region not in attempts:
        attempts.append(cycle_region)
    for fallback in ("IND", "BD", "ME", "SG", "ID", "TH", "VN", "PK"):
        if fallback not in attempts:
            attempts.append(fallback)

    last_err = None
    for reg in attempts:
        try:
            acct = await _try_login_with_region(rec, reg, tag)
            if reg != stored_region:
                rec["region"] = reg
                print(f"  {tag} region override: {stored_region} -> {reg}")
            return acct
        except Exception as e:
            last_err = e
            msg = str(e)
            if "HTTP 400" in msg or "implausible result" in msg:
                rec["open_id"] = None
                rec["access_token"] = None
                rec["platform"] = None
                continue
            raise
    raise RuntimeError(f"{tag} login failed for all regions: {last_err}")


async def get_guest_token(uid, password, max_retries=6):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    versions = ['4.0.18P6', '4.0.19P7', '4.0.20P1', '4.1.0P3', '4.1.5P2', '4.2.1P8',
                '4.2.3P1', '5.0.1B2', '5.0.2P4', '5.1.0P1', '5.2.0B1', '5.2.5P3',
                '5.3.0B1', '5.3.2P2', '5.4.0P1', '5.4.3B2', '5.5.0P1', '5.5.2P3']
    models = ['SM-A125F', 'SM-A225F', 'SM-A325M', 'SM-A515F', 'SM-A725F', 'SM-M215F', 'SM-M325FV',
              'Redmi 9A', 'Redmi 9C', 'POCO M3', 'POCO M4 Pro', 'RMX2185', 'RMX3085',
              'moto g(9) play', 'CPH2239', 'V2027', 'OnePlus Nord', 'ASUS_Z01QD']
    android_versions = ['9', '10', '11', '12', '13', '14']
    languages = ['en-US', 'es-MX', 'pt-BR', 'id-ID', 'ru-RU', 'hi-IN']
    countries = ['USA', 'MEX', 'BRA', 'IDN', 'RUS', 'IND']
    ua = (f"GarenaMSDK/{random.choice(versions)}({random.choice(models)};"
          f"Android {random.choice(android_versions)};"
          f"{random.choice(languages)};{random.choice(countries)};)")
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": ua,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    data = {
        "uid": _normalize_uid(uid), "password": password,
        "response_type": "token", "client_type": "2",
        "client_secret": SECRET, "client_id": "100067",
    }
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as r:
                    if r.status != 200:
                        last_err = f"HTTP {r.status}"
                        await asyncio.sleep(min(2.0 * attempt, 10.0))
                        continue
                    j = await r.json()
                    oid = j.get("open_id")
                    tok = j.get("access_token")
                    plat = j.get("platform", 4)
                    if oid and tok:
                        return oid, tok, int(plat or 4)
                    last_err = f"missing fields: {j}"
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(min(2.0 * attempt, 10.0))
    raise RuntimeError(f"guest token grant failed: {last_err}")


_equipped_uids = set()


def _equip_client_url(acct):
    srv = (acct.get("server_url") or "").rstrip("/")
    if "client." in srv:
        return srv
    r = (acct.get("region") or "IND").upper()
    if r == "IND":
        return "https://client.ind.freefiremobile.com"
    if r == "BD":
        return "https://client.bd.freefiremobile.com"
    return "https://clientbp.ggpolarbear.com"


async def equip_accounts(accounts):
    """equip.py se har account ko equip + reward claim (har uid ke liye sirf 1 baar)."""
    todo = [a for a in accounts if a.get("uid") not in _equipped_uids and a.get("jwt")]
    if not todo:
        return

    async def _one(a):
        try:
            await equip.run_equip_workflow(a["jwt"], _equip_client_url(a))
            _equipped_uids.add(a.get("uid"))
        except Exception as e:
            print(f"  X {a.get('tag', '?')} equip failed: {e}")

    await asyncio.gather(*[_one(a) for a in todo])


async def run_one_squad(batch, region_hint=None):
    if not batch:
        return

    base_region = (region_hint or batch[0].get("region") or REGION).upper()
    region_idx = REGION_ROTATION_LIST.index(base_region) if base_region in REGION_ROTATION_LIST else 0
    cycle = START_CYCLE
    region_idx += START_CYCLE // REGION_ROTATE_EVERY_N

    while True:
        current_region = REGION_ROTATION_LIST[region_idx % len(REGION_ROTATION_LIST)]
        cfg = build_region_cfg(current_region)
        print(f"  [CYCLE {cycle}] region => {current_region}")

        logged_in = []
        for i, rec in enumerate(batch):
            tag = "[M]" if i == 0 else f"[S{i}]"
            try:
                acct = await login_account(rec, cfg, tag)
                acct["tag"] = tag
                logged_in.append(acct)
            except Exception as e:
                print(f"  X {tag} login: {e}")
            await asyncio.sleep(1.5)

        if len(logged_in) < 2:
            print(f"  X not enough accounts logged in, retry 20s")
            await asyncio.sleep(20.0)
            cycle += 1
            continue

        await equip_accounts(logged_in)

        squad_ids = [int(a["ingame_id"]) for a in logged_in]
        master = logged_in[0]
        slaves = logged_in[1:]
        slave_ids = [int(s["ingame_id"]) for s in slaves]
        print(f"  Team Leader => {master.get('name', '?')}")

        holder = {
            "group_id": None,
            "team_code": None,
            "team_code_ready": asyncio.Event(),
            "slave_joined": set(),
            "expected_ids": set(slave_ids) | {int(master["ingame_id"])},
            "master_id": None,
        }
        match_infos = {}
        slave_stop = asyncio.Event()

        squad_done = {
            "event": asyncio.Event(),
            "count": 0,
            "total": len(logged_in),
            "started_at": time.time(),
        }

        slave_tasks = [
            asyncio.create_task(slave_loop(s, holder, match_infos, slave_stop))
            for s in slaves
        ]
        await asyncio.sleep(2.0)
        master_task = asyncio.create_task(master_loop(master, slave_ids, holder, match_infos))

        expected_tags = [a["tag"] for a in logged_in]
        deadline = time.time() + 180
        while time.time() < deadline:
            if all(t in match_infos for t in expected_tags):
                break
            await asyncio.sleep(0.5)

        missing = [t for t in expected_tags if t not in match_infos]
        if missing:
            print(f"  X missing match info: {missing} — retry in 15s")
            slave_stop.set()
            for t in slave_tasks + [master_task]:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*(slave_tasks + [master_task]), return_exceptions=True)
            for a in logged_in:
                w = a.get("writer")
                if w is not None:
                    try:
                        if not w.is_closing():
                            w.close()
                            await w.wait_closed()
                    except Exception:
                        pass
                    a["writer"] = None
            await asyncio.sleep(15.0)
            region_idx += 1
            cycle += 1
            continue

        for a in logged_in:
            r5 = match_infos[a["tag"]]
            server_ip_port = r5["2"]
            udp_key       = r5["3"]
            join_token    = r5["4"]
            match_code    = r5["42"]

            def _u(v):
                return v.get("data") if isinstance(v, dict) else v

            real_match_id   = _u(r5.get("1") or 0) or 0
            real_map_id     = _u(r5.get("6") or 1) or 1
            real_game_mode  = _u(r5.get("7") or 15) or 15
            real_match_mode = _u(r5.get("8") or 1) or 1
            real_sleep_ms   = _u(r5.get("5") or 0) or 0

            prepare_packets, post_packet = await build_join_match_startup(
                join_token, udp_key, match_code,
                int(a["ingame_id"]), real_match_id,
                server_ip=server_ip_port, region=a["region"],
                client_version="1.132.16",
                client_version_code="2019121229",
                access_token=a["access_token"],
                match_id=real_match_id,
                country=a["region"],
                map_id=real_map_id,
                game_mode=real_game_mode,
                match_mode=real_match_mode,
            )

            asyncio.create_task(play_game_idle(
                server_ip_port, prepare_packets, post_packet, udp_key, match_code,
                int(a["ingame_id"]), a["region"],
                a["cfg"].get("remote_version", _PLAY_VERSION),
                tag=a["tag"],
                account_jwt=join_token,
                sleep_ms=real_sleep_ms,
                squad_done=squad_done,
                name=a.get("name", "?"),
                squad_ids=squad_ids,
                server_kts=a.get("ts", 0),
            ))

        print(f"  Match dispatched — UDP running in background")

        slave_stop.set()
        for t in slave_tasks + [master_task]:
            if not t.done():
                t.cancel()
        await asyncio.gather(*(slave_tasks + [master_task]), return_exceptions=True)
        slave_tasks.clear()
        master_task = None

        for a in logged_in:
            w = a.get("writer")
            if w is not None:
                try:
                    if not w.is_closing():
                        w.close()
                        await w.wait_closed()
                        _log(f"TCP closed => {a.get('name', a.get('tag'))}")
                except Exception:
                    pass
                a["writer"] = None
            try:
                a["jwt"] = ""
            except Exception:
                pass

        if ONE_MATCH:
            try:
                await asyncio.wait_for(squad_done["event"].wait(), timeout=ONE_MATCH_WAIT)
            except asyncio.TimeoutError:
                print(f"  [{MODE_LABEL}] match wait timeout")
            print(f"  [{MODE_LABEL}] match finished")
            return

        await asyncio.sleep(NEW_MATCH_DELAY)

        cycle += 1
        if cycle % REGION_ROTATE_EVERY_N == 0:
            region_idx += 1
            print(f"  [ROTATE] next region => {REGION_ROTATION_LIST[region_idx % len(REGION_ROTATION_LIST)]}")


async def run_squad_game(accounts, region_hint=None):
    try:
        with open(UDP_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"# {datetime.now().isoformat()}\n")
    except Exception:
        pass
    if not accounts:
        return
    total = len(accounts)
    batch_size = SQUAD_PLAYERS
    batches = [accounts[i:i + batch_size] for i in range(0, total, batch_size)]

    async def run_batch(idx, batch):
        try:
            await run_one_squad(batch, region_hint=region_hint)
        except Exception:
            pass

    await asyncio.gather(*[run_batch(i, b) for i, b in enumerate(batches, 1)], return_exceptions=True)


async def start_match_interactive():
    accounts = load_accounts()
    if len(accounts) < 2:
        print(f"  X Need at least 2 accounts (found {len(accounts)})")
        return
    await run_squad_game(accounts)


def main():
    print()
    print(f"                RBC X Glory — Homer Edition  [{MODE_LABEL}]")
    print()
    asyncio.run(start_match_interactive())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  interrupted")
