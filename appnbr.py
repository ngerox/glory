# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#  NG RAXX — Squad Bot (v7.1 — BEARER FIX + FULL LOGIN TRACE + 60 GLORY + AUTO-EQUIP)
# ═══════════════════════════════════════════════════════════════════
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid, gc
import itertools, secrets, traceback, base64, collections, math
import hmac, hashlib, string, ssl
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import logging
import urllib3
from flask import Flask, Response, request
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import RbcTeam_pb2
import RbcFF_pb2
import thunderFF_pb2

try:
    import CguFF_pb2
except ImportError:
    CguFF_pb2 = None

try:
    from dashboard_server import start_web_dashboard
except ImportError:
    start_web_dashboard = None

# ★ AUTO-EQUIP
try:
    from equip import run_equip_workflow
    EQUIP_AVAILABLE = True
except ImportError as _e:
    print(f"[WARN] equip.py not found: {_e}")
    EQUIP_AVAILABLE = False
    async def run_equip_workflow(*a, **k): return

# ═══════════════════════════════════════════════════════════════════
#  MOVEMENT & GLORY CONFIG
# ═══════════════════════════════════════════════════════════════════
AUTO_MOVE_ENABLED         = True
AUTO_MOVE_START_DELAY     = 2.0
AUTO_MOVE_SPAWN_TIMEOUT   = 18.0
AUTO_MOVE_LAND_TIMEOUT    = 6.0
AUTO_MOVE_TICK_INTERVAL   = 0.1
AUTO_MOVE_WALK_SPEED      = 352
AUTO_MOVE_RUN_SPEED       = 546
AUTO_MOVE_RUN_CHANCE      = 0.6
AUTO_MOVE_RADIUS          = 6000
AUTO_MOVE_MIN_LEG         = 1500
AUTO_MOVE_TURN_PER_TICK   = 25.0
AUTO_MOVE_PAUSE_RANGE     = (0.6, 2.5)
AUTO_MOVE_RESYNC_DISTANCE = 2500
AUTO_MOVE_PIGGYBACK_ACK   = True
AUTO_MOVE_MSG_KEYS        = list(range(0x64, 0x6E))
AUTO_MOVE_DEFAULT_RTT     = 120

# ★ GLORY BOOST CONFIG ★
GLORY_BOOST_ENABLED       = True
GLORY_TICK_INTERVAL       = 0.05        # 20Hz fast sync
GLORY_ACTION_EVERY        = 0.5         # fake shoot/loot action packet
GLORY_PING_EVERY          = 0.5         # extra ping packet
GLORY_MSG_KEYS            = list(range(0x64, 0x6E))

SQUAD_ARRIVAL_RADIUS  = 280.0
SQUAD_TARGET_TIMEOUT  = 22.0
SQUAD_ENEMY_TTL       = 7.0
STUCK_THRESHOLD       = 6.0
STUCK_LOG_COOLDOWN    = 3.0

ANTI_AFK_ENABLED        = True
ANTI_AFK_TICK_HZ        = 6.0
ANTI_AFK_SPAWN_DELAY    = 3.0
ANTI_AFK_RADIUS         = 800
ANTI_AFK_SPEED          = 55
ANTI_AFK_SPRINT_SPEED   = 95
ANTI_AFK_IDLE_CHANCE    = 0.08
ANTI_AFK_SPRINT_CHANCE  = 0.35
ANTI_AFK_DECISION_SEC   = 2.5
ANTI_AFK_PING_EVERY     = 2.0
ANTI_AFK_JUMP_EVERY     = 20.0

ANALOG_DIRECTIONS = [
    (0.0,  1.0, "maju"), (0.0, -1.0, "mundur"),
    (-1.0, 0.0, "kiri"), (1.0,  0.0, "kanan"),
    (-0.7, 0.7, "maju-kiri"), (0.7,  0.7, "maju-kanan"),
    (-0.7,-0.7, "mundur-kiri"), (0.7, -0.7, "mundur-kanan"),
    (0.0,  0.0, "idle"),
]

ENABLE_SPEED_MOVEMENT       = True
MOVEMENT_SPEED_MIN          = 1.0
MOVEMENT_SPEED_MAX          = 1.4
MOVEMENT_PATTERN            = "circle"
MOVEMENT_TICK_MS            = 240
MOVEMENT_RADIUS             = 180
MOVEMENT_UPDATE_SPEED_EVERY = 4.0

MOVEMENT_STATE_IDLE_CHANCE   = 0.10
MOVEMENT_STATE_WALK_CHANCE   = 0.28
MOVEMENT_STATE_RUN_CHANCE    = 0.32
MOVEMENT_STATE_SPRINT_CHANCE = 0.10
MOVEMENT_STATE_JUMP_CHANCE   = 0.08
MOVEMENT_STATE_CROUCH_CHANCE = 0.06
MOVEMENT_STATE_PRONE_CHANCE  = 0.06

PLAYER_STATE_MAP = {"idle":0,"walk":1,"run":1,"sprint":1,"jump":2,"crouch":3,"prone":4}
MOVE_STATE_MAP   = {"idle":0,"walk":1,"run":2,"sprint":3,"jump":4,"crouch":1,"prone":1}
STATE_SPEED      = {"idle":0,"walk":45,"run":70,"sprint":95,"jump":55,"crouch":25,"prone":15}

MOVEMENT_AVAILABLE = True

RBC_RUNTIME = {
    "MaxSquads":                   5555555558,
    "MaxParallelMatchesPerSquad":  5555555555500,
    "MatchesPerSquad":             55555555555555550,
    "LifetimeSec":                 8 * 60 * 60,
    "PerMatchTimeoutSec":          15 * 60,              # ★ 15 MINUTES MAX
    "HeartbeatSec":                30,
    "MaxMatchesPerWorker":         999999999,
    "ReconnectOnLoginExpiry":      True,
    "RestartAfterLifetime":        True,
}
_MAX_PARALLEL_MATCHES_PER_SQUAD = RBC_RUNTIME["MaxParallelMatchesPerSquad"]
ACTIVE_GROUPS_FILE = "active_groups.json"

class RBCBotState:
    def __init__(self):
        self.accounts = {}
        self.account_credentials = {}
        self.auth_to_game_id = {}
        self.account_workers = {}
        self.refresh_callbacks = {}
        self.paused_accounts = set()
        self.total_matches = 0
        self.matches_started = 0
        self.total_exp_gained = 0
        self.start_time = time.time()
        self.creating = False

    def log(self, message, level='info'): pass

    def register_account(self, uid, nickname='Unknown', region='ID', level=1, exp=0, likes=0):
        key = str(uid)
        self.accounts[key] = {
            'uid': key, 'nickname': str(nickname or 'Unknown'),
            'region': str(region or 'ID'), 'level': int(level or 1),
            'exp': int(exp or 0), 'gained_exp': 0, 'likes': int(likes or 0),
            'status': 'ONLINE', 'matches': 0,
        }
        return self.accounts[key]

    def update_status(self, uid, status, remaining=0):
        key = str(uid)
        game_id = self.auth_to_game_id.get(key, key)
        if game_id in self.accounts:
            self.accounts[game_id]['status'] = str(status)
            self.accounts[game_id]['remaining'] = int(remaining or 0)

    def update_exp(self, uid, exp, level):
        key = str(uid)
        if key not in self.accounts:
            self.register_account(key)
        account = self.accounts[key]
        old_exp = int(account.get('exp', 0) or 0)
        new_exp = int(exp or 0)
        delta = max(0, new_exp - old_exp)
        account['exp'] = new_exp
        account['level'] = int(level or account.get('level', 1))
        account['gained_exp'] = int(account.get('gained_exp', 0) or 0) + delta
        self.total_exp_gained += delta

    def increment_match(self, uid):
        key = str(uid)
        game_id = self.auth_to_game_id.get(key, key)
        if game_id in self.accounts:
            self.accounts[game_id]['matches'] = int(self.accounts[game_id].get('matches', 0)) + 1
        self.total_matches += 1
        self.matches_started += 1

    def is_paused(self, uid):
        return str(uid) in self.paused_accounts

bot_state = RBCBotState()
ACTIVE_GROUPS = {}

WEB_HOST = "0.0.0.0"
WEB_PORT = 20333
ACCOUNTS_FILE = os.environ.get("RBC_ACCOUNTS_FILE", "accounts.json")
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
TOKEN_CACHE_TTL = 4500

API_PORT = 6293
API_BIND = '0.0.0.0'
API_KEY = b'Yg&tc%DEuh6%Zc^8'
API_IV = b'6oyZDr22E3ychjM%'
ApiTimeout = 15.0
ApiRetry = 2

START_MATCH_INTERVAL    = 2.0
NEW_MATCH_DELAY         = 2.0
MAX_MATCH_DURATION      = RBC_RUNTIME["PerMatchTimeoutSec"]
MATCH_IDLE_TIMEOUT      = 2400.0
EXP_REFRESH_INTERVAL    = RBC_RUNTIME["HeartbeatSec"]
EXP_REFRESH_AFTER_MATCH_DELAY = 5.0
MAX_CONSECUTIVE_PARSE_FAILURES = 10
NON_MATCH_RECONNECT_DELAY      = 1.0

BR_MODE_ID             = 1
BR_MAP_ID              = 1

REGION_LANG = {"ME": "ar", "IND": "hi", "ID": "id", "VN": "vi", "TH": "th",
               "BD": "bn", "PK": "ur", "TW": "zh", "RU": "ru", "SAC": "es",
               "BR": "pt", "NA": "pt", "SG": "pt", "US": "pt"}

FORCED_CLIENT_VERSION = "1.134.21"

MATCH_SEARCH_TIMEOUT   = 120.0
MATCH_WATCHDOG_CHECK   = 30.0
REGION_ROTATION_LIST   = ["IND", "ID", "SG", "TH", "MY", "VN", "PH"]
REGION_ROTATE_EVERY_N  = 2
MAX_SEARCH_ATTEMPTS    = RBC_RUNTIME["MaxMatchesPerWorker"]

SAFE_PLAY_MODE        = True
BYPASS_TIMING_JITTER  = True
BYPASS_PACKET_JITTER  = True
BYPASS_HELLO_DELAY    = True
BYPASS_KA_JITTER      = True

ENABLE_HTTP_PING = True
PING_INTERVAL    = 20.0
PING_TIMEOUT     = 8.0
PING_URL         = "https://loginbp.ppmainecoonghj.com/Ping"
PING_REAL_IP     = "103.109.214.211"

FALLBACK_UID = ""
FALLBACK_PASSWORD = ""

TEAM_MODE               = True
TEAM_SIZE               = 4
TEAM_PEER_WAIT_TIMEOUT  = 60.0
TEAM_CREATE_WAIT        = 4.0         # ★ Slightly longer for stability
TEAM_INVITE_CYCLE_WAIT  = 3.0
TEAM_INVITE_MAX_TIME    = 45.0
TEAM_HEARTBEAT_INTERVAL = 2.0
TEAM_IDLE_ITERS_TEAM    = 30000
TEAM_MEMBER_START_DELAY = 15.0
TEAM_FINAL_WAIT         = 5.0         # ★ 5 sec wait before start_match
TEAM_READY_DELAY        = 3.0
_accept_friend_request  = True
DEBUG_TEAM_PACKETS      = False

# ★ LOGIN TRACE / RETRY
LOGIN_DEBUG        = True          # False karne se step-logs band
LOGIN_MAX_RETRIES  = 3
LOGIN_RETRY_DELAY  = 2.0

def bypass_jitter(base, spread=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return base
    return max(0.05, base + random.uniform(-spread, spread))

def bypass_packet_jitter(base, spread_ratio=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_PACKET_JITTER): return base
    return max(0.1, base + random.uniform(-base * spread_ratio, base * spread_ratio))

def bypass_hello_delay():
    if not (SAFE_PLAY_MODE and BYPASS_HELLO_DELAY): return 0.0
    return random.uniform(0.05, 0.45)

def bypass_ka_jitter(base=5.0):
    if not (SAFE_PLAY_MODE and BYPASS_KA_JITTER): return base
    return max(3.0, base + random.uniform(-0.8, 1.2))

def bypass_human_reconnect_delay(attempt):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return min(attempt * 0.5, 2.0)
    return max(0.05, min(attempt * 0.5, 2.0) + random.uniform(-0.4, 0.7))

def get_device_for_account(account_identifier):
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                devices = json.load(f)
        except Exception: pass
    key = str(account_identifier)
    if key in devices: return devices[key]
    dev_list = [
        ("Samsung", "SM-A155F", "Mali-G57 MC2", "Android OS 13 / API-33 (TP1A.220624.014/E156BXXS6BXD2)"),
        ("Samsung", "SM-A155F", "Mali-G57 MC2", "Android OS 14 / API-34 (UP1A.231005.007/A155FXXU3BXD1)"),
        ("Samsung", "SM-A156E", "Mali-G57 MC2", "Android OS 14 / API-34 (UP1A.231005.007)"),
        ("Samsung", "SM-M155F", "Mali-G57 MC2", "Android OS 14 / API-34 (UP1A.231005.007)"),
    ]
    brand, model, gpu, os_ver = random.choice(dev_list)
    dev = {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        "brand": brand, "model": model, "gpu_renderer": gpu, "system_software": os_ver,
        "screen_width": 2340, "screen_height": 1080, "screen_dpi": "295",
        "memory": random.randint(5000, 6200),
        "processor_details": "ARM64 FP ASIMD AES | 2200 | 8",
        "client_ip": f"{random.randint(27, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}",
        "cpu_architecture": "64",
        "language": "en", "country_code": "SG",
        "city": "Coimbatore", "state": "TN",
        "telecom_operator": "airtel", "network_type_a": "WIFI",
    }
    devices[key] = dev
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    except Exception: pass
    return dev

_DNS_CACHE: Dict[str, Tuple[str, float]] = {}
_DNS_CACHE_TTL = 300.0

async def resolve_host_cloudflare(hostname):
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts): return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    try:
        loop = asyncio.get_running_loop()
        info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
        if info:
            ip = info[0][4][0]
            _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
            return ip
    except Exception: pass
    return hostname

def optimize_tcp_socket(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception: pass

def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass

client = httpx.AsyncClient(verify=False, timeout=10.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50))
headers = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859',
    'X-GA': 'v1 1', 'ReleaseVersion': 'OB55'
}

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
SIGN_KEY = HEX_KEY.encode()

_LOGIN_SEMAPHORE = asyncio.Semaphore(4)

KEYSTREAM = bytes([0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,
                   0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,
                   0x30,0x30,0x30,0x30,0x32,0x30])

GGRE_RAW = bytes.fromhex(
    "47475245010101006d020000b260ee08e1f86b4c57f9c70f86bba26ed5d1436bcf52e142db3249d905eded757764991ca31a8373cdd26eab91b80f3f1f6f262f4f10b895d7b6937ddba30a27197453890e9da49373f736c679b8254e2f8e1623e91084a5fdd5374fe478ff99e010834553fddeb0bec4018d142e49df9bb236675b67e852f92a43586f7a7d4d0d7a197a1d4da32714dab4d069ad53214e2c33b3877420a12459738c4c619cbd815fa878bbd104776bb3e1ac7818d5397b04a666ac57f682763ff2df31bc2f846ddc7904f3dce1bda0c4b01f9698e9166f98c84f92640abe3f6317834a42e5c12573b46842c1a6ea8fe6ca9c006dca48a2087e1f983dfb5692771e4a0b15b337ad669b1d08b40862b176bace5331b49a767375b1a8469012aa70a67b55fe71b72478201d0b3ac7269c064c960361e92ee7ba8a42cc6b582bf9b965fb388fa9172ad44c4b073ac23c02080a6bcd106b691ffdf4c7cf71e42f2063fcf196e9bddc5e85be1fe5048eb1b31b460efbb46d76195eef9904c4cba326f2e17ff51fec17dd965aa06dadd4ab07d6966e4a7c38e8afd66dfde56c872bb87516a8f7313c797e4d80e5ad4a5f7afad95c1e0449254adae052e71a3fb98399f93ab30848e0d23252dd45e6fd41bc5fa7303dfb846a8fd713a0032a0b0ae96dfba1bbe41d20abd8099e2cb7fccc329d25bd153029139ef05d090a5093ea557693c0a8d491395b8a23ca844b3887dd5dfc29ac06f4b9be87883a793211b973465e2644c4f5de02b8ab01571401203fc2740423826858cc6da0194c195d27aac4ec4b9d23d506c1501d06440aca3fc180926d75d4a004d3dff21eb4ea1e8c86e6c9627248eff953e1d192d5c8efc006a7e512388ef2ebdb72ee3ad42d719f28e8f994e12ebf4c79f2ffe3abd7408ccd2236a7b89b2606247a732c10c4"
)

CRC7_TABLE = bytes([
    0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,
    81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,76,69,
    43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,64,73,82,91,
    44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,46,17,24,3,10,
    86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,93,84,107,98,121,112,
    7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,9,0,27,18,45,36,63,54,
    88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,47,115,122,97,104,87,94,69,76,
    59,50,41,32,31,22,13,4,106,99,120,113,78,71,92,85,34,43,48,57,6,15,20,29,
    37,44,55,62,1,8,19,26,109,100,127,118,73,64,91,82,60,53,46,39,24,17,10,3,
    116,125,102,111,80,89,66,75,23,30,5,12,51,58,33,40,95,86,77,68,123,114,105,96,
    14,7,28,21,42,35,56,49,70,79,84,93,98,107,112,121,
])
_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0:1, 1:2, 2:2, 3:1, 4:2}
_FIELD_NAMES = {0:"sendOption", 1:"cmd", 2:"orderId", 3:"flags", 4:"length"}

class Colors:
    GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'
    CYAN='\033[96m'; MAGENTA='\033[95m'; WHITE='\033[97m'
    GOLD='\033[38;5;220m'; BOLD='\033[1m'; DIM='\033[2m'; ENDC='\033[0m'

NGRAXX_TAG = f"{Colors.MAGENTA}{Colors.BOLD}[NG-RAXX]{Colors.ENDC}"
RBC_TAG = NGRAXX_TAG

def _rbc_banner():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    art = [
        r" ███╗   ██╗ ██████╗     ██████╗  █████╗ ██╗  ██╗██╗  ██╗",
        r" ████╗  ██║██╔════╝     ██╔══██╗██╔══██╗╚██╗██╔╝╚██╗██╔╝",
        r" ██╔██╗ ██║██║  ███╗    ██████╔╝███████║ ╚███╔╝  ╚███╔╝ ",
        r" ██║╚██╗██║██║   ██║    ██╔══██╗██╔══██║ ██╔██╗  ██╔██╗ ",
        r" ██║ ╚████║╚██████╔╝    ██║  ██║██║  ██║██╔╝ ██╗██╔╝ ██╗",
        r" ╚═╝  ╚═══╝ ╚═════╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
    ]
    print(f"\n{Colors.MAGENTA}════════════════════════════════════════════════════════════════════{Colors.ENDC}", flush=True)
    print(f"{Colors.MAGENTA}╔══════════════════════════════════════════════════════════════════╗{Colors.ENDC}", flush=True)
    for line in art:
        print(f"{Colors.MAGENTA}║{Colors.ENDC}  {Colors.BOLD}{Colors.WHITE}{line}{Colors.ENDC}  {Colors.MAGENTA}║{Colors.ENDC}", flush=True)
    print(f"{Colors.MAGENTA}║{Colors.ENDC}                                                                  {Colors.MAGENTA}║{Colors.ENDC}", flush=True)
    print(f"{Colors.MAGENTA}║{Colors.ENDC}  {Colors.CYAN}◆  NG RAXX SQUAD BOT  ·  v7.1  ·  4-4 SQUAD + GLORY  ◆{Colors.ENDC}       {Colors.MAGENTA}║{Colors.ENDC}", flush=True)
    print(f"{Colors.MAGENTA}║{Colors.ENDC}  {Colors.DIM}BEARER FIX + FULL LOGIN TRACE — {now}{Colors.ENDC}                {Colors.MAGENTA}║{Colors.ENDC}", flush=True)
    print(f"{Colors.MAGENTA}╚══════════════════════════════════════════════════════════════════╝{Colors.ENDC}", flush=True)
    print(f"{Colors.MAGENTA}════════════════════════════════════════════════════════════════════{Colors.ENDC}\n", flush=True)

def print_colored(t, c=Colors.WHITE):
    try: print(f"{c}{t}{Colors.ENDC}", flush=True)
    except Exception: pass

def print_success(t):
    try:
        print(f"{RBC_TAG} {Colors.GREEN}[+] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "success")
    except Exception: pass

def print_error(t):
    try:
        print(f"{RBC_TAG} {Colors.FAIL}[-] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "error")
    except Exception: pass

def print_warning(t):
    try:
        print(f"{RBC_TAG} {Colors.WARNING}[!] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "warning")
    except Exception: pass

def print_info(t):
    try:
        print(f"{RBC_TAG} {Colors.CYAN}[i] {t}{Colors.ENDC}", flush=True)
        if bot_state is not None and hasattr(bot_state, "log"): bot_state.log(t, "info")
    except Exception: pass

# ═══════════════════════════════════════════════════════════════════
#  LOGIN TRACE HELPERS
# ═══════════════════════════════════════════════════════════════════
def _step(uid, stage, extra=""):
    if not LOGIN_DEBUG: return
    try:
        print(f"{Colors.DIM}[TRACE {uid}] {time.strftime('%H:%M:%S')} · {stage} {extra}{Colors.ENDC}", flush=True)
    except Exception: pass

def print_tb(stage, e=None):
    """Poora traceback + exception type/message print karta hai."""
    try:
        print(f"{Colors.FAIL}──────── TRACEBACK [{stage}] ────────{Colors.ENDC}", flush=True)
        traceback.print_exc()
        print(f"{Colors.FAIL}─────────────────────────────────────{Colors.ENDC}", flush=True)
    except Exception: pass
    if e is not None:
        print_error(f"[{stage}] {type(e).__name__}: {e}")

def _snip(b, n=180):
    try:
        if isinstance(b, (bytes, bytearray)):
            return f"{len(b)}B {bytes(b[:n])!r}"
        return str(b)[:n]
    except Exception: return "?"

def _dump_keys(label, d, limit=40):
    if not LOGIN_DEBUG: return
    try:
        if not isinstance(d, dict):
            print_info(f"[DUMP {label}] {type(d).__name__}={_snip(d)}"); return
        print_info(f"[DUMP {label}] keys={list(d.keys())[:limit]}")
        for k, v in list(d.items())[:limit]:
            dv = v.get("data") if isinstance(v, dict) else v
            print_info(f"   f{k} -> {type(dv).__name__} {_snip(dv, 60)}")
    except Exception: pass

def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d:
        v = d[key].get('data'); return v if v is not None else default
    if str(key) in d:
        v = d[str(key)].get('data'); return v if v is not None else default
    return default

_match_counters: Dict[str, int] = {}
_match_counter_lock = asyncio.Lock()

async def _inc_match(uid):
    async with _match_counter_lock:
        _match_counters[uid] = _match_counters.get(uid, 0) + 1
        return _match_counters[uid]

async def _dec_match(uid):
    async with _match_counter_lock:
        if uid in _match_counters and _match_counters[uid] > 0:
            _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)

async def _get_match_count(uid):
    async with _match_counter_lock:
        return _match_counters.get(uid, 0)

async def _get_total_match_count():
    async with _match_counter_lock:
        return sum(_match_counters.values())

_team_state = {"peers": {}, "leader_uid": None, "team_code": None, "pk_code": None,
    "members": set(), "members_lock": asyncio.Lock(), "lock": asyncio.Lock()}

# ═══════════════════════════════════════════════════════════════════
#  PER-ACCOUNT MOVEMENT STATE
# ═══════════════════════════════════════════════════════════════════

class AccountMoveState:
    def __init__(self, uid):
        self.uid = str(uid)
        self.target = None
        self.target_set_at = 0.0
        self.enemies = {}
        self.lock = asyncio.Lock()

_ACCOUNT_MOVE_STATES: Dict[str, AccountMoveState] = {}
_ACCOUNT_MOVE_LOCK = asyncio.Lock()

async def _get_account_move_state(uid):
    key = str(uid)
    async with _ACCOUNT_MOVE_LOCK:
        st = _ACCOUNT_MOVE_STATES.get(key)
        if st is None:
            st = AccountMoveState(key)
            _ACCOUNT_MOVE_STATES[key] = st
        return st

_enemy_bus = {"enemies": {}, "lock": asyncio.Lock()}

async def _enemy_bus_add(tag, pos):
    async with _enemy_bus["lock"]:
        _enemy_bus["enemies"][str(tag)] = {"pos": tuple(pos), "ts": time.time()}

async def _enemy_bus_snapshot():
    now = time.time()
    async with _enemy_bus["lock"]:
        fresh = {k: v for k, v in _enemy_bus["enemies"].items()
                 if now - v["ts"] < SQUAD_ENEMY_TTL}
        _enemy_bus["enemies"] = fresh
        return dict(fresh)

_account_slots = {"lock": asyncio.Lock(), "uid_to_slot": {}, "slots": set()}

async def _account_register_slot(uid, slot):
    if slot is None: return
    async with _account_slots["lock"]:
        _account_slots["uid_to_slot"][str(uid)] = int(slot)
        _account_slots["slots"].add(int(slot))

async def _account_is_teammate_slot(slot):
    if slot is None: return False
    async with _account_slots["lock"]:
        return int(slot) in _account_slots["slots"]

async def _account_set_target(uid, pos):
    st = await _get_account_move_state(uid)
    async with st.lock:
        st.target = tuple(pos)
        st.target_set_at = time.time()

async def _account_register_enemy(uid, tag, pos):
    st = await _get_account_move_state(uid)
    async with st.lock:
        st.enemies[str(tag)] = {"pos": tuple(pos), "ts": time.time()}
    await _enemy_bus_add(tag, pos)

async def _account_nearest_enemy(uid, from_pos):
    st = await _get_account_move_state(uid)
    now = time.time()
    own = {}
    async with st.lock:
        own = {k: v for k, v in st.enemies.items() if now - v["ts"] < SQUAD_ENEMY_TTL}
        st.enemies = own
    shared = await _enemy_bus_snapshot()
    merged = {**shared, **own}
    if not merged: return None
    best = None; best_d = float("inf")
    for _, v in merged.items():
        ex, _, ez = v["pos"]
        d = math.hypot(ex - from_pos[0], ez - from_pos[2])
        if d < best_d:
            best_d = d; best = v["pos"]
    return best

async def _account_get_target(uid):
    st = await _get_account_move_state(uid)
    async with st.lock:
        return st.target, st.target_set_at

async def _account_clear_target(uid, only_if=None):
    st = await _get_account_move_state(uid)
    async with st.lock:
        if only_if is None or st.target == only_if:
            st.target = None
            st.target_set_at = 0.0

async def _team_member_join(uid):
    uid = str(uid)
    async with _team_state["members_lock"]:
        before = len(_team_state["members"])
        _team_state["members"].add(uid)
        after = len(_team_state["members"])
    if after != before:
        print_success(f"[TEAM] 👥 In team ({after}/{TEAM_SIZE}) | joined: {uid}")
        try:
            for p_uid in list(_team_state["peers"].keys()):
                role = "LEADER" if _team_state["leader_uid"] == p_uid else "MEMBER"
                joined = p_uid in _team_state["members"]
                tag = f"IN_TEAM ({after}/{TEAM_SIZE}) [{role}]" if joined else f"JOINING ({after}/{TEAM_SIZE}) [{role}]"
                bot_state.update_status(p_uid, tag, 0)
        except Exception: pass
    return after

async def _team_member_leave(uid):
    async with _team_state["members_lock"]:
        _team_state["members"].discard(str(uid))

async def _team_member_count():
    async with _team_state["members_lock"]:
        return len(_team_state["members"])

async def _team_member_reset(keep_leader=True):
    async with _team_state["members_lock"]:
        _team_state["members"].clear()
        if keep_leader and _team_state["leader_uid"]:
            _team_state["members"].add(_team_state["leader_uid"])

_token_cache_memo = {}
_token_cache_memo_time = 0.0
_TOKEN_CACHE_MEMO_TTL = 5.0

def _json_serializer(obj):
    if isinstance(obj, (bytes, bytearray)): return {"__bytes_hex__": bytes(obj).hex()}
    raise TypeError(f"not serializable: {type(obj)}")

def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            try: return bytes.fromhex(obj["__bytes_hex__"])
            except Exception: return b""
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_deserializer(x) for x in obj]
    return obj

def _load_token_cache():
    global _token_cache_memo, _token_cache_memo_time
    now = time.time()
    if _token_cache_memo and (now - _token_cache_memo_time) < _TOKEN_CACHE_MEMO_TTL:
        return _token_cache_memo
    if not os.path.exists(TOKEN_CACHE_FILE): return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content: return {}
        data = json.loads(content)
        if not isinstance(data, dict): raise ValueError("root must be dict")
        parsed = _json_deserializer(data)
        _token_cache_memo = parsed; _token_cache_memo_time = now
        return parsed
    except Exception as e:
        print_error(f"Token cache corrupt -> delete: {e}")
        try: os.remove(TOKEN_CACHE_FILE)
        except Exception: pass
        return {}

def _save_token_cache(cache):
    global _token_cache_memo, _token_cache_memo_time
    try:
        tmp = TOKEN_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=_json_serializer)
        os.replace(tmp, TOKEN_CACHE_FILE)
        _token_cache_memo = cache; _token_cache_memo_time = time.time()
    except Exception as e: print_error(f"Cache save: {e}")

def cache_get(uid):
    cache = _load_token_cache()
    e = cache.get(str(uid))
    if not e: return None
    if time.time() - e.get("cached_at", 0) > TOKEN_CACHE_TTL:
        cache_invalidate(uid); return None
    if str(e.get("account_id", "")).isdigit(): e["account_id"] = int(e["account_id"])
    if not isinstance(e.get("login_payload_data"), (bytes, bytearray)):
        cache_invalidate(uid); return None
    return e

def cache_set(uid, data):
    cache = _load_token_cache()
    e = dict(data); e["cached_at"] = time.time()
    cache[str(uid)] = e; _save_token_cache(cache)
    print_success(f"[CACHE] Saved UID {uid}")

def cache_invalidate(uid):
    cache = _load_token_cache()
    if str(uid) in cache:
        del cache[str(uid)]; _save_token_cache(cache)

def _update_cache_profile(data, level, exp):
    try:
        keys = []
        if data.get('auth_uid'): keys.append(str(data['auth_uid']))
        if data.get('auth_token'): keys.append(f"tok_{data['auth_token'][:20]}")
        if not keys: return
        cache = _load_token_cache(); ch = False
        for k in keys:
            if k in cache and isinstance(cache[k], dict):
                cache[k]['level'] = level; cache[k]['exp'] = exp; ch = True
        if ch: _save_token_cache(cache)
    except Exception: pass

async def aes_encrypt(payload, key, iv):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, AES.block_size))

async def get_playstore_version():
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='id'))
        v = res.get("version")
        _step("-", "playstore version", str(v))
        return v
    except Exception as e:
        print_tb("get_playstore_version", e)
        return "1.134.21"

async def version_config(region="ID"):
    app_version = await get_playstore_version()
    lang = REGION_LANG.get(str(region).upper(), "en")
    url = ("https://version.ggwhitehawk.com/live/ver.php"
           f"?version={app_version}&lang={lang}&device=android&channel=android"
           f"&appstore=googleplay&region={str(region).upper()}"
           "&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    try:
        r = await client.get(url)
        _step("-", "version_config", f"HTTP {r.status_code} R={region}")
        r.raise_for_status()
        d = r.json()
        su = d.get("server_url")
        lr = d.get("latest_release_version") or "OB55"
        if not su:
            print_error(f"[VERSION] server_url missing | body={_snip(r.content)}")
            return None
        gops = [u.strip() for u in d.get("gop_url", "").split(";") if u.strip()]
        gop_1 = gops[0] if gops else "https://ffmconnect.ppmainecoonghj.com"
        remote = FORCED_CLIENT_VERSION or d.get("remote_version") or app_version
        _step("-", "version_config OK", f"rel={lr} cv={remote} srv={su[:40]}")
        return lr, remote, su, gop_1, app_version
    except Exception as e:
        print_tb("version_config", e)
        return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {"Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br", "Connection": "close"}
    data = {"uid": uid, "password": password, "response_type": "token", "client_type": "2",
        "client_secret": HEX_KEY, "client_id": "100067"}
    for attempt in range(1, 7):
        try:
            r = await client.post(url, headers=hdrs, data=data)
            _step(uid, f"get_access_token #{attempt}", f"HTTP {r.status_code} {_snip(r.content, 120)}")
            if r.status_code == 200:
                d = r.json()
                oid = d.get("open_id"); at = d.get("access_token"); pf = d.get("platform", 4)
                if oid and at:
                    _step(uid, "get_access_token OK", f"open_id={oid} pf={pf} token_len={len(at)}")
                    return oid, at, pf
                print_error(f"[TOKEN] 200 but no open_id/access_token: {_snip(r.content)}")
            elif r.status_code == 429:
                await asyncio.sleep(1.5); continue
        except Exception as e:
            print_tb(f"get_access_token #{attempt}", e)
        await asyncio.sleep(0.8)
    return None

# ═══════════════════════════════════════════════════════════════════
#  PROTO / DECODE HELPERS
# ═══════════════════════════════════════════════════════════════════
async def parse_results(parsed):
    out = {}
    for r in parsed:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            fd["data"] = await parse_results(r.data.results)
        out[r.field] = fd
    return out

async def decode_protobuf(data):
    parsed = Parser().parse(data)
    return json.dumps(await parse_results(parsed))

def decode_protobuf_dict_safe(data):
    try:
        parsed = Parser().parse(data)
        return _recursive_dict(parsed)
    except Exception: return {}

def _recursive_dict(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _recursive_dict(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _recursive_dict(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out

def _decode_proto_manual(data):
    result = {}; offset = 0; data_len = len(data)
    while offset < data_len:
        header = 0; shift = 0
        while offset < data_len:
            b = data[offset]; offset += 1
            header |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
            if shift > 28: break
        if header == 0: break
        fn = header >> 3; wt = header & 0x7
        if fn == 0: break
        if wt == 0:
            v = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 63: break
            result[fn] = v
        elif wt == 2:
            length = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 28: break
            if length > data_len - offset: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                if s and all(31 < ord(c) < 127 or ord(c) in (9,10,13) for c in s):
                    result[fn] = s
                else:
                    nested = _decode_proto_manual(value)
                    result[fn] = nested if nested else value.hex()
            except UnicodeDecodeError:
                nested = _decode_proto_manual(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 5: offset += 4
        elif wt == 1: offset += 8
        else: break
    return result

def decode_varint(data, offset):
    result = 0; shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80): return result, offset
        shift += 7
    return None, offset

def decode_protobuf_2(data):
    result = {}; offset = 0; dl = len(data)
    while offset < dl:
        header, offset = decode_varint(data, offset)
        if header is None: break
        fn = header >> 3; wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None: result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                result[fn] = s if s else value.hex()
            except UnicodeDecodeError:
                nested = decode_protobuf_2(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 1: offset += 8
        elif wt == 3: offset += 4
        else: break
    return result

def _parse_results_sync(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type == "varint": fd["data"] = r.data
        elif r.wire_type in ("string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _parse_results_sync(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _parse_results_sync(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out

def decode_protobuf_dict(data: bytes) -> dict:
    try: return _parse_results_sync(Parser().parse(data))
    except Exception: return {}

def extract_raw_fields(data: bytes) -> dict:
    result = {}; offset = 0; dl = len(data)
    while offset < dl:
        header, offset = decode_varint(data, offset)
        if header is None: break
        fn = header >> 3; wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None: result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None: break
            if offset + length > dl: break
            result[fn] = bytes(data[offset:offset+length]); offset += length
        elif wt == 1: offset += 8
        elif wt == 3: offset += 4
        else: break
    return result

def encode_varint(n):
    if n < 0: return b''
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def _encode_proto_std(fields):
    out = b""
    for f in sorted(fields.keys()):
        v = fields[f]
        if isinstance(v, bool): out += encode_varint((f << 3) | 0) + encode_varint(int(v))
        elif isinstance(v, int): out += encode_varint((f << 3) | 0) + encode_varint(v)
        elif isinstance(v, (str, bytes)):
            if isinstance(v, str): v = v.encode()
            out += encode_varint((f << 3) | 2) + encode_varint(len(v)) + v
    return out

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            nested = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)

def encrypt_api(plain_hex):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
        pad(bytes.fromhex(plain_hex), AES.block_size)).hex()

def encrypt_aes(hex_data: str) -> str:
    return encrypt_api(hex_data)

def encrypt_api_bytes(plain_bytes):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain_bytes, AES.block_size))

def _pb_varint(fn, val): return encode_varint((fn << 3) | 0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint((fn << 3) | 2) + encode_varint(len(enc)) + enc

def create_proto(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length(field, bytes(create_proto(item))))
                elif isinstance(item, str): packet.extend(_pb_length(field, item))
                elif isinstance(item, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(item)))
                elif isinstance(item, bool): packet.extend(_pb_varint(field, 1 if item else 0))
                elif isinstance(item, int): packet.extend(_pb_varint(field, item))
        elif isinstance(value, bool): packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int): packet.extend(_pb_varint(field, value))
        elif isinstance(value, str): packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

def create_packet(Pk, N, K, V):
    if isinstance(K, str): K = bytes.fromhex(K) if len(K) == 32 else K.encode()
    if isinstance(V, str): V = bytes.fromhex(V) if len(V) == 32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk), 16)).hex()
    L = len(PkEnc) // 2
    hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0: hexlen = '0' + hexlen
    pad_len = 12 - len(N) - len(hexlen)
    if pad_len < 0: pad_len = 0
    return bytes.fromhex(N + ('0' * pad_len) + hexlen + PkEnc)

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def generate_signature(payload_str):
    return hmac.new(SIGN_KEY, payload_str.encode(), hashlib.sha256).hexdigest()

def _bearer(tok=None):
    """httpx/h11 trailing space allow nahi karta -> 'Bearer' bina space."""
    t = str(tok).strip() if tok else ""
    return f"Bearer {t}" if t else "Bearer"

# ★ create_team field-14
_C_S1 = "0200044B122D3B02010000000000000000000000000000E3172CED00"
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

def create_team(key, iv, game_version="1.134.21"):
    fields = {
        1: 1, 2: {2: bytes.fromhex("01"), 3: 1, 4: 3, 5: "en",
            8: {1: "IDC3", 2: 123, 3: "ID"}, 9: 1,
            10: bytes.fromhex("01090a0b1219202729"), 11: 2, 13: 1,
            14: {1: _C_14_1, 2: 478, 3: _C_14_3, 4: "y[Z]", 6: 12, 7: _C_14_7,
                 8: str(game_version), 9: 3, 10: 1, 11: _C_14_11},
            19: 329, 21: bytes.fromhex("374f521955"), 24: {1: 21},
            27: "a_6534489873065906362"}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def team_fresh(account_id, key, iv):
    return create_packet(create_proto({1: 72, 2: {1: int(account_id)}}).hex(), "0515", key, iv)

def invite_player_in_team(target_uid, key, iv, region="ID"):
    return create_packet(create_proto({1: 2, 2: {1: int(target_uid), 2: region, 4: 1}}).hex(),
                         "0515", key, iv)

def accept_team_invite(target_uid, group_id, key, iv):
    fields = {1: 4, 2: {1: int(target_uid), 3: int(target_uid),
        4: bytes.fromhex("0107090a0b120f19202729"), 8: 1,
        9: {1: "08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",
            2: 235, 3: {14: 80, 11: 86}, 4: "{Y\\R", 6: 13, 7: {2: 4},
            8: "1.134.21", 9: 2, 10: 1, 11: "0362625351"},
        10: str(group_id),
        11: {"1": "IDC3", "2": 107, "3": "ID"}, 13: "en", 16: "374f5219",
        20: {1: 21}, 23: "a_6534489873065906362",
        24: "https://dl-sg-production.freefiremobile.com/",
        27: {1: 2, 2: 4}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def start_match_team(account_id, key, iv, region="ID"):
    fields = {1: 9, 2: {1: int(account_id), 7: {1: "IDC3", 2: 410, 3: region}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def ready_for_game(uid, key, iv):
    return create_packet(create_proto({1: 15, 2: {1: uid, 2: 1}}).hex(), "0519", key, iv)

def _rd_var(B, Pos, End):
    V = 0; Sh = 0
    while Pos < End:
        X = B[Pos]; Pos += 1
        V |= (X & 0x7F) << Sh
        if not (X & 0x80): break
        Sh += 7
        if Sh > 63: break
    return V, Pos

def _walk_proto(B, Pos=0, End=None, depth=0):
    import struct
    if depth > 20: return {}
    if End is None: End = len(B)
    Out = {}
    while Pos < End:
        try:
            Tag, Pos = _rd_var(B, Pos, End)
            F = Tag >> 3; W = Tag & 7
            if F == 0: break
            if W == 0:
                V, Pos = _rd_var(B, Pos, End)
                Out.setdefault(F, []).append(V)
            elif W == 2:
                Ln, Pos = _rd_var(B, Pos, End)
                if Pos + Ln > End: break
                Raw = B[Pos:Pos + Ln]; Pos += Ln
                DecOk = False
                try:
                    S = Raw.decode("utf-8")
                    if all(C.isprintable() or C in "\n\r\t" for C in S):
                        Out.setdefault(F, []).append(S); DecOk = True
                except Exception: pass
                if not DecOk:
                    Sub = None
                    try:
                        Sub = _walk_proto(Raw, 0, len(Raw), depth + 1)
                        if not Sub: Sub = None
                    except Exception: Sub = None
                    Out.setdefault(F, []).append(Sub if Sub else Raw.hex())
            elif W == 5:
                V = struct.unpack_from("<f", B, Pos)[0]; Pos += 4
                Out.setdefault(F, []).append(V)
            elif W == 1:
                V = struct.unpack_from("<d", B, Pos)[0]; Pos += 8
                Out.setdefault(F, []).append(V)
            else: break
        except Exception: break
    return Out

def _find_proto_root(Raw):
    for I in range(min(len(Raw) - 10, 256)):
        if Raw[I] in (0x08, 0x12):
            try:
                T = _walk_proto(Raw, I, len(Raw))
                if 1 in T and isinstance(T[1][0], int) and T[1][0] > 100000000:
                    return I, T
                if 2 in T and isinstance(T[2][0], str) and T[2][0].isalpha():
                    return I, T
            except Exception: continue
    return 0, {}

def _search_jwt_in_vals(Vals):
    if not isinstance(Vals, list): Vals = [Vals]
    for V in Vals:
        if isinstance(V, str):
            if V.startswith("eyJ") and V.count(".") == 2 and len(V) > 100:
                return V
            if len(V) > 20 and all(C in "0123456789abcdefABCDEF" for C in V):
                try:
                    Dec = bytes.fromhex(V)
                    Idx = Dec.find(b"eyJ")
                    if Idx != -1:
                        Allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
                        End = Idx
                        while End < len(Dec) and Dec[End] in Allowed: End += 1
                        Cand = Dec[Idx:End].decode("ascii", errors="ignore")
                        if Cand.count(".") == 2 and len(Cand) > 100:
                            return Cand
                except Exception: pass
        elif isinstance(V, dict):
            Found = _extract_jwt_from_tree(V)
            if Found: return Found
        elif isinstance(V, list):
            Found = _search_jwt_in_vals(V)
            if Found: return Found
    return None

def _extract_jwt_from_tree(Tree):
    if not isinstance(Tree, dict): return None
    V8 = Tree.get(8) or Tree.get("8")
    if V8:
        F = _search_jwt_in_vals(V8)
        if F: return F
    for Fnum, Vals in Tree.items():
        F = _search_jwt_in_vals(Vals)
        if F: return F
    return None

def extract_jwt_from_raw(Raw: bytes) -> Optional[str]:
    if not Raw: return None
    Off, Tree = _find_proto_root(Raw)
    Jwt = _extract_jwt_from_tree(Tree)
    if Jwt: return Jwt
    Marker = b"eyJ"
    Start = Raw.find(Marker)
    while Start != -1:
        Allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
        End = Start
        while End < len(Raw) and Raw[End] in Allowed: End += 1
        Cand = Raw[Start:End].decode("utf-8", errors="ignore")
        if Cand.count(".") == 2 and len(Cand) > 100:
            return Cand
        Start = Raw.find(Marker, Start + 1)
    return None

def tree_flat(Tree):
    Out = {}
    for K, V in Tree.items():
        if isinstance(V, list) and len(V) == 1: Out[str(K)] = V[0]
        else: Out[str(K)] = V
    return Out

# ═══════════════════════════════════════════════════════════════════
#  AUTH — REGISTER / GRANT / MAJORREGISTER / PAYLOAD / MAJORLOGIN / GETLOGIN
# ═══════════════════════════════════════════════════════════════════
async def register_account(password, gop_url, app_version):
    await asyncio.sleep(3.0)
    rp = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
    payload = json.dumps(rp, separators=(',', ':'))
    sig = generate_signature(payload)
    hdrs = {
        "User-Agent": f"GarenaMSDK/4.0.44(SM-E135F ;Android 14;en;GB;app {app_version} 2019118525;)",
        "Authorization": f"Signature {sig}",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
    }
    try:
        r = await client.post(f"{gop_url}/api/v2/oauth/guest:register",
                              headers=hdrs, content=payload, timeout=15.0)
        _step("-", "guest register", f"HTTP {r.status_code} {_snip(r.content, 100)}")
        data = r.json()
        if data.get("code") == 0: return data["data"]["uid"]
        print_error(f"[REGISTER] code={data.get('code')} msg={data.get('message')}")
    except Exception as e:
        print_tb("register_account", e)
    return None

async def grant_token(uid, password, gop_url, app_version, max_attempts=5):
    gp = {
        "client_id": 100067, "client_secret": HEX_KEY, "client_type": 2,
        "device_id": f"02-{uuid.uuid4()}", "password": password,
        "response_type": "token", "uid": int(uid),
    }
    payload = json.dumps(gp, separators=(',', ':'))
    sig = generate_signature(payload)
    hdrs = {
        "User-Agent": f"GarenaMSDK/4.0.44(SM-E135F ;Android 14;en;GB;app {app_version} 2019118525;)",
        "Authorization": f"Signature {sig}",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
    }
    urls = [f"{gop_url}/api/v2/oauth/guest/token:grant",
            f"{gop_url}/api/v2/oauth/guest:token:grant"]
    last_reason = "unknown"
    for attempt in range(max_attempts):
        for url in urls:
            try:
                r = await client.post(url, headers=hdrs, content=payload, timeout=15.0)
                text = r.text
                _step(uid, f"grant #{attempt+1}", f"HTTP {r.status_code} {_snip(text, 100)}")
                if r.status_code != 200:
                    last_reason = f"HTTP {r.status_code}: {text[:100]}"; continue
                try: data = json.loads(text)
                except Exception:
                    last_reason = f"non-JSON: {text[:100]}"; continue
                if data.get("code") == 0 and data.get("data"): return data["data"]
                last_reason = f"code={data.get('code')} msg={data.get('message') or '?'}"
            except Exception as e:
                last_reason = f"{type(e).__name__}: {e}"
        if attempt < max_attempts - 1:
            await asyncio.sleep(2.0 + attempt * 1.5)
    print_error(f"[GRANT] failed for UID {uid} | last={last_reason}")
    return None

async def major_register(release_v, access_token, open_id, name, game_version,
                         login_url, lang_code="en"):
    field14 = bytes(ord(c) ^ KEYSTREAM[i % 32] for i, c in enumerate(open_id))
    fields = {1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1, 13: 1,
              14: field14, 15: lang_code, 16: 2, 20: game_version, 21: 1, 22: GGRE_RAW}
    proto = _encode_proto_std(fields)
    payload = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(proto, 16))
    url = f"{login_url.rstrip('/')}/MajorRegister"
    hdrs = {
        "Accept": "*/*", "Authorization": _bearer(),
        "Content-Type": "application/x-www-form-urlencoded",
        "ReleaseVersion": f"{release_v}",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
        "X-Unity-Version": "2018.4.12f1",
    }
    try:
        r = await client.post(url, headers=hdrs, content=payload, timeout=30.0)
        content = r.content
        _step("-", "major_register", f"HTTP {r.status_code} len={len(content)}")
        if r.status_code != 200 or not content: return None
        for off in [0, 64, 48, 32, 16]:
            if off >= len(content): continue
            try:
                rr = decode_protobuf_2(content[off:])
                if rr and 3 in rr:
                    return {str(k): {"data": v} for k, v in rr.items()}
            except Exception: pass
        return None
    except Exception as e:
        print_tb("major_register", e)
        return None

async def get_payload(access_token, open_id, platform, version, lang_code="en", region="ID"):
    device_id = f"Google|{uuid.uuid4()}"
    major_login = {
        "3": str(datetime.now())[:-7], "4": "free fire", "5": 1,
        "7": str(version or FORCED_CLIENT_VERSION or "1.134.21"),
        "8": "Android OS 14 / API-34 (UP1A.231005.007/E156BXXS6AYD4)",
        "9": "Handheld", "10": "airtel", "11": "CarrierDataNetwork",
        "12": 2340, "13": 1080, "14": "295",
        "15": "ARM64 FP ASIMD AES | 2200 | 8", "16": 5586,
        "17": "Mali-G57 MC2", "18": "OpenGL ES 3.2 v1.r38p1",
        "19": device_id, "20": "27.61.46.111", "21": lang_code,
        "22": f"{open_id}", "23": f"{platform}", "24": "Handheld",
        "25": "samsung SM-A146B", "26": str(region).upper(), "29": f"{access_token}",
        "30": 1, "41": "airtel", "42": "4G",
        "57": "7428b253defc164018c604a1ebbfebdf",
        "60": 108009, "61": 3859, "62": 5023, "64": 3987,
        "65": 108009, "66": 3987, "67": 108009,
        "70": 4, "73": 3,
        "74": "/data/app/~~OlJmIW-Yzl-44x2WnJP4Nw==/com.garena.game.ffi-_eDk_pQQMiFk1YUeqwJBvQ==/lib/arm64",
        "76": 3,
        "77": "dd9d4c174e0472d34b7fd34bd5924bc9|/data/app/~~OlJmIW-Yzl-44x2WnJP4Nw==/com.garena.game.ffi-_eDk_pQQMiFk1YUeqwJBvQ==/base.apk",
        "78": 3, "79": 2, "81": "64", "83": "2019121269",
        "85": 3, "86": "OpenGLES2", "87": 8191, "88": int(platform),
        "92": 9570, "93": "android",
        "94": "KqsHT54jON6bxITmlrRyOrXWBqKqZ4BoqPzT/mhtriAfRt2dt7gC8pnAJfj11alcEUA5sD8BshSYQhxXT9RFmU6YzcI1FKK4MwxJcF4+kvelPD1H",
        "95": 111207,
        "96": "{\"cur_rate\":null,\"support_etc2\":false}",
        "97": 1, "99": "4", "100": "4", "102": {},
        "104": 11921, "105": 1,
        "106": "https://dl-tata.freefireind.in/live/ABHotUpdates/|https://core-tata.freefireind.in/live/ABHotUpdates/|dff941d41e6e3a9e76f05ed71fdc8d87",
        "107": "1.6168622e0868ddbd",
    }
    send_getlogin = dict(major_login)
    send_getlogin["90"] = "Coimbatore"
    send_getlogin["91"] = "TN"
    send_getlogin["99"] = "4"
    send_getlogin["103"] = 1
    p1 = create_proto(major_login).hex()
    p2 = create_proto(send_getlogin).hex()
    _step("-", "get_payload", f"p1={len(p1)//2}B p2={len(p2)//2}B region={region}")
    return bytes.fromhex(encrypt_aes(p1)), bytes.fromhex(encrypt_aes(p2))

async def major_login(payload, login_url, release_version):
    url = f"{login_url.rstrip('/')}/MajorLogin"
    hdrs = {"Accept": "*/*", "Authorization": _bearer(),
            "Content-Type": "application/x-www-form-urlencoded",
            "ReleaseVersion": f"{release_version}",
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
            "X-Unity-Version": "2018.4.12f1"}
    try:
        r = await client.post(url, headers=hdrs, content=payload, timeout=15.0)
        content = r.content
        _step("-", "major_login", f"HTTP {r.status_code} len={len(content)}")
        if r.status_code != 200:
            print_error(f"[MAJORLOGIN] HTTP {r.status_code} body={_snip(content)}")
            return None
        if len(content) < 100:
            print_error(f"[MAJORLOGIN] response too short: {_snip(content)}")
            return None
        best = None; best_score = -1; best_off = 0
        for off in [64, 0, 48, 32, 80, 16, 128, 8, 96, 60, 56, 40, 24, 20, 12, 4]:
            if off >= len(content): continue
            cb = content[off:]; cand = None
            try: cand = decode_protobuf_dict(cb)
            except Exception: cand = None
            if not cand:
                try:
                    c2 = decode_protobuf_2(cb)
                    if c2: cand = {str(k): {"data": v} for k, v in c2.items()}
                except Exception: cand = None
            if not cand: continue
            keys = set(cand.keys())
            has_jwt = ("8" in keys) or (8 in keys)
            has_url = ("10" in keys) or (10 in keys)
            score = len(cand) + (100 if has_jwt else 0) + (50 if has_url else 0)
            if score > best_score:
                best = cand; best_score = score; best_off = off
            if has_jwt and has_url: break
        if not best:
            print_error(f"[MAJORLOGIN] no protobuf candidate | hex={content[:64].hex()}")
            return None
        if ("8" not in best) and (8 not in best):
            jwt = extract_jwt_from_raw(content)
            if jwt:
                best["8"] = {"data": jwt}
                print_warning(f"[MAJORLOGIN] JWT recovered via raw scan (len={len(jwt)})")
        best["__RAW_HEX__"] = content.hex(); best["__OFFSET__"] = best_off
        _dump_keys("MajorLogin", best, 30)
        _step("-", "major_login parsed", f"off={best_off} fields={len(best)}")
        if ("8" not in best) and (8 not in best):
            print_error("[MAJORLOGIN] JWT field 8 absent — full dump above")
        return best
    except Exception as e:
        print_tb("major_login", e)
        return None

async def get_login_data(payload, jwt_token, server_url, release_version):
    url = f"{server_url.rstrip('/')}/GetLoginData"
    hdrs = {"Accept": "*/*", "Authorization": _bearer(jwt_token),
            "Content-Type": "application/x-www-form-urlencoded",
            "ReleaseVersion": f"{release_version}",
            "User-Agent": "UnityPlayer/2018.4.12f1", "X-GA": "v1 1",
            "X-GA-SV": str(int(time.time())), "X-Unity-Version": "2018.4.12f1"}
    for attempt in range(1, 4):
        try:
            r = await client.post(url, headers=hdrs, content=payload, timeout=10.0)
            content = r.content
            _step("-", f"get_login_data #{attempt}", f"HTTP {r.status_code} len={len(content)}")
            if r.status_code != 200:
                print_error(f"[GETLOGIN] HTTP {r.status_code} body={_snip(content)}")
                await asyncio.sleep(1.0); continue
            for off in [0, 64, 48, 32, 80, 16, 128, 8, 96, 112, 144, 160]:
                if off >= len(content): continue
                try:
                    c = decode_protobuf_dict(content[off:])
                    if c and (("14" in c and "32" in c) or (14 in c and 32 in c)):
                        _step("-", "get_login_data OK", f"off={off} addrs found")
                        return c
                except Exception: pass
            for off in [0, 64, 48, 32, 80, 16, 128, 8, 96]:
                if off >= len(content): continue
                try:
                    c = decode_protobuf_dict(content[off:])
                    if c and len(c) >= 3:
                        _dump_keys("GetLoginData", c, 30)
                        print_warning(f"[GETLOGIN] addrs (14/32) missing, using fallback off={off}")
                        return c
                except Exception: pass
            for off in [0, 64, 48, 32, 80]:
                if off >= len(content): continue
                c = decode_protobuf_2(content[off:])
                if c and len(c) >= 3:
                    _dump_keys("GetLoginData(manual)", c, 30)
                    print_warning(f"[GETLOGIN] manual decode fallback off={off}")
                    return {str(k): {"data": v} for k, v in c.items()}
            print_error(f"[GETLOGIN] no candidate decode | hex={content[:64].hex()}")
        except Exception as e:
            print_tb(f"get_login_data #{attempt}", e)
        await asyncio.sleep(1.0)
    return None

async def get_player_personal_show(target_uid, jwt_token, server_url, release_version):
    url = f"{server_url}/GetPlayerPersonalShow"
    payload = bytes.fromhex(encrypt_aes(create_proto({"1": int(target_uid)}).hex()))
    hdrs = {"authorization": _bearer(jwt_token),
            "host": server_url.replace("https://", "").split("/")[0],
            "x-ga": "v1 1", "content-type": "application/x-www-form-urlencoded",
            "releaseversion": f"{release_version}",
            "user-agent": "UnityPlayer/2022.3.47f1", "accept": "*/*",
            "x-unity-version": "2022.3.47f1"}
    try:
        r = await client.post(url, headers=hdrs, content=payload, timeout=8.0)
        if r.status_code != 200:
            _step(target_uid, "personal_show", f"HTTP {r.status_code}")
            return None
        return decode_protobuf_2(r.content)
    except Exception as e:
        print_tb("get_player_personal_show", e)
        return None

async def choose_region(region, jwt_token, login_url, release_version):
    region_code = str(region).upper()
    url = f"{login_url.rstrip('/')}/ChooseRegion"
    proto = create_proto({1: region_code})
    payload = bytes.fromhex(encrypt_aes(proto.hex()))
    hdrs = {
        "Accept-Encoding": "gzip",
        "Authorization": _bearer(jwt_token),
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "ReleaseVersion": f"{release_version}",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
        "X-Unity-Version": "2018.4.12f1",
    }
    try:
        r = await client.post(url, headers=hdrs, content=payload, timeout=15.0)
        print_info(f"[CHOOSE-REGION] {region} → HTTP {r.status_code} | {_snip(r.content, 80)}")
        return r.status_code
    except Exception as e:
        print_tb("choose_region", e); return None

def _iter_proto_values(d, depth=0):
    if depth > 6 or not isinstance(d, dict): return
    for k, v in d.items():
        if str(k).startswith("__"): continue
        data = v.get("data") if isinstance(v, dict) else v
        yield k, data
        if isinstance(data, dict):
            yield from _iter_proto_values(data, depth + 1)

def _extract_key_iv(res_json):
    if "__RAW_HEX__" in res_json and "__OFFSET__" in res_json:
        try:
            raw = bytes.fromhex(res_json["__RAW_HEX__"])
            off = int(res_json["__OFFSET__"])
            rf = extract_raw_fields(raw[off:])
            for kf, vf in [(22, 23), (24, 25), (6, 7)]:
                k = rf.get(kf); v = rf.get(vf)
                if isinstance(k, (bytes, bytearray)) and len(k) == 16 and \
                   isinstance(v, (bytes, bytearray)) and len(v) == 16:
                    _step("-", "key_iv", f"raw pair {kf}/{vf}")
                    return bytes(k), bytes(v)
        except Exception as e:
            print_tb("_extract_key_iv(raw)", e)

    found = {}
    try:
        for k, data in _iter_proto_values(res_json):
            raw = None
            if isinstance(data, (bytes, bytearray)) and len(data) == 16: raw = bytes(data)
            elif isinstance(data, str) and len(data) == 32:
                try:
                    c = bytes.fromhex(data)
                    if len(c) == 16: raw = c
                except Exception: pass
            if raw:
                try: found[int(k)] = raw
                except Exception: pass
    except Exception as e:
        print_tb("_extract_key_iv(scan)", e)

    if len(found) < 2:
        if found:
            print_error(f"[KEYIV] only {len(found)} 16-byte field(s): {list(found.keys())}")
        else:
            print_error("[KEYIV] no 16-byte field found")
        return None, None
    for kf, vf in [(22, 23), (24, 25), (6, 7)]:
        if kf in found and vf in found:
            _step("-", "key_iv", f"dict pair {kf}/{vf}")
            return found[kf], found[vf]
    sk = sorted(found.keys())
    print_warning(f"[KEYIV] fallback pair f{sk[0]}/f{sk[1]}")
    return found[sk[0]], found[sk[1]]

def _gf_field(ld, key, default=None):
    if not ld: return default
    for k in (str(key), key):
        v = ld.get(k, None)
        if v is None: continue
        if isinstance(v, dict): return v.get("data", default)
        return v
    return default

async def send_majorlogin(data, release_version, server_url):
    return await major_login(data, server_url, release_version)

async def send_getlogin(data, base_url, token, release_version):
    return await get_login_data(data, token, base_url, release_version)

# ═══════════════════════════════════════════════════════════════════
#  TCP STARTUP / PING
# ═══════════════════════════════════════════════════════════════════
async def send_ping(account_id, token, release_version):
    try:
        try: acc = int(account_id)
        except Exception: acc = 0
        now_ms = int(time.time() * 1000)
        payload = struct.pack("<Q", acc & 0xFFFFFFFFFFFFFFFF) + struct.pack("<Q", now_ms & 0xFFFFFFFFFFFFFFFF)
        req_id = secrets.token_urlsafe(18)[:22]
        hdrs = {
            'accept': '*/*', 'accept-encoding': 'deflate, gzip',
            'authorization': _bearer(token),
            'content-type': 'application/x-www-form-urlencoded',
            'releaseversion': release_version,
            'user-agent': 'UnityPlayer/2018.4.12f1',
            'x-ga': 'v1 1', 'x-ga-sv': str(int(time.time())),
            'x-railway-edge': 'sin1', 'x-railway-request-id': req_id,
            'x-real-ip': PING_REAL_IP, 'x-request-start': str(now_ms),
            'x-unity-version': '2018.4.12f1',
        }
        r = await client.post(PING_URL, headers=hdrs, content=payload, timeout=PING_TIMEOUT)
        return r.status_code == 200
    except Exception: return False

async def ping_worker(account_id, token, release_version, region="ID"):
    if not ENABLE_HTTP_PING: return
    uid_str = str(account_id); ok_count = 0; fails = 0
    try:
        await asyncio.sleep(5.0 + random.uniform(0, 2.0))
        while True:
            ok = await send_ping(uid_str, token, release_version)
            if ok:
                ok_count += 1; fails = 0
                if ok_count % 10 == 0: print_info(f"[PING] {uid_str} OK total={ok_count}")
            else:
                fails += 1
                if fails <= 3: print_warning(f"[PING] {uid_str} fail #{fails}")
            await asyncio.sleep(max(5.0, PING_INTERVAL + random.uniform(-3.0, 3.0)))
    except asyncio.CancelledError: pass
    finally: print_info(f"[PING] Stopped {uid_str} OK={ok_count}")

async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="ID", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = (await aes_encrypt(token.encode(), key, iv)).hex()
    enc_len = f"{len(enc)//2:08x}"
    reg = str(region).upper() if region else "ID"
    if typ == 'OnLine':
        pfx = '7119' if reg == 'ID' else ('7114' if reg == 'IND' else '7115')
        return f"{pfx}{uid_hex}{ts_hex}00000000{enc_len}{enc}"
    pfx = '9219' if reg == 'ID' else ('9214' if reg == 'IND' else '9215')
    return f"{pfx}{uid_hex}{ts_hex}{enc_len}{enc}"

async def send_keep_alive(region="ID"):
    try:
        reg = str(region).upper() if region else "ID"
        return bytes.fromhex("0219" if reg == "ID" else ("0214" if reg == "IND" else "0215"))
    except Exception:
        return bytes.fromhex("0219")

BR_HEX = (
    "080112800a0a010110013a110a044944433110aa011a064555524f50453a100a044944433210311a064555524f5045"
    "40014a0801090a0b1219202758016291090a80013038384638324246303241393637363730323031303130303030"
    "30303030303030303030303030303031363030303130303135303030323232463937454545304630303030303034363736323531"
    "34303030303030303030303030303030303030303030303030303030303030303030303030306666303030303030"
    "3030636163666131366410241afb02735d5e571400024a775d45414d1a041b1c001f11010449715f4243481a001e"
    "1d071c1703004b1a4066785c524570735c51486775421b5c5a4c07504042685a63610816054e19025e7519600147"
    "7c015165406370195f5547404e4550640103020f1304064863754268676c755f65576e40467e5f0a417a4701026d"
    "675d6e73670b1108495a4c6a0b78470b740065645e525a057258425f584a447d4e6759440c11044e7c596d7f4b62"
    "5f7d04055a47505c4e1d6b5b4107447d7201057d7f0f14084e430457674f7e517d72015172415d027473577c4d61"
    "5f79535256780911030f4d5e027a797f614165067806505d53777750475e75064257076500460817014e741e7e50"
    "78487e7a7c465e7669767153497064605a7376677773550d160148037e18675966787f4c42607a645f577e7b44"
    "1b460776026b18685d0b110205490060020f70676175654674706671797f41067346677c4e06585e780f15074c57"
    "047b40517075415f6364027259674b5b0166407f7340600407770a22047a5d5c52300b3a0a167305067162727516"
    "134208312e3133302e3232480350015ae90403626253513635686e556f4e36416456324b796f566c636f47777648"
    "4f624e56526c4d727073504b4f43654177616848494176795556497273743752737149734a7a786b324752526837"
    "7a2f637664626d504f6a73552f79626d38547a4c69586d2f474351696d494b53486833447955726f39515152756c"
    "34545350626d6d624b7949565937545671577059455372323646572f59624578507338514f706d317372785455736c"
    "30796a434144444d4f34616a654b615753366361496c554b4963797a494e396d52516f715277687939797257476d"
    "337a644345337a6a61436f492f5a585233656f65365a42647a64677654636b6b665733356e4d4c6a6a56507256"
    "4b6433523172756174394e50514150724a5546627859696c4c5a3859707336654d5447666b6649793574666a526c"
    "314d4648706b51774c6373374439656378566c41636f374e664f6d2b30654756466c443474447870677138553359"
    "5973587645384842502f70666c767a737138316a32524f4d7857437556445442492f684735625462773166456e42"
    "49725162762b636144775147696f74554e316d4c4b77734379456f4766706746614251457645672b736a764c4c78"
    "704743334c304a5344532f74526169504354553344374e6249306547516651622f5a466f4c36455630775a324d6f"
    "583932414c572f5049752f56634663584e70596b356f7966326151416a536971486a2f363276354843644f525551"
    "303578754e6171795251625653704654303137655237675255636b4966366c6f447476342b514e4a4670766d7475"
    "7077707774396a5a5974437a4b56743657726d6e36785837706658456251555434684f3758a201050803108703a2"
    "01050804108103a20105080510c001a20105081d10cc01a2010408161078a20105080e10af01a201020815"
)

async def start_game_battle_royale(region, client_version, writer, key, iv):
    packet = bytes.fromhex(BR_HEX)
    try:
        if CguFF_pb2 is not None:
            proto = CguFF_pb2.StartMatch(); proto.ParseFromString(packet)
            if hasattr(proto.main, 'region_list') and len(proto.main.region_list) > 0:
                proto.main.region_list[0].region = region
                if len(proto.main.region_list) > 1: proto.main.region_list[1].region = region
            if hasattr(proto.main, 'client_version'):
                proto.main.client_version.remote_version = client_version
            packet = proto.SerializeToString()
    except Exception: pass
    enc = (await aes_encrypt(packet, key, iv)).hex()
    plen = len(enc) // 2
    hl = hex(plen)[2:]
    hl = hl if len(hl) > 1 else "0" + hl
    reg = str(region).upper() if region else "BD"
    pfx = "031500" if reg == "ID" else ("031400" if reg == "IND" else "031500")
    final = pfx + "0" * (6 - len(hl)) + hl + enc
    writer.write(bytes.fromhex(final)); await writer.drain()
    print_info(f"[BR] search sent ({plen}B) R={reg}")

async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while z >= 0x80: out.append((z & 0x7F) | 0x80); z >>= 7
    out.append(z); return bytes(out)

async def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

async def zigzag_encode_signed(n):
    try: n = int(n)
    except Exception: n = 0
    zz = (n << 1) ^ (n >> 63)
    if zz < 0: zz = -zz
    out = bytearray()
    while True:
        b = zz & 0x7F; zz >>= 7
        if zz: b |= 0x80
        out.append(b)
        if not zz: break
    return bytes(out)

async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1

async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

async def tea_cbc_encrypt(padded, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(padded)); pc = bytearray(8); pi = bytearray(8)
    for i in range(0, len(padded), 8):
        x = bytearray(8)
        for j in range(8): x[j] = padded[i+j] ^ pc[j]
        e0,e1 = await tea_enc(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0); struct.pack_into("<I", enc, 4, e1)
        for j in range(8): out[i+j] = enc[j] ^ pi[j]
        pc[:] = out[i:i+8]; pi[:] = x
    return bytes(out)

async def tea_cbc_decrypt(body, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(body)); pi = bytearray(8); pc = bytearray(8)
    x = bytearray(8); dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8): x[j] = body[i+j] ^ pi[j]
        d0,d1 = await tea_dec(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        struct.pack_into("<I", dec, 0, d0); struct.pack_into("<I", dec, 4, d1)
        for j in range(8): out[i+j] = dec[j] ^ pc[j]
        pc[:] = body[i:i+8]; pi[:] = dec
    return bytes(out)

async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7

async def encode_header(layout, so, cmd, oid, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:length}[code]
        if _FIELD_SIZES[code] == 1: out.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF); out.append((v >> 8) & 0xFF)
    return bytes(out)

async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf: c = CRC7_TABLE[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

async def sv_frame(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0]) + await encode_header(layout, so, cmd, oid, flags, len(body), k, v80)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:len(body)}[code]
        if _FIELD_SIZES[code] == 1: hdr.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF); hdr.append((v >> 8) & 0xFF)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    nr = [c for c in ru if c != 2]
    return ru, nr

async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    if len(data) > 25: raise ValueError("too long")
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    k = key[0] if key else 10
    v80 = ((k << 8) | k) & 0xFFFF
    layout = [int(c) for c in str(layout).strip()] if isinstance(layout, str) else list(layout)
    padded = await build_padded(content)
    enc_body = await tea_cbc_encrypt(padded, key)
    hdr = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    pkt = bytearray([0x63, 0x00]) + hdr + enc_body
    pkt[1] = await crc7_buff(0, pkt[2:]) & 0x7F
    return bytes(pkt).hex()

async def classify(frame):
    cmd = frame["cmd"]
    name = MESSAGE_ID_TO_NAME.get(cmd, f"UNKNOWN_{cmd}")
    if name == "UDP_HELLO": return "HELLO"
    if name == "UDP_ACK": return "ACK"
    if name == "UDP_PING": return "PING"
    if name == "RUDP_JOIN_MATCH": return "JOIN_MATCH"
    if name.startswith("RUDP_"): return name
    if name.startswith("UDP_"): return name
    return "DATA"

async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    _, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        if ack_style == "echo":
            content = frame["content"] if frame["content"] else b"\x10\x00\x00\x00"
            return typ, await build_packet(hello_key, nr, 1, 1, None, 1, content, key)
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        content = frame["content"] if frame["content"] else b"\x01\x00"
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, content, key)
    if typ == "PING":
        c = frame["content"]
        counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0, counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None

async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    nr = (await layouts_from_mask(mask))[1]
    ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
    loop = asyncio.get_event_loop(); i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]
        counter = int(time.time() * 1000) & 0xFFFFFFFF
        pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00",
                                 key_bytes, encrypted=False)
        try: await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception: pass
        i += 1
        try: await asyncio.wait_for(stop_event.wait(), timeout=bypass_packet_jitter(3.0, 0.4))
        except asyncio.TimeoutError: pass

async def try_header(buf, layout, k, v80):
    off = 2; out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf): return None
        out[_FIELD_NAMES[code]] = ((buf[off] ^ k) if size == 1
                                    else ((buf[off] | (buf[off+1] << 8)) ^ v80) & 0xFFFF)
        off += size
    out["headerLen"] = off
    return out

async def oicq_unpad(padded):
    if not padded or len(padded) < 8: return None
    if not all(padded[-1-i] == 0 for i in range(7)): return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len; e = len(padded) - 7
    return padded[s:e] if s < e else b""

async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    candidates = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0,1,2,3,4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0,1,3,4])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f: continue
        if f["flags"] > 7 or f["sendOption"] > 7: continue
        if f["length"] != len(data) - f["headerLen"]: continue
        body = data[f["headerLen"]:f["headerLen"]+f["length"]]
        content = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            padded = await tea_cbc_decrypt(body, key)
            content = await oicq_unpad(padded)
            if content is None: continue
        else: content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        candidates.append({"kind":kind, "layout":layout, "headerLen":f["headerLen"],
            "msgKey":data[0], "cmd":f["cmd"], "flags":f["flags"],
            "sendOption":f["sendOption"], "orderId":f.get("orderId"),
            "length":f["length"], "content":content, "crcOk":crc_ok,
            "score":score, "total":len(data)})
    if not candidates: return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]

async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val,
                                      server_ip="", region="ID", client_version="1.132.6",
                                      client_version_code="2019121229", access_token="",
                                      mode_id=BR_MODE_ID, map_id=BR_MAP_ID):
    token = token.strip()
    udp_key = bytes.fromhex(udp_key)
    match_code = [int(ch) for ch in str(match_code).strip()]
    thunder_jwt = token[:660] if len(token) > 660 else token
    sharma_jwt = token[660:] if len(token) > 660 else ""
    eth = thunder_jwt.encode() if isinstance(thunder_jwt, str) else thunder_jwt
    esh = sharma_jwt.encode() if isinstance(sharma_jwt, str) else sharma_jwt
    garena420 = await has_ssan_zig(len(eth)) + eth
    reg = str(region).upper() if region else "ID"
    csoversea_block = bytes.fromhex(
        "ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d"
        "3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e"
        "3137302e3233303b33352e3138352e3138332e35370000000000000100000000000000000000000001"
        "00000800000100000000000100a8a2d7bebd8d8bdf110200")
    mid = bytes.fromhex('0000000001000102030101') + await has_ssan_zig(len(reg)) + reg.encode()
    mid += bytes.fromhex('0001030003000004')
    mid += await has_ssan_zig(len(client_version)) + client_version.encode()
    mid += await has_ssan_zig(len(client_version_code)) + client_version_code.encode()
    mid += csoversea_block
    clean_ip = server_ip.split(':')[0] if server_ip else "0.0.0.0"
    mid += await has_ssan_zig(len(clean_ip)) + clean_ip.encode()
    if access_token:
        clean_acc = access_token.strip()
        mid += await has_ssan_zig(len(clean_acc)) + clean_acc.encode()
    mid += await has_ssan_zig(len(esh)) + esh
    tg = (await uleb_encode(int(account_id)) + await uleb_encode(int(block_val)) +
          await uleb_encode(1) + await uleb_encode(int(mode_id)) +
          await uleb_encode(int(block_val)) + await uleb_encode(int(map_id)) + mid)
    process = await sv_frame(0x5E, match_code, 2, 447, 0, 1, garena420, udp_key)
    loading = await sv_frame(0x5A, match_code, 2, 448, 1, 1, tg, udp_key)
    return process.hex(), loading.hex()

# ═══════════════════════════════════════════════════════════════════
#  MOVEMENT PRIMITIVES + MoveState
# ═══════════════════════════════════════════════════════════════════
def read_varint(data: bytes, offset: int) -> Tuple[int, int]:
    r, s = 0, 0
    while True:
        if offset >= len(data):
            raise IndexError("offset out of bounds")
        b = data[offset]
        offset += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80):
            break
        s += 7
    return r, offset

MSG_PLAYER_STATE_SYNC = next(
    (mid for mid, name in MESSAGE_ID_TO_NAME.items() if name == "UDP_PLAYER_STATE_SYNC"),
    2001,
)

async def zigzag_encode(n):
    z = ((n << 1) ^ (n >> 63)) & 0xFFFFFFFFFFFFFFFF
    return await uleb_encode(z)

def zigzag_decode(n):
    return (n >> 1) ^ -(n & 1)

def read_varints(buf):
    out = []
    off = 0
    while off < len(buf):
        v, off = read_varint(buf, off)
        out.append(v)
    return out

def float_to_u32(f):
    return struct.unpack("<I", struct.pack("<f", float(f) + 0.0))[0]

class MoveState:
    def __init__(self):
        self.session_start = time.time()
        self.slot = None
        self.server_pos = None
        self.server_physx_state = None
        self.server_vel_y = 0
        self.server_update_seq = 0
        self.pending_ack = None
        self.rtt_ms = None
        self.ping_sent = {}
        self.cmd_counts = collections.Counter()
        self.undecoded = 0
        self.last_2001_head = None
        self.owner_uid = None
        self.slot_registered = False
        self.enemy_positions = {}
        self.last_enemy_log = 0.0

    def diagnostics(self):
        top = ", ".join(f"{c}x{n}" for c, n in self.cmd_counts.most_common(10)) or "none"
        return (f"cmds[{top}] | undecoded {self.undecoded} | "
                f"2001 seq {self.server_update_seq} | slot {self.slot} | "
                f"enemies_known {len(self.enemy_positions)}")

    def on_server_frame(self, frame):
        self.cmd_counts[frame["cmd"]] += 1
        if frame.get("kind") == "RUDP" and frame.get("orderId") is not None:
            oid = frame["orderId"]
            if self.pending_ack is None or ((oid - self.pending_ack) & 0xFFFF) < 0x8000:
                self.pending_ack = oid
        if frame["cmd"] == MSG_PLAYER_STATE_SYNC:
            self._on_own_state(frame["content"] or b"")
        elif frame["cmd"] == 3:
            c = frame["content"] or b""
            if len(c) >= 4:
                sent = self.ping_sent.pop(struct.unpack_from("<I", c, 0)[0], None)
                if sent is not None:
                    self.rtt_ms = int((time.time() - sent) * 1000)

    def _on_own_state(self, content):
        try:
            v = read_varints(content)
        except Exception:
            self.last_2001_head = f"unparseable {content[:12].hex()}"
            return
        self.last_2001_head = v[:4]
        if len(v) < 16 or v[0] != 0 or v[1] != 2:
            return
        self.slot = v[2]
        self.server_pos = (zigzag_decode(v[3]), zigzag_decode(v[4]), zigzag_decode(v[5]))
        self.server_vel_y = zigzag_decode(v[12])
        self.server_physx_state = v[14]
        self.server_update_seq += 1
        if not self.slot_registered and self.owner_uid:
            self.slot_registered = True
            try:
                asyncio.create_task(_account_register_slot(self.owner_uid, self.slot))
            except Exception: pass
        try:
            self._try_parse_extra_players(v)
        except Exception: pass

    def _try_parse_extra_players(self, v):
        own = self.slot
        idx = 27
        hits = []
        while idx + 3 < len(v):
            slot = v[idx]
            if 1 <= slot <= 50 and slot != own:
                try:
                    px = zigzag_decode(v[idx+1])
                    py = zigzag_decode(v[idx+2])
                    pz = zigzag_decode(v[idx+3])
                    if (-10000 <= px <= 10000 and -2000 <= py <= 5000
                            and -10000 <= pz <= 10000):
                        hits.append((slot, (px, py, pz)))
                        idx += 4
                        continue
                except Exception: pass
            idx += 1
        if hits:
            now = time.time()
            for slot, p in hits:
                self.enemy_positions[slot] = (p[0], p[1], p[2], now)
                try:
                    async def _push_if_enemy(s, pos):
                        if await _account_is_teammate_slot(s): return
                        await _account_register_enemy(self.owner_uid, f"en{s}", pos)
                    asyncio.create_task(_push_if_enemy(slot, p))
                except Exception: pass
            if now - self.last_enemy_log > 1.0:
                self.last_enemy_log = now
                print_info(f"[HUNT-PARSE {self.owner_uid}] {len(hits)} candidate(s) total={len(self.enemy_positions)}")


async def build_player_state_sync_2001(key_bytes, mask, msg_key, slot, pos, stick, move_input, vel,
                                     physx_state, physx_pose, facing, net_tick, counter_ms,
                                     ack_order=None):
    body = bytearray()
    body += await uleb_encode((1 << 24) | int(slot))
    for value in (*pos, *stick, *move_input, *vel):
        body += await zigzag_encode(int(round(value)))
    body += await uleb_encode(int(physx_state))
    body += await uleb_encode(int(physx_pose))
    for f in facing:
        body += await uleb_encode(float_to_u32(f))
    body += b"\x00\x00"
    body += await uleb_encode(int(net_tick))
    body += b"\x00\x00\x00"
    body += await uleb_encode(int(counter_ms))
    body = bytes(body)

    k = key_bytes[0]
    v80 = ((k << 8) | k) & 0xFFFF
    flags = 4 if ack_order is not None else 0
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, MSG_PLAYER_STATE_SYNC, None, flags, len(body), k, v80)
    if ack_order is not None:
        a = ((int(ack_order) & 0xFFFF) ^ v80) & 0xFFFF
        hdr += bytes([a & 0xFF, a >> 8, k])
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)

async def build_action_beacon_2002(key_bytes, mask, msg_key, slot, pos, action_type=1, ack_order=None):
    body = bytearray()
    body += await uleb_encode((2 << 24) | int(slot))
    body += await zigzag_encode(int(pos[0]))
    body += await zigzag_encode(int(pos[2]))
    body += await uleb_encode(int(action_type))
    body += b"\x00\x00"
    k = key_bytes[0]; v80 = ((k << 8) | k) & 0xFFFF
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, 2002, None, 4 if ack_order else 0, len(body), k, v80)
    if ack_order:
        a = ((int(ack_order) & 0xFFFF) ^ v80) & 0xFFFF
        hdr += bytes([a & 0xFF, a >> 8, k])
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def build_position_heartbeat_2003(key_bytes, mask, msg_key, slot, pos, ack_order=None):
    body = bytearray()
    body += await uleb_encode((3 << 24) | int(slot))
    for v in (pos[0], pos[1], pos[2]):
        body += await zigzag_encode(int(v))
    body += b"\x00\x00\x00\x00"
    k = key_bytes[0]; v80 = ((k << 8) | k) & 0xFFFF
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, 2003, None, 4 if ack_order else 0, len(body), k, v80)
    if ack_order:
        a = ((int(ack_order) & 0xFFFF) ^ v80) & 0xFFFF
        hdr += bytes([a & 0xFF, a >> 8, k])
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def build_extra_ping_cmd3(key_bytes, mask, msg_key, counter):
    body = struct.pack("<I", counter & 0xFFFFFFFF) + b"\x00\x00\x00"
    k = key_bytes[0]; v80 = ((k << 8) | k) & 0xFFFF
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, 3, None, 0, len(body), k, v80)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def auto_move_loop(sock, ip, port, key_bytes, mask, state, stop_event, label=""):
    loop = asyncio.get_event_loop()
    my_uid = state.owner_uid

    async def wait(seconds):
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False

    # ── Wait for spawn (own-state 2001 landed) ──
    next_report = time.time() + AUTO_MOVE_SPAWN_TIMEOUT
    landed_deadline = None
    force_started = False
    while True:
        if state.slot is not None and state.server_pos is not None:
            if landed_deadline is None:
                landed_deadline = time.time() + AUTO_MOVE_LAND_TIMEOUT
            if (state.server_physx_state == 0 and state.server_vel_y == 0) or time.time() > landed_deadline:
                break
        elif time.time() > next_report:
            # ★ FORCE START — synthesize spawn so 4th player still moves
            if not force_started:
                force_started = True
                print_warning(f"[MOVE]{label} ⚠ own-state timeout — FORCE-START with synthetic spawn: {state.diagnostics()}")
                state.slot = state.slot or 1
                state.server_pos = state.server_pos or (0, 0, 0)
                state.server_physx_state = 0
                state.server_vel_y = 0
                break
        if await wait(0.2):
            return
    if await wait(AUTO_MOVE_START_DELAY):
        return

    if state.slot is None: state.slot = 1
    if state.server_pos is None: state.server_pos = (0, 0, 0)
    try:
        await _account_register_slot(my_uid, state.slot)
    except Exception: pass

    pos = list(state.server_pos)
    seen_seq = state.server_update_seq
    heading = random.uniform(-math.pi, math.pi)
    stick = (math.sin(heading) * 100, 0.0, math.cos(heading) * 100)
    last_send = time.time()
    last_pos = tuple(pos)
    stuck_timer = 0.0
    last_stuck_log = 0.0
    stuck_events = 0

    afk_decision_at  = time.time() + ANTI_AFK_DECISION_SEC
    afk_jump_at      = time.time() + ANTI_AFK_JUMP_EVERY
    cur_state        = "run"
    cur_speed_update = time.time()
    speed_mult       = 1.0
    circle_angle     = random.uniform(-math.pi, math.pi)
    circle_dir       = random.choice([-1, 1])

    # Glory Boost State
    last_glory_ping    = 0.0
    last_action_beacon = 0.0
    last_pos_hb        = 0.0
    last_pose_cycle    = 0.0

    print_success(f"[XIRUS]{label} ONLINE uid={my_uid} slot={state.slot} spawn={[round(x) for x in pos]}")

    while not stop_event.is_set():
        now = time.time()
        dt_ms = (now - last_send) * 1000.0
        last_send = now

        if state.server_update_seq != seen_seq and state.server_pos:
            seen_seq = state.server_update_seq
            sx, sy, sz = state.server_pos
            if math.hypot(sx - pos[0], sz - pos[2]) > AUTO_MOVE_RESYNC_DISTANCE:
                print_info(f"[MOVE]{label} server-resync -> {state.server_pos}")
                pos = [sx, sy, sz]

        moved = math.hypot(pos[0] - last_pos[0], pos[2] - last_pos[2])
        if moved < 4.0:
            stuck_timer += AUTO_MOVE_TICK_INTERVAL
        else:
            if stuck_timer > STUCK_THRESHOLD:
                print_success(f"[STUCK]{label} escaped after {stuck_timer:.1f}s")
                stuck_events += 1
            stuck_timer = 0.0
            last_pos = tuple(pos)
        if stuck_timer > STUCK_THRESHOLD and (now - last_stuck_log) > STUCK_LOG_COOLDOWN:
            last_stuck_log = now
            my_target = await _account_get_target(my_uid)
            print_warning(
                f"[STUCK]{label} STUCK {stuck_timer:.1f}s @ {[round(x) for x in pos]} "
                f"| slot={state.slot} physx={state.server_physx_state} velY={state.server_vel_y} "
                f"| target={my_target[0]} | stuck={stuck_events}")

        my_target, my_target_set_at = await _account_get_target(my_uid)
        target_age = (now - my_target_set_at) if my_target else 999

        nearest = await _account_nearest_enemy(my_uid, pos)
        if nearest is not None:
            my_target = nearest
            if target_age > 1.5:
                print_info(f"[SQUAD]{label} enemy-lock {[round(x) for x in nearest]}")

        if my_target is None or (target_age > SQUAD_TARGET_TIMEOUT and nearest is None):
            ang = random.uniform(-math.pi, math.pi)
            dist = random.uniform(1200, AUTO_MOVE_RADIUS)
            new_t = (pos[0] + math.sin(ang) * dist, pos[1],
                     pos[2] + math.cos(ang) * dist)
            await _account_set_target(my_uid, new_t)
            my_target = new_t
            print_info(f"[SQUAD]{label} new target {[round(x) for x in new_t]}")

        if ENABLE_SPEED_MOVEMENT and (now - cur_speed_update) >= MOVEMENT_UPDATE_SPEED_EVERY:
            cur_speed_update = now
            speed_mult = random.uniform(MOVEMENT_SPEED_MIN, MOVEMENT_SPEED_MAX)

        if now >= afk_decision_at:
            afk_decision_at = now + ANTI_AFK_DECISION_SEC
            weights = [
                ("idle",   MOVEMENT_STATE_IDLE_CHANCE),
                ("walk",   MOVEMENT_STATE_WALK_CHANCE),
                ("run",    MOVEMENT_STATE_RUN_CHANCE),
                ("sprint", MOVEMENT_STATE_SPRINT_CHANCE),
                ("jump",   MOVEMENT_STATE_JUMP_CHANCE),
                ("crouch", MOVEMENT_STATE_CROUCH_CHANCE),
                ("prone",  MOVEMENT_STATE_PRONE_CHANCE),
            ]
            total_w = sum(w for _, w in weights)
            r = random.uniform(0, total_w)
            acc = 0.0
            cur_state = "run"
            for name, w in weights:
                acc += w
                if r <= acc:
                    cur_state = name
                    break
            if random.random() < ANTI_AFK_IDLE_CHANCE:
                heading += random.uniform(-math.pi, math.pi)
                stick = (math.sin(heading) * 100, 0.0, math.cos(heading) * 100)

        move_input = (0, 0)
        vel = (0, 0, 0)
        pose = 0
        chasing = False

        if my_target is not None:
            dx = my_target[0] - pos[0]; dz = my_target[2] - pos[2]
            remain = math.hypot(dx, dz)
            if remain < SQUAD_ARRIVAL_RADIUS:
                await _account_clear_target(my_uid, only_if=my_target)
                my_target = None
            else:
                chasing = True
                speed = AUTO_MOVE_RUN_SPEED * speed_mult
                step = speed * dt_ms / 100.0
                want = math.atan2(dx, dz)
                diff = (want - heading + math.pi) % (2 * math.pi) - math.pi
                max_turn = math.radians(AUTO_MOVE_TURN_PER_TICK)
                heading += max(-max_turn, min(max_turn, diff))
                ux, uz = math.sin(heading), math.cos(heading)
                stick = (ux * 100, 0.0, uz * 100)
                move_input = (stick[0], stick[2])
                vel = (ux * speed, 0, uz * speed)
                pose = MOVE_STATE_MAP.get("run", 2)
                pos[0] += ux * step
                pos[2] += uz * step

        if not chasing:
            if cur_state == "idle":
                move_input = (0, 0)
                vel = (0, 0, 0)
                pose = PLAYER_STATE_MAP["idle"]
            else:
                if MOVEMENT_PATTERN == "circle":
                    circle_angle += circle_dir * (MOVEMENT_TICK_MS / 1000.0) * 1.2
                    radius = MOVEMENT_RADIUS
                    wander_x = pos[0] + math.sin(circle_angle) * radius
                    wander_z = pos[2] + math.cos(circle_angle) * radius
                else:
                    if random.random() < 0.05:
                        heading += random.uniform(-math.pi / 3, math.pi / 3)
                    wander_x = pos[0] + math.sin(heading) * MOVEMENT_RADIUS
                    wander_z = pos[2] + math.cos(heading) * MOVEMENT_RADIUS

                dx = wander_x - pos[0]; dz = wander_z - pos[2]
                if abs(dx) + abs(dz) < 1.0:
                    dx, dz = math.sin(heading), math.cos(heading)
                want = math.atan2(dx, dz)
                diff = (want - heading + math.pi) % (2 * math.pi) - math.pi
                heading += max(-math.radians(15), min(math.radians(15), diff))
                ux, uz = math.sin(heading), math.cos(heading)

                speed = STATE_SPEED.get(cur_state, 70) * speed_mult
                step = speed * dt_ms / 100.0
                stick = (ux * 100, 0.0, uz * 100)
                move_input = (stick[0], stick[2])
                vel = (ux * speed, 0, uz * speed)
                pose = MOVE_STATE_MAP.get(cur_state, 1)
                pos[0] += ux * step
                pos[2] += uz * step

            if now >= afk_jump_at:
                afk_jump_at = now + ANTI_AFK_JUMP_EVERY
                pose = PLAYER_STATE_MAP["jump"]

        facing = (math.sin(heading), 0.0, math.cos(heading))
        rtt = state.rtt_ms if state.rtt_ms is not None else AUTO_MOVE_DEFAULT_RTT
        ack = None
        if AUTO_MOVE_PIGGYBACK_ACK and state.pending_ack is not None:
            ack, state.pending_ack = state.pending_ack, None
        try:
            pkt = await build_player_state_sync_2001(
                key_bytes, mask, random.choice(AUTO_MOVE_MSG_KEYS), state.slot,
                pos, stick, move_input, vel, 0, pose, facing,
                max(1, min(1000, rtt)),
                int((now - state.session_start) * 1000),
                ack_order=ack)
            await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception as e:
            print_warning(f"[MOVE]{label} send err: {e}")

        # ★★★ GLORY BOOST PACKETS (60 Glory Fix) ★★★
        if GLORY_BOOST_ENABLED:
            # 1. Extra cmd=3 ping (Uptime glory)
            if now - last_glory_ping >= GLORY_PING_EVERY:
                last_glory_ping = now
                try:
                    p = await build_extra_ping_cmd3(
                        key_bytes, mask, random.choice(GLORY_MSG_KEYS),
                        int(now * 1000) & 0xFFFFFFFF)
                    await loop.sock_sendto(sock, p, (ip, port))
                except Exception: pass

            # 2. Fake Shoot/Loot Action (cmd=2002)
            if now - last_action_beacon >= GLORY_ACTION_EVERY:
                last_action_beacon = now
                try:
                    action_type = random.choice([1, 2, 3, 4]) # 1=shoot, 2=damage, 3=loot
                    b = await build_action_beacon_2002(
                        key_bytes, mask, random.choice(GLORY_MSG_KEYS),
                        state.slot, pos, action_type=action_type)
                    await loop.sock_sendto(sock, b, (ip, port))
                except Exception: pass

            # 3. Position Heartbeat (cmd=2003)
            if now - last_pos_hb >= GLORY_ACTION_EVERY:
                last_pos_hb = now
                try:
                    hb = await build_position_heartbeat_2003(
                        key_bytes, mask, random.choice(GLORY_MSG_KEYS),
                        state.slot, pos)
                    await loop.sock_sendto(sock, hb, (ip, port))
                except Exception: pass

            # 4. Pose Cycling (walk, run, jump - server ko active lagne ke liye)
            if now - last_pose_cycle >= 1.2:
                last_pose_cycle = now
                pose = random.choice([
                    PLAYER_STATE_MAP["walk"],
                    PLAYER_STATE_MAP["run"],
                    PLAYER_STATE_MAP["sprint"],
                    PLAYER_STATE_MAP["jump"],
                ])

        if await wait(GLORY_TICK_INTERVAL if GLORY_BOOST_ENABLED else AUTO_MOVE_TICK_INTERVAL):
            return

async def play_game(server_ip_port, thunder, sharma, udp_key, match_code,
                    account_id, player_region, client_version, key, iv,
                    match_index, on_match_complete=None):
    t0 = time.time()
    ping_task = None
    move_task = None
    sock = None
    ping_stop = asyncio.Event()
    move_stop = asyncio.Event()
    uid_str = str(account_id)
    completed = False
    move_state = MoveState()
    move_state.owner_uid = uid_str

    try:
        ip, port = server_ip_port.split(":"); port = int(port)
        rip = await resolve_host_cloudflare(ip)
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: sock.bind(('0.0.0.0', 0))
        except Exception: pass
        optimize_udp_socket(sock); sock.setblocking(False)
        udp_key_bytes = bytes.fromhex(udp_key)

        await asyncio.sleep(bypass_hello_delay())
        hello = await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)
        await loop.sock_sendto(sock, bytes.fromhex(hello), (rip, port))

        ack_state = "waiting_for_hello_reply"
        thunder_sent = False
        thunder_retries = 0
        join_match_rcv = False
        local_closed = False
        send_lock = asyncio.Lock()
        move_started = False

        ping_task = asyncio.create_task(
            keepalive_ping(sock, rip, port, udp_key_bytes, match_code, ping_stop))
        last_activity = time.time()
        print_colored(f"[MATCH #{match_index}] UDP -> {server_ip_port} (DNS:{rip} UID:{uid_str})", Colors.MAGENTA)

        async def start_movement_worker():
            nonlocal move_task, move_started
            if move_started: return
            move_started = True
            if not AUTO_MOVE_ENABLED:
                print_warning(f"[MOVE] AUTO_MOVE_ENABLED=False -> #{match_index} no movement")
                return
            move_task = asyncio.create_task(auto_move_loop(
                sock, rip, port, udp_key_bytes, match_code,
                move_state, move_stop,
                label=f"#{match_index}:{account_id}"
            ))
            print_success(f"[MOVE] started for #{match_index} (UID:{account_id})")

        async def send_startup():
            nonlocal ack_state, thunder_sent, thunder_retries
            if thunder_sent and thunder_retries >= 2: return
            async with send_lock:
                try:
                    await loop.sock_sendto(sock, bytes.fromhex(thunder), (rip, port))
                    thunder_sent = True
                    thunder_retries += 1
                    await asyncio.sleep(bypass_jitter(0.1, 0.05))
                    _, nr = await layouts_from_mask(match_code)
                    ack = await build_packet(0x68, nr, 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                    await loop.sock_sendto(sock, ack, (rip, port))
                    await asyncio.sleep(bypass_jitter(0.2, 0.05))
                    await loop.sock_sendto(sock, bytes.fromhex(sharma), (rip, port))
                    ack_state = "thunder_sharma_sent"
                    print_success(f"[MATCH #{match_index}] Startup delivered (UID:{account_id} retry={thunder_retries})")
                    await start_movement_worker()
                except Exception as e:
                    print_error(f"[MATCH #{match_index}] startup: {e}")

        # ★ SAFETY NET: Force movement start 10s after handshake begins
        async def force_move_after_delay():
            await asyncio.sleep(10.0)
            if not move_started:
                print_warning(f"[MOVE] #{match_index} FORCE-START (10s fallback) for UID:{account_id}")
                await start_movement_worker()
        force_move_task = asyncio.create_task(force_move_after_delay())

        while not local_closed:
            if time.time() - t0 > MAX_MATCH_DURATION:
                print_info(f"[MATCH #{match_index}] 15-minute cap reached — closing UDP")
                break
            try:
                resp, saddr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if resp:
                    last_activity = time.time()
                    frame = await decode_packet(resp, udp_key_bytes, match_code)

                    if frame and move_state is not None:
                        try:
                            move_state.on_server_frame(frame)
                        except Exception: pass

                    if frame:
                        pt = await classify(frame)
                        if frame['cmd'] in [103, 107]:
                            print_success(f"[MATCH #{match_index}] END cmd={frame['cmd']}")
                            completed = True; local_closed = True; continue
                        if frame['cmd'] == 101:
                            try:
                                _, nr = await layouts_from_mask(match_code)
                                a = await build_packet(0x68, nr, 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                                await loop.sock_sendto(sock, a, saddr)
                            except Exception: pass
                            continue
                        if pt in ["ACK", "PING", "HELLO", "JOIN_MATCH"]:
                            if pt == "HELLO" and ack_state == "waiting_for_hello_reply":
                                _, r = await reply_for(frame, udp_key_bytes, match_code, ack_style="short")
                                if r: await loop.sock_sendto(sock, r, saddr)
                                ack_state = "ack_sent_waiting"
                            elif pt == "ACK":
                                if ack_state == "waiting_for_hello_reply":
                                    _, r = await reply_for(frame, udp_key_bytes, match_code)
                                    if r: await loop.sock_sendto(sock, r, saddr)
                                    ack_state = "ready_to_send_thunder"
                                elif ack_state == "ack_sent_waiting":
                                    ack_state = "ready_to_send_thunder"
                                else:
                                    _, r = await reply_for(frame, udp_key_bytes, match_code)
                                    if r: await loop.sock_sendto(sock, r, saddr)
                            elif pt == "PING":
                                _, r = await reply_for(frame, udp_key_bytes, match_code)
                                if r: await loop.sock_sendto(sock, r, saddr)
                            elif pt == "JOIN_MATCH" and not join_match_rcv:
                                _, r = await reply_for(frame, udp_key_bytes, match_code)
                                if r: await loop.sock_sendto(sock, r, saddr); join_match_rcv = True
            except asyncio.TimeoutError:
                if ack_state == "ready_to_send_thunder" and not thunder_sent:
                    await send_startup()
                elif ack_state == "waiting_for_hello_reply":
                    if (time.time() - last_activity) > 7.0:
                        try:
                            hp = await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)
                            await loop.sock_sendto(sock, bytes.fromhex(hp), (rip, port))
                        except Exception: pass
                        last_activity = time.time()
                    if (time.time() - t0) > 25.0:
                        print_warning(f"[MATCH #{match_index}] Handshake timeout"); break
                elif ack_state == "thunder_sharma_sent":
                    if (time.time() - last_activity) > MATCH_IDLE_TIMEOUT:
                        print_success(f"[MATCH #{match_index}] Finished naturally")
                        completed = True; break
                continue
            except BlockingIOError:
                await asyncio.sleep(0.05)
            except OSError:
                await asyncio.sleep(0.5); continue
            except Exception:
                await asyncio.sleep(0.5); continue
            if ack_state == "ready_to_send_thunder" and not thunder_sent:
                try: await send_startup()
                except Exception: pass
        try: force_move_task.cancel()
        except Exception: pass
        return f"match #{match_index} finished"
    except Exception as e:
        print_error(f"[MATCH #{match_index}] {e}"); return f"match #{match_index} error"
    finally:
        try: force_move_task.cancel()
        except Exception: pass
        if completed or (time.time() - t0) >= MAX_MATCH_DURATION:
            try: bot_state.increment_match(uid_str)
            except Exception: pass
            if on_match_complete:
                try: asyncio.create_task(on_match_complete())
                except Exception: pass

        move_stop.set()
        if move_task:
            move_task.cancel()
            try: await move_task
            except asyncio.CancelledError: pass
            except Exception: pass

        ping_stop.set()
        if ping_task:
            ping_task.cancel()
            try: await ping_task
            except asyncio.CancelledError: pass

        if sock:
            try: sock.close()
            except Exception: pass

        rem = await _dec_match(uid_str)
        total = await _get_total_match_count()
        print_info(f"[MATCH #{match_index}] Closed. UID:{rem} Total:{total}")
        try: bot_state.update_status(uid_str, "IN_MATCH" if rem > 0 else "ONLINE", rem)
        except Exception: pass

async def start_startup_safe(fn):
    try: await fn()
    except Exception: pass

async def _process_social_packet(raw_bytes, account_data, tag="MAIN"):
    try:
        hex_data = raw_bytes.hex()
        candidates = []
        if len(raw_bytes) >= 6:
            plen = raw_bytes[4]
            if 0 < plen <= (len(raw_bytes) - 5):
                try:
                    inner = bytes(raw_bytes[5:5 + plen])
                    d0 = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
                    if d0: candidates.append((5, d0))
                except Exception: pass
        for off in [5, 6, 10, 8, 12, 4, 0]:
            if off >= len(hex_data): continue
            try: inner = bytes.fromhex(hex_data[off:])
            except Exception: continue
            decoded = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
            if decoded: candidates.append((off, decoded))
        if not candidates: return
        candidates.sort(key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0, reverse=True)
        best_off, decoded = candidates[0]
        def _v(c, k):
            if not isinstance(c, dict): return None
            v = c.get(k) if k in c else c.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            return v
        f5w = decoded.get("5") or decoded.get(5) if isinstance(decoded, dict) else None
        f5 = f5w["data"] if isinstance(f5w, dict) and "data" in f5w else f5w
        target = None
        if isinstance(f5, dict):
            for fk in [1, 2, 3, 4, 6]:
                c = _v(f5, fk)
                if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                    target = str(c); break
        if not target: return
        own = str(account_data.get('account_id', '')) if account_data else ''
        if own and target == own: return
        if not _accept_friend_request or not account_data: return
        jwt = account_data.get('token'); srv = account_data.get('server_url')
        rel = account_data.get('release_version'); own_id = account_data.get('account_id')
        if not (jwt and srv and rel and own_id): return
        url = f"{srv.rstrip('/')}/ConfirmFriendRequest"
        fields = {"1": int(target), "2": int(own_id)}
        try:
            payload = bytes.fromhex(encrypt_api(create_proto(fields).hex()))
            hdrs = {
                "authorization": _bearer(jwt),
                "host": srv.replace("https://", "").replace("http://", "").split("/")[0],
                "x-ga": "v1 1", "content-type": "application/x-www-form-urlencoded",
                "accept-encoding": "deflate, gzip", "releaseversion": f"{rel}",
                "user-agent": "UnityPlayer/2022.3.47f1", "accept": "*/*",
                "x-unity-version": "2022.3.47f1",
            }
            async with httpx.AsyncClient(verify=False, timeout=8.0) as s:
                r = await s.post(url, headers=hdrs, content=payload)
                if r.status_code == 200 and len(r.content) > 0:
                    print_success(f"[FRIEND-{tag}] ✅ {target}")
        except Exception: pass
    except Exception: pass

def _wrap_manual(inner):
    try:
        alt = _decode_proto_manual(inner)
        if alt and len(alt) > 0:
            return {str(k): {"data": v} for k, v in alt.items()}
    except Exception: pass
    return None

async def _handle_team_invite(hex_data, pl, uid_str, current_account_data,
                              current_key, current_iv, writer):
    try:
        if DEBUG_TEAM_PACKETS:
            print_info(f"[TEAM-IN {uid_str}] len={pl} hex={hex_data[:80]}")
        candidates = []
        for off in [10, 8, 6, 12, 14, 4, 16, 0, 20, 2]:
            if off >= len(hex_data) or len(hex_data) - off < 4: continue
            try: inner = bytes.fromhex(hex_data[off:])
            except Exception: continue
            dec = decode_protobuf_dict_safe(inner)
            if dec and isinstance(dec, dict) and len(dec) > 0:
                candidates.append((off, "parser", dec)); continue
            alt = _decode_proto_manual(inner)
            if alt and len(alt) > 0:
                candidates.append((off, "manual", {str(k): {"data": v} for k, v in alt.items()}))
        if not candidates: return False
        candidates.sort(key=lambda x: len(x[2]) if isinstance(x[2], dict) else 0, reverse=True)
        best_off, decoder, dec = candidates[0]
        print_info(f"[TEAM-IN {uid_str}] decoded@{best_off}/{decoder} fields={list(dec.keys())[:20]}")
        def _unwrap(d, keys):
            if not isinstance(d, dict): return None
            for k in keys:
                v = d.get(k) if k in d else d.get(str(k))
                if isinstance(v, dict) and "data" in v: return v["data"]
                if isinstance(v, dict): return v
            return None
        target_dict = None
        for kp in [["5"], ["4"], ["6"], ["2"], ["1"]]:
            u = _unwrap(dec, kp)
            if isinstance(u, dict) and len(u) >= 3:
                target_dict = u
                print_info(f"[TEAM-IN {uid_str}] nested@{kp[0]}")
                break
        if target_dict is None: target_dict = dec
        def _g(d, k):
            if not isinstance(d, dict): return None
            v = d.get(k) if k in d else d.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            if isinstance(v, dict):
                for kk in ["1","2","3","4","5","6","7","8"]:
                    vv = v.get(kk) if kk in v else v.get(int(kk))
                    if isinstance(vv, dict) and "data" in vv: return vv["data"]
            return v
        group_id = None
        for k in list(target_dict.keys()):
            c = _g(target_dict, k)
            if isinstance(c, str) and 20 <= len(c) <= 40:
                group_id = c
                print_success(f"[TEAM-IN {uid_str}] 📋 group_id@f{k}: {c[:24]}...")
                break
        if not group_id:
            for k in list(dec.keys()):
                c = _g(dec, k)
                if isinstance(c, str) and 20 <= len(c) <= 40:
                    group_id = c
                    print_success(f"[TEAM-IN {uid_str}] 📋 group_id@root.f{k}: {c[:24]}...")
                    break
        own_acc = str(current_account_data.get('account_id')) if current_account_data else None
        inviter = None
        all_f = list(target_dict.keys()) + list(dec.keys())
        for k in all_f:
            c = _g(target_dict, k) or _g(dec, k)
            if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                if str(c) != uid_str and str(c) != own_acc:
                    inviter = str(c)
                    print_success(f"[TEAM-IN {uid_str}] 👤 inviter@f{k}: {c}")
                    break
        tc = None
        for k in all_f:
            c = _g(target_dict, k) or _g(dec, k)
            if c and str(c).isdigit() and len(str(c)) == 7:
                tc = str(c); break
        if tc:
            async with _team_state["lock"]:
                _team_state["team_code"] = tc
            print_success(f"[TEAM-IN {uid_str}] 📢 Team Code: {tc}")
        is_member = (_team_state["leader_uid"] != uid_str)
        if inviter and group_id and is_member:
            async with _team_state["members_lock"]:
                already = uid_str in _team_state["members"]
            if already:
                return True
            print_success(f"[TEAM-IN {uid_str}] 📨 ACCEPT: inviter={inviter} group={group_id[:16]}...")
            accepted = False
            for attempt in range(3):
                try:
                    acc = accept_team_invite(int(inviter), group_id, current_key, current_iv)
                    if writer and not writer.is_closing():
                        writer.write(acc); await writer.drain()
                        print_success(f"[TEAM-IN {uid_str}] ✅ accept #{attempt+1} ({len(acc)}B)")
                        accepted = True; break
                except Exception as e:
                    print_warning(f"[TEAM-IN {uid_str}] accept err #{attempt+1}: {e}")
                await asyncio.sleep(0.8)
            if accepted:
                await _team_member_join(uid_str)
            return True
        return False
    except Exception as e:
        print_warning(f"[TEAM-IN {uid_str}] error: {e}")
        return False

async def functional_battle_royale(addrs, starter_packet, account_region, client_version,
                                    key, iv, account_id="", account_data=None,
                                    account_level=2, max_reconnects=10):
    reconnects = 0
    ip, port = addrs.split(":")
    play_matches: List[asyncio.Task] = []
    no_response_count = 0
    search_attempts = 0
    last_start_time = 0.0
    uid_str = str(account_id)
    current_level = int(account_level or 2)
    consecutive_parse_failures = 0
    current_token = starter_packet
    current_key = key; current_iv = iv
    current_account_data = account_data
    reconnect_count_total = 0
    region_index = 0
    current_search_region = REGION_ROTATION_LIST[0]
    _writer_ref = {"w": None}
    _team_active = {"flag": True}

    async def trigger_post_match_refresh():
        await asyncio.sleep(EXP_REFRESH_AFTER_MATCH_DELAY)
        try:
            cd = bot_state.account_credentials.get(uid_str)
            if cd: await refresh_account_profile(cd)
        except Exception: pass

    async def _team_coordinator():
        try:
            deadline = time.time() + TEAM_PEER_WAIT_TIMEOUT
            while time.time() < deadline:
                async with _team_state["lock"]:
                    n = len(_team_state["peers"])
                if n >= TEAM_SIZE: break
                if bot_state.is_paused(uid_str): return
                await asyncio.sleep(0.5)
            async with _team_state["lock"]:
                n = len(_team_state["peers"])
                is_leader = (_team_state["leader_uid"] == uid_str)
                peers_snapshot = dict(_team_state["peers"])
            if not is_leader:
                print_info(f"[TEAM] {uid_str} waiting as member...")
                return
            if n < TEAM_SIZE:
                print_warning(f"[TEAM] Only {n}/{TEAM_SIZE} peers")
            else:
                print_success(f"[TEAM] ✅ All {n} peers online")
            await asyncio.sleep(TEAM_READY_DELAY)
            print_success(f"[TEAM] 👑 {uid_str} creating team...")
            async with _team_state["lock"]:
                _team_state["team_code"] = None
                _team_state["pk_code"] = None
            own_id_num = None
            if current_account_data: own_id_num = current_account_data.get('account_id')
            if not own_id_num:
                try: own_id_num = int(uid_str)
                except Exception: own_id_num = 0
            try:
                pkt = create_team(current_key, current_iv, client_version)
                if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                    _writer_ref["w"].write(pkt); await _writer_ref["w"].drain()
                    print_info(f"[TEAM] create_team sent ({len(pkt)}B)")
                    await _team_member_reset(keep_leader=False)
                    await _team_member_join(uid_str)
            except Exception as e:
                print_error(f"[TEAM] create_team: {e}")
            await asyncio.sleep(TEAM_CREATE_WAIT)
            peer_uids = []
            for peer_uid, info in peers_snapshot.items():
                if peer_uid == uid_str: continue
                pa = None
                try: pa = info["data"].get("account_id")
                except Exception: pass
                if not pa: pa = peer_uid
                peer_uids.append(int(pa))
            print_info(f"[TEAM] Will invite {len(peer_uids)} peers: {peer_uids}")
            heartbeat_stop = asyncio.Event()
            async def heartbeat_loop():
                while not heartbeat_stop.is_set():
                    try:
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            pkt = team_fresh(int(own_id_num), current_key, current_iv)
                            _writer_ref["w"].write(pkt); await _writer_ref["w"].drain()
                    except Exception: pass
                    try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError: pass
            hb_task = asyncio.create_task(heartbeat_loop())
            print_success(f"[TEAM] 🎯 Invite-loop start (max {int(TEAM_INVITE_MAX_TIME)}s)")
            invite_start = time.time()
            cycle = 0
            while time.time() - invite_start < TEAM_INVITE_MAX_TIME:
                if not _team_active["flag"]: break
                if bot_state.is_paused(uid_str): break
                cnt = await _team_member_count()
                if cnt >= TEAM_SIZE:
                    print_success(f"[TEAM] 🎉 Full team ({cnt}/{TEAM_SIZE})!")
                    break
                cycle += 1
                for i, tuid in enumerate(peer_uids):
                    async with _team_state["members_lock"]:
                        joined = str(tuid) in _team_state["members"]
                    if joined: continue
                    try:
                        inv = invite_player_in_team(tuid, current_key, current_iv, region=account_region)
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            _writer_ref["w"].write(inv); await _writer_ref["w"].drain()
                            print_success(f"[TEAM] 📨 invite {tuid} cycle#{cycle}")
                    except Exception as e:
                        print_warning(f"[TEAM] invite err: {e}")
                    await asyncio.sleep(0.5)
                try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_INVITE_CYCLE_WAIT)
                except asyncio.TimeoutError: pass
            final_cnt = await _team_member_count()
            print_colored(f"[TEAM] ══ FINAL: In team ({final_cnt}/{TEAM_SIZE}) ══", Colors.MAGENTA)
            if final_cnt < TEAM_SIZE:
                print_error(f"[TEAM] Only {final_cnt}/{TEAM_SIZE} joined — abort, retry")
                heartbeat_stop.set()
                try: hb_task.cancel(); await hb_task
                except Exception: pass
                return
            await asyncio.sleep(TEAM_FINAL_WAIT)
            heartbeat_stop.set()
            try: hb_task.cancel(); await hb_task
            except Exception: pass
            print_success(f"[TEAM] 🚀 {uid_str} loop: ready → 1s → start (every 5s)")
            while _team_active["flag"]:
                try:
                    if bot_state.is_paused(uid_str): break
                    async with _team_state["lock"]:
                        if _team_state["leader_uid"] != uid_str: break
                    oid = current_account_data.get('account_id', own_id_num) if current_account_data else own_id_num
                    try:
                        rdy = ready_for_game(int(oid), current_key, current_iv)
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            _writer_ref["w"].write(rdy); await _writer_ref["w"].drain()
                    except Exception as e: print_warning(f"[TEAM] ready err: {e}")
                    await asyncio.sleep(1.0)
                    sm = start_match_team(int(oid), current_key, current_iv, region=account_region)
                    if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                        _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                except Exception as e: print_warning(f"[TEAM] start err: {e}")
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
        except Exception as e:
            print_error(f"[TEAM] coordinator: {e}")
            traceback.print_exc()

    async def _member_match_trigger():
        try:
            await asyncio.sleep(TEAM_READY_DELAY + TEAM_MEMBER_START_DELAY)
            async with _team_state["lock"]:
                if _team_state["leader_uid"] == uid_str: return
            print_success(f"[TEAM] 🚀 Member {uid_str}: ready → 1s → start (every 5s)")
            my_id = current_account_data.get('account_id', uid_str) if current_account_data else uid_str
            while _team_active["flag"]:
                try:
                    if bot_state.is_paused(uid_str): break
                    if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                        try:
                            rdy = ready_for_game(int(my_id), current_key, current_iv)
                            _writer_ref["w"].write(rdy); await _writer_ref["w"].drain()
                        except Exception as e: print_warning(f"[TEAM] member ready err: {e}")
                        await asyncio.sleep(1.0)
                        sm = start_match_team(int(my_id), current_key, current_iv, region=account_region)
                        _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                except Exception as e: print_warning(f"[TEAM] member trigger: {e}")
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
        except Exception as e: print_warning(f"[TEAM] member outer: {e}")

    try:
        while True:
            writer = None; gateway_ping_task = None
            team_coord_task = None; member_trigger_task = None
            try:
                if current_account_data:
                    fresh = None
                    if current_account_data.get('auth_type') == 'guest' and current_account_data.get('auth_uid'):
                        fresh = cache_get(str(current_account_data['auth_uid']))
                    elif current_account_data.get('auth_type') == 'token' and current_account_data.get('auth_token'):
                        fresh = cache_get(f"tok_{current_account_data['auth_token'][:20]}")
                    if fresh:
                        current_account_data = fresh
                        current_key = fresh['aes_ak']; current_iv = fresh['iv_i']
                        current_token = await build_tcp_startup_packet(
                            fresh['account_id'], fresh['token'], fresh['server_time'],
                            current_key, current_iv,
                            region=fresh.get('region', account_region), typ='OnLine')
                        try:
                            lv = int(fresh.get('level', current_level) or current_level)
                            if lv != current_level: current_level = lv
                        except Exception: pass
                    else:
                        print_warning(f"[FUNC] Cache miss {uid_str} -> re-login")
                        try:
                            if current_account_data.get('auth_uid'):
                                cache_invalidate(str(current_account_data['auth_uid']))
                            if current_account_data.get('auth_token'):
                                cache_invalidate(f"tok_{current_account_data['auth_token'][:20]}")
                        except Exception: pass
                        raise ConnectionError("Cache expired")
                try:
                    if uid_str in bot_state.accounts:
                        ll = int(bot_state.accounts[uid_str].get('level', current_level) or current_level)
                        if ll != current_level:
                            print_info(f"[LEVEL] {uid_str}: {current_level} -> {ll}")
                            current_level = ll
                except Exception: pass
                rip = await resolve_host_cloudflare(ip)
                reader, writer = await asyncio.open_connection(rip, int(port))
                _writer_ref["w"] = writer
                raw_sock = writer.get_extra_info('socket')
                if raw_sock: optimize_tcp_socket(raw_sock)
                await asyncio.sleep(bypass_hello_delay())
                writer.write(bytes.fromhex(current_token)); await writer.drain()
                try:
                    ka = await send_keep_alive(account_region)
                    if ka and not writer.is_closing():
                        writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
                except Exception: pass
                async def func_gateway_keepalive():
                    ka_bytes = await send_keep_alive(account_region)
                    while True:
                        await asyncio.sleep(bypass_ka_jitter(5.0))
                        try:
                            if writer and not writer.is_closing():
                                writer.write(ka_bytes); await writer.drain()
                        except Exception: break
                gateway_ping_task = asyncio.create_task(func_gateway_keepalive())
                connection_start_time = asyncio.get_running_loop().time()
                last_watchdog_check = connection_start_time
                search_attempts = 0
                if reconnect_count_total > 0 and (reconnect_count_total % REGION_ROTATE_EVERY_N == 0):
                    region_index = (region_index + 1) % len(REGION_ROTATION_LIST)
                    current_search_region = REGION_ROTATION_LIST[region_index]
                    print_warning(f"[REGION ROTATE] {uid_str} -> {current_search_region}")
                else:
                    current_search_region = REGION_ROTATION_LIST[region_index]
                print_success(f"[FUNC] TCP connected {uid_str} (DNS:{rip} Lvl:{current_level} R:{current_search_region})")
                reconnects = 0; no_response_count = 0; last_start_time = 0.0
                async with _team_state["lock"]:
                    _team_state["peers"][uid_str] = {
                        "writer": writer, "data": current_account_data,
                        "key": current_key, "iv": current_iv}
                    if _team_state["leader_uid"] is None:
                        _team_state["leader_uid"] = uid_str
                        print_success(f"[TEAM] 👑 {uid_str} is leader")
                if TEAM_MODE:
                    await asyncio.sleep(2.0)
                    team_coord_task = asyncio.create_task(_team_coordinator())
                    member_trigger_task = asyncio.create_task(_member_match_trigger())
                else:
                    await start_game_battle_royale(current_search_region, client_version, writer, current_key, current_iv)
                while True:
                    play_matches[:] = [m for m in play_matches if not m.done()]
                    active = await _get_match_count(uid_str)
                    try: bot_state.update_status(uid_str, "ONLINE" if active == 0 else "IN_MATCH", active)
                    except Exception: pass
                    now = asyncio.get_running_loop().time()
                    if now - last_watchdog_check >= MATCH_WATCHDOG_CHECK:
                        last_watchdog_check = now
                        sd = now - connection_start_time
                        if sd > 30: print_warning(f"[WATCHDOG] {uid_str} searching {int(sd)}s att={search_attempts}")
                        if sd > MATCH_SEARCH_TIMEOUT:
                            raise ConnectionError("Search watchdog")
                    if search_attempts >= MAX_SEARCH_ATTEMPTS:
                        raise ConnectionError("Max attempts")
                    try:
                        data = await asyncio.wait_for(reader.read(8192), timeout=0.5)
                    except asyncio.TimeoutError:
                        no_response_count += 1
                        if TEAM_MODE:
                            if no_response_count > TEAM_IDLE_ITERS_TEAM:
                                raise ConnectionError("Team idle timeout")
                        else:
                            if no_response_count > 80: raise ConnectionError("idle")
                        continue
                    if not data: raise ConnectionError("closed")
                    hex_data = data.hex()
                    pl = len(data)
                    no_response_count = 0
                    if DEBUG_TEAM_PACKETS and not hex_data.startswith("0300") and not hex_data.startswith("0600"):
                        print_info(f"[RAW-IN {uid_str}] len={pl} prefix={hex_data[:24]}")
                    if hex_data.startswith("0600") and pl > 20:
                        await _process_social_packet(data, current_account_data, tag="MAIN")
                        continue
                    if hex_data.startswith("05") and pl > 10:
                        await _handle_team_invite(hex_data, pl, uid_str, current_account_data,
                                                  current_key, current_iv, writer)
                        continue
                    if hex_data.startswith("0300") and 10 < pl < 30:
                        continue
                    if hex_data.startswith("0300") and pl >= 300:
                        print_colored("=" * 60, Colors.GREEN)
                        print_colored(f"MATCH FOUND! (UID:{uid_str}) Loading...", Colors.GREEN)
                        print_colored("=" * 60, Colors.GREEN)
                        for tk in (team_coord_task, member_trigger_task):
                            if tk and not tk.done():
                                tk.cancel()
                                try: await tk
                                except asyncio.CancelledError: pass
                        team_coord_task = None; member_trigger_task = None
                        _team_active["flag"] = False
                        try:
                            res = json.loads(await decode_protobuf(hex_data[10:]))
                            token = udp_key = match_code = server_ip_port = None
                            match_account_id = block_val = None
                            if '42' in res and 'data' in res['42']:
                                match_code = res['42']['data']
                            if '5' in res and 'data' in res['5']:
                                r5 = res['5']['data']
                                server_ip_port = r5.get('2', {}).get('data')
                                udp_key = r5.get('3', {}).get('data')
                                token = r5.get('4', {}).get('data')
                                if '42' in r5: match_code = r5['42']['data']
                            if '1' in res and 'data' in res['1']:
                                match_account_id = res['1']['data']
                            if '5' in res and 'data' in res['5']:
                                block_val = res['5']['data'].get('1', {}).get('data')
                            effective = match_account_id or account_id or "BD_BOT"
                            if token and udp_key and match_code and server_ip_port:
                                try:
                                    async with _team_state["lock"]:
                                        _team_state["pk_code"] = str(match_code)
                                        _team_state["team_code"] = str(match_code)
                                    print_colored(f"[PK] 🎯 Room Code: {match_code}", Colors.MAGENTA)
                                    print_colored(f"[PK] 🌐 Server: {server_ip_port}", Colors.MAGENTA)
                                    print_colored(f"[PK] 🔑 UDP Key: {udp_key}", Colors.MAGENTA)
                                except Exception: pass
                                acc_tok = current_account_data.get('access_token', '') if current_account_data else ""
                                mid, mp = BR_MODE_ID, BR_MAP_ID
                                tag = "BATTLE_ROYALE"
                                print_info(f"[TARGET] {tag} mid={mid} mp={mp}")
                                thunder, sharma = await build_match_startup_packets(
                                    token, udp_key, match_code, effective, block_val or 0,
                                    server_ip=server_ip_port, region=account_region,
                                    client_version=client_version, access_token=acc_tok,
                                    mode_id=mid, map_id=mp)
                                match_index = await _inc_match(uid_str)
                                total = await _get_total_match_count()
                                print_colored(f"[MATCH #{match_index}] UDP -> {server_ip_port} ({tag}) UID:{uid_str}", Colors.CYAN)
                                new_match = asyncio.create_task(play_game(
                                    server_ip_port, thunder, sharma, udp_key, match_code,
                                    effective, current_search_region, client_version,
                                    current_key, current_iv,
                                    match_index=match_index, on_match_complete=trigger_post_match_refresh))
                                play_matches.append(new_match)
                                consecutive_parse_failures = 0
                                async def drain_gw():
                                    while not new_match.done():
                                        try:
                                            dg = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                                            if not dg: break
                                            gh = dg.hex()
                                            if gh.startswith("0600") and len(dg) > 20:
                                                await _process_social_packet(dg, current_account_data, tag="DRAIN")
                                        except asyncio.TimeoutError: continue
                                        except Exception: break
                                drain_task = asyncio.create_task(drain_gw())
                                try: await new_match
                                except Exception as e: print_error(f"[MATCH #{match_index}] {e}")
                                finally:
                                    drain_task.cancel()
                                    try: await drain_task
                                    except asyncio.CancelledError: pass
                                play_matches[:] = [m for m in play_matches if not m.done()]
                                async with _team_state["lock"]:
                                    _team_state["peers"].pop(uid_str, None)
                                    if _team_state["leader_uid"] == uid_str:
                                        _team_state["leader_uid"] = None
                                    _team_state["pk_code"] = None
                                await _team_member_leave(uid_str)
                                _team_active["flag"] = True
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                print_info(f"[FUNC] {uid_str} reconnect in {NEW_MATCH_DELAY}s...")
                                await asyncio.sleep(NEW_MATCH_DELAY)
                                reconnect_count_total += 1
                                break
                            else:
                                consecutive_parse_failures += 1
                                print_warning(f"[FUNC] Non-match big pkt #{consecutive_parse_failures}")
                                if consecutive_parse_failures >= MAX_CONSECUTIVE_PARSE_FAILURES:
                                    consecutive_parse_failures = 0
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                await asyncio.sleep(NON_MATCH_RECONNECT_DELAY)
                                break
                        except Exception as e:
                            print_error(f"[FUNC] Match parse: {e}")
                            print_tb("match_parse", e)
                            consecutive_parse_failures += 1
                            try: writer.close(); await writer.wait_closed()
                            except Exception: pass
                            await asyncio.sleep(NON_MATCH_RECONNECT_DELAY)
                            break
                    if 30 <= pl <= 40: continue
            except asyncio.CancelledError:
                print_warning(f"[FUNC] Cancelled — cancel {len(play_matches)} UDP")
                for m in play_matches:
                    if not m.done(): m.cancel()
                if play_matches:
                    await asyncio.gather(*play_matches, return_exceptions=True)
                play_matches.clear()
                if gateway_ping_task: gateway_ping_task.cancel()
                async with _team_state["lock"]:
                    _team_state["peers"].pop(uid_str, None)
                    if _team_state["leader_uid"] == uid_str:
                        _team_state["leader_uid"] = None
                await _team_member_leave(uid_str)
                raise
            except Exception as e:
                if gateway_ping_task: gateway_ping_task.cancel()
                print_error(f"[FUNC] TCP state {uid_str}: {e}")
                print_tb("functional_battle_royale", e)
                play_matches[:] = [m for m in play_matches if not m.done()]
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                if "Cache expired" in str(e):
                    print_warning(f"[FUNC] re-login {uid_str}")
                    break
                reconnect_count_total += 1
                reconnects += 1
                if reconnects > max_reconnects:
                    reconnects = 0
                    await asyncio.sleep(3)
                    continue
                await asyncio.sleep(bypass_human_reconnect_delay(reconnects))
            finally:
                _team_active["flag"] = False
                for tk in (team_coord_task, member_trigger_task):
                    if tk and not tk.done():
                        tk.cancel()
                        try: await tk
                        except (asyncio.CancelledError, Exception): pass
                if gateway_ping_task: gateway_ping_task.cancel()
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                async with _team_state["lock"]:
                    _team_state["peers"].pop(uid_str, None)
                    if _team_state["leader_uid"] == uid_str:
                        _team_state["leader_uid"] = None
                await _team_member_leave(uid_str)
                _team_active["flag"] = True
                try: gc.collect()
                except: pass
    except asyncio.CancelledError:
        for m in play_matches:
            if not m.done(): m.cancel()
        if play_matches: await asyncio.gather(*play_matches, return_exceptions=True)
        play_matches.clear()
        raise

async def informational(addrs, starter_packet, key, iv, region="ID", max_reconnects=3):
    reconnects = 0
    ip, port = addrs.split(":")
    while True:
        writer = None; ping_task = None
        try:
            rip = await resolve_host_cloudflare(ip)
            reader, writer = await asyncio.open_connection(rip, int(port))
            rs = writer.get_extra_info('socket')
            if rs: optimize_tcp_socket(rs)
            writer.write(bytes.fromhex(starter_packet)); await writer.drain()
            reconnects = 0
            try:
                ka = await send_keep_alive(region)
                if ka and not writer.is_closing():
                    writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
            except Exception: pass
            async def info_ka():
                ka = await send_keep_alive(region)
                while True:
                    await asyncio.sleep(bypass_ka_jitter(5.0))
                    try:
                        if writer and not writer.is_closing():
                            writer.write(ka); await writer.drain()
                    except Exception: break
            ping_task = asyncio.create_task(info_ka())
            while True:
                data = await reader.read(8192)
                if not data: raise ConnectionError("closed")
        except asyncio.CancelledError:
            if ping_task: ping_task.cancel()
            if writer:
                try: writer.close(); await writer.wait_closed()
                except Exception: pass
            raise
        except Exception:
            if ping_task: ping_task.cancel()
            if writer:
                try: writer.close(); await writer.wait_closed()
                except Exception: pass
            reconnects += 1
            if reconnects > max_reconnects:
                await asyncio.sleep(3); reconnects = 0
            else: await asyncio.sleep(1)

def _register_credentials(ad):
    try:
        acc_id = str(ad['account_id'])
        bot_state.account_credentials[acc_id] = ad
        if ad.get('auth_uid'): bot_state.account_credentials[str(ad['auth_uid'])] = ad
        if ad.get('auth_token'): bot_state.account_credentials[f"tok_{ad['auth_token'][:20]}"] = ad
    except Exception: pass

async def refresh_account_profile(ad_or_uid):
    try:
        if isinstance(ad_or_uid, str):
            uid = str(ad_or_uid); ad = bot_state.account_credentials.get(uid)
        else:
            ad = ad_or_uid; uid = str(ad.get('account_id')) if ad else "?"
        if not ad: return
        token = ad.get('token'); acc_id = ad.get('account_id')
        srv = ad.get('server_url'); rel = ad.get('release_version')
        if not (token and acc_id and srv and rel): return
        data = await get_player_personal_show(int(acc_id), token, srv, rel)
        if not data: return
        pd = data.get(1, {}) if isinstance(data.get(1), dict) else {}
        nickname = pd.get(3); lvl = pd.get(6); exp = pd.get(7)
        if exp is None: return
        try:
            exp = int(exp); lvl = int(lvl) if lvl else 1
        except Exception: return
        aid = str(acc_id)
        if aid not in bot_state.accounts:
            bot_state.register_account(aid, nickname or f"Player_{aid}",
                                       region=ad.get('region', 'ID'), level=lvl, exp=exp)
            return
        old_ex = 0; old_lv = 0
        try:
            old_ex = int(bot_state.accounts[aid].get('exp', 0) or 0)
            old_lv = int(bot_state.accounts[aid].get('level', 0) or 0)
        except Exception: pass
        bot_state.update_exp(aid, exp, lvl)
        if nickname: bot_state.accounts[aid]["nickname"] = nickname
        _update_cache_profile(ad, lvl, exp)
        ad['level'] = lvl; ad['exp'] = exp
        if nickname: ad['nickname'] = nickname
        if old_lv > 0 and lvl > old_lv:
            print_success(f"[LEVEL UP] {aid}: {old_lv} -> {lvl}")
        elif old_ex != exp:
            print_success(f"[EXP] {aid} Lvl{lvl} +{exp - old_ex}")
    except Exception as e:
        print_tb("refresh_account_profile", e)

# ═══════════════════════════════════════════════════════════════════
#  ACCOUNT PROCESSING (NEW AUTH FLOW + RETRY + TRACE)
# ═══════════════════════════════════════════════════════════════════
async def process_account_uid_pass(uid, password, region_override=None):
    uid = str(uid)
    cached = cache_get(uid)
    if cached:
        print_success(f"[CACHE] {uid} loaded")
        acc_id = str(cached['account_id'])
        bot_state.register_account(uid=acc_id,
            nickname=cached.get('nickname', f"Player_{acc_id}"),
            region=cached.get('region', 'ID'),
            level=cached.get('level', 1), exp=cached.get('exp', 0),
            likes=cached.get('likes', 0))
        _register_credentials(cached); return cached

    print_info(f"[LOGIN] UID {uid}...")
    for attempt in range(1, LOGIN_MAX_RETRIES + 1):
        try:
            _step(uid, f"attempt {attempt}/{LOGIN_MAX_RETRIES} start")
            async with _LOGIN_SEMAPHORE:
                region = (region_override or "ID").upper()
                vc = await version_config(region)
                if not vc:
                    print_error(f"[LOGIN] {uid} version_config FAILED (region={region})")
                    raise RuntimeError("version_config failed")
                release_version, client_version, server_url, gop_1, app_version = vc

                lang = REGION_LANG.get(region, "en")
                tg = await get_access_token(uid, password)
                if not tg:
                    print_error(f"[LOGIN] {uid} get_access_token FAILED (uid/password?)")
                    raise RuntimeError("get_access_token failed")
                open_id, access_token, platform = tg

                major_payload, login_payload = await get_payload(
                    access_token, open_id, platform, client_version, lang, region)

                res_json = await major_login(major_payload, server_url, release_version)
                if not res_json:
                    print_error(f"[LOGIN] {uid} major_login FAILED")
                    raise RuntimeError("major_login failed")

                def _gd(k):
                    v = res_json.get(str(k))
                    if isinstance(v, dict) and "data" in v: return v["data"]
                    if k in res_json and not isinstance(res_json[k], dict): return res_json[k]
                    if isinstance(v, dict): return v.get("data")
                    return None

                acc_id_raw = _gd(1); region_raw = _gd(2) or region
                jwt_token = _gd(8); server_url_raw = _gd(10); server_time = _gd(21)
                if not acc_id_raw:
                    print_error("[LOGIN] account_id (f1) missing in MajorLogin")
                if not jwt_token:
                    print_error("[LOGIN] JWT (f8) missing in MajorLogin")
                if not server_url_raw:
                    print_error("[LOGIN] server_url (f10) missing in MajorLogin")
                aes_ak, iv_i = _extract_key_iv(res_json)
                if not jwt_token or not server_url_raw or not aes_ak:
                    raise RuntimeError(
                        f"MajorLogin incomplete jwt={bool(jwt_token)} url={bool(server_url_raw)} "
                        f"aes={bool(aes_ak)} iv={bool(iv_i)}")

                getlogin_json = await get_login_data(login_payload, jwt_token, server_url_raw, release_version)
                if not getlogin_json:
                    print_error("[LOGIN] get_login_data FAILED")
                    raise RuntimeError("get_login_data failed")

            func_addrs = _gf_field(getlogin_json, 14)
            info_addrs = _gf_field(getlogin_json, 32)
            if not func_addrs or not info_addrs:
                print_error(f"[LOGIN] TCP addrs missing func={func_addrs} info={info_addrs}")
                raise RuntimeError("TCP addrs missing")

            level = int(_gf_field(getlogin_json, 6, 1) or 1)
            exp = int(_gf_field(getlogin_json, 7, 0) or 0)
            likes = int(_gf_field(getlogin_json, 8, 0) or 0)
            nickname = _gf_field(getlogin_json, 4, f"Player_{acc_id_raw}") or f"Player_{acc_id_raw}"
            region_final = region_raw or _gf_field(getlogin_json, 3, region) or region
            acc_id = str(acc_id_raw)

            bot_state.register_account(uid=acc_id, nickname=nickname, region=region_final,
                                        level=level, exp=exp, likes=likes)
            print_success(f"[OK] {acc_id} | {nickname} | Lvl{level} | BATTLE ROYALE")

            ad = {
                'account_id': acc_id_raw, 'nickname': nickname, 'region': region_final,
                'level': level, 'exp': exp, 'likes': likes,
                'open_id': open_id, 'access_token': access_token, 'platform': str(platform),
                'uid': uid,
                'token': jwt_token, 'server_time': server_time,
                'aes_ak': aes_ak, 'iv_i': iv_i,
                'functional_addrs': func_addrs, 'informational_addrs': info_addrs,
                'release_version': release_version, 'client_version': client_version,
                'server_url': server_url_raw, 'login_payload_data': login_payload,
                'auth_type': 'guest', 'auth_uid': uid, 'auth_password': password,
            }
            _register_credentials(ad); cache_set(uid, ad)
            return ad
        except Exception as e:
            print_tb(f"process_account_uid_pass attempt {attempt}", e)
            if attempt < LOGIN_MAX_RETRIES:
                wait = LOGIN_RETRY_DELAY * attempt
                print_warning(f"[LOGIN] {uid} retry in {wait:.1f}s...")
                await asyncio.sleep(wait)
    print_error(f"[LOGIN] {uid} GAVE UP after {LOGIN_MAX_RETRIES} attempts")
    return None

async def process_account_token(access_token, region_override=None):
    cache_key = f"tok_{access_token[:20]}"
    cached = cache_get(cache_key)
    if cached:
        acc_id = str(cached['account_id'])
        bot_state.register_account(uid=acc_id,
            nickname=cached.get('nickname', f"Player_{acc_id}"),
            region=cached.get('region', 'ID'),
            level=cached.get('level', 1), exp=cached.get('exp', 0),
            likes=cached.get('likes', 0))
        print_success(f"[CACHE] token -> {acc_id}")
        _register_credentials(cached); return cached

    print_info("[LOGIN] Token...")
    for attempt in range(1, LOGIN_MAX_RETRIES + 1):
        try:
            _step(cache_key, f"token attempt {attempt}/{LOGIN_MAX_RETRIES} start")
            async with _LOGIN_SEMAPHORE:
                region = (region_override or "ID").upper()
                vc = await version_config(region)
                if not vc:
                    print_error(f"[LOGIN] version_config FAILED (region={region})")
                    raise RuntimeError("version_config failed")
                release_version, client_version, server_url, gop_1, app_version = vc
                lang = REGION_LANG.get(region, "en")

                url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
                hdrs = {"User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"}
                resp = await asyncio.to_thread(
                    lambda: httpx.get(url, headers=hdrs, timeout=10, verify=False))
                _step(cache_key, "token inspect", f"HTTP {resp.status_code} {_snip(resp.content, 100)}")
                d = resp.json()
                if 'error' in d:
                    print_error(f"[LOGIN] token inspect error: {d.get('error')}")
                    raise RuntimeError("token invalid")
                open_id = d.get('open_id'); platform = d.get('platform', 4)
                if not open_id:
                    print_error("[LOGIN] open_id missing from inspect")
                    raise RuntimeError("no open_id")

                major_payload, login_payload = await get_payload(
                    access_token, open_id, str(platform), client_version, lang, region)

                res_json = await major_login(major_payload, server_url, release_version)
                if not res_json:
                    print_error("[LOGIN] major_login FAILED")
                    raise RuntimeError("major_login failed")

                def _gd(k):
                    v = res_json.get(str(k))
                    if isinstance(v, dict) and "data" in v: return v["data"]
                    if k in res_json and not isinstance(res_json[k], dict): return res_json[k]
                    if isinstance(v, dict): return v.get("data")
                    return None

                acc_id_raw = _gd(1); region_raw = _gd(2) or region
                jwt_token = _gd(8); server_url_raw = _gd(10); server_time = _gd(21)
                if not acc_id_raw:
                    print_error("[LOGIN] account_id (f1) missing in MajorLogin")
                if not jwt_token:
                    print_error("[LOGIN] JWT (f8) missing in MajorLogin")
                if not server_url_raw:
                    print_error("[LOGIN] server_url (f10) missing in MajorLogin")
                aes_ak, iv_i = _extract_key_iv(res_json)
                if not jwt_token or not server_url_raw or not aes_ak:
                    raise RuntimeError(
                        f"MajorLogin incomplete jwt={bool(jwt_token)} url={bool(server_url_raw)} "
                        f"aes={bool(aes_ak)} iv={bool(iv_i)}")

                getlogin_json = await get_login_data(login_payload, jwt_token, server_url_raw, release_version)
                if not getlogin_json:
                    print_error("[LOGIN] get_login_data FAILED")
                    raise RuntimeError("get_login_data failed")

            func_addrs = _gf_field(getlogin_json, 14)
            info_addrs = _gf_field(getlogin_json, 32)
            if not func_addrs or not info_addrs:
                print_error(f"[LOGIN] TCP addrs missing func={func_addrs} info={info_addrs}")
                raise RuntimeError("TCP addrs missing")

            level = int(_gf_field(getlogin_json, 6, 1) or 1)
            exp = int(_gf_field(getlogin_json, 7, 0) or 0)
            likes = int(_gf_field(getlogin_json, 8, 0) or 0)
            nickname = _gf_field(getlogin_json, 4, f"Player_{acc_id_raw}") or f"Player_{acc_id_raw}"
            region_final = region_raw or _gf_field(getlogin_json, 3, region) or region
            acc_id = str(acc_id_raw)

            bot_state.register_account(uid=acc_id, nickname=nickname, region=region_final,
                                        level=level, exp=exp, likes=likes)
            print_success(f"[OK] token {acc_id} | {nickname} | Lvl{level}")

            ad = {
                'account_id': acc_id_raw, 'nickname': nickname, 'region': region_final,
                'level': level, 'exp': exp, 'likes': likes,
                'open_id': open_id, 'access_token': access_token, 'platform': str(platform),
                'uid': open_id,
                'token': jwt_token, 'server_time': server_time,
                'aes_ak': aes_ak, 'iv_i': iv_i,
                'functional_addrs': func_addrs, 'informational_addrs': info_addrs,
                'release_version': release_version, 'client_version': client_version,
                'server_url': server_url_raw, 'login_payload_data': login_payload,
                'auth_type': 'token', 'auth_token': access_token,
            }
            _register_credentials(ad); cache_set(cache_key, ad)
            return ad
        except Exception as e:
            print_tb(f"process_account_token attempt {attempt}", e)
            if attempt < LOGIN_MAX_RETRIES:
                wait = LOGIN_RETRY_DELAY * attempt
                print_warning(f"[LOGIN] token retry in {wait:.1f}s...")
                await asyncio.sleep(wait)
    print_error(f"[LOGIN] token GAVE UP after {LOGIN_MAX_RETRIES} attempts")
    return None

async def _auto_equip_for_account(ad):
    """Run equip.py workflow for one account right after successful login."""
    if not EQUIP_AVAILABLE: return
    try:
        jwt = ad.get('token'); srv = ad.get('server_url') or "https://client.ind.freefiremobile.com"
        if not jwt: return
        acc_id = ad.get('account_id')
        print_info(f"[EQUIP] Running auto-equip for {acc_id}...")
        await run_equip_workflow(jwt, srv)
        print_success(f"[EQUIP] ✅ Auto-equip completed for {acc_id}")
    except Exception as e:
        print_warning(f"[EQUIP] Failed for {ad.get('account_id')}: {e}")
        print_tb("auto_equip", e)

async def run_account_worker(ad, label):
    acc_id = str(ad['account_id'])
    info_task = None; exp_task = None; ping_task = None
    try:
        # ★ AUTO-EQUIP first, before matchmaking
        await _auto_equip_for_account(ad)

        reg = ad.get('region', 'ID')
        tcp_online = await build_tcp_startup_packet(
            ad['account_id'], ad['token'], ad['server_time'],
            ad['aes_ak'], ad['iv_i'], region=reg, typ='OnLine')
        tcp_chat = await build_tcp_startup_packet(
            ad['account_id'], ad['token'], ad['server_time'],
            ad['aes_ak'], ad['iv_i'], region=reg, typ='ChaT')
        info_task = asyncio.create_task(informational(ad['informational_addrs'], tcp_chat,
                                                      ad['aes_ak'], ad['iv_i'], region=reg))
        if ENABLE_HTTP_PING:
            ping_task = asyncio.create_task(ping_worker(acc_id, ad['token'], ad['release_version'], region=reg))
            print_success(f"[PING] Started {acc_id}")
        async def exp_refresher():
            try:
                f = bot_state.account_credentials.get(acc_id)
                if f: await refresh_account_profile(f)
            except Exception: pass
            while True:
                await asyncio.sleep(EXP_REFRESH_INTERVAL + random.uniform(-3.0, 3.0))
                try:
                    f = bot_state.account_credentials.get(acc_id)
                    if f: await refresh_account_profile(f)
                except Exception: pass
        exp_task = asyncio.create_task(exp_refresher())
        await functional_battle_royale(ad['functional_addrs'], tcp_online, ad['region'], ad['client_version'],
            ad['aes_ak'], ad['iv_i'], account_id=acc_id, account_data=ad,
            account_level=int(ad.get('level', 2) or 2))
    except asyncio.CancelledError: raise
    except Exception as e:
        print_error(f"run_account_worker {label}: {e}")
        print_tb("run_account_worker", e)
        if "Cache expired" in str(e) or "closed" in str(e):
            cache_invalidate(acc_id)
            if ad.get('auth_uid'): cache_invalidate(str(ad['auth_uid']))
            if ad.get('auth_token'): cache_invalidate(f"tok_{ad['auth_token'][:20]}")
    finally:
        for t in (info_task, exp_task, ping_task):
            if t and not t.done(): t.cancel()
        for t in (info_task, exp_task, ping_task):
            if t:
                try: await t
                except Exception: pass

async def account_loop_guest(uid, password):
    while True:
        try:
            print_info(f"[LOGIN] Guest {uid}...")
            cache_invalidate(uid)
            try: bot_state.update_status(str(uid), "CONNECTING")
            except Exception: pass
            ad = await process_account_uid_pass(uid, password)
            if not ad:
                print_error(f"Login failed {uid}, retry 15s")
                try: bot_state.update_status(str(uid), "ERROR")
                except Exception: pass
                await asyncio.sleep(15); continue
            await run_account_worker(ad, uid)
            print_warning(f"Session end {uid}, reconnect 3s")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print_warning(f"Worker {uid} stopped")
            try: bot_state.update_status(str(uid), "OFFLINE")
            except Exception: pass
            break
        except Exception as e:
            print_error(f"Error {uid}: {e}, retry 10s")
            print_tb(f"account_loop_guest {uid}", e)
            await asyncio.sleep(10)

async def account_loop_token(token):
    label = token[:10]
    while True:
        try:
            ad = await process_account_token(token)
            if not ad:
                print_error("Login token fail, retry 15s")
                await asyncio.sleep(15); continue
            acc_id = str(ad['account_id'])
            await run_account_worker(ad, acc_id)
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print_warning(f"Token {label} stopped"); break
        except Exception as e:
            print_error(f"Token error: {e}, retry 10s")
            print_tb(f"account_loop_token {label}", e)
            await asyncio.sleep(10)

def load_accounts():
    accounts = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list): accounts = data
        except Exception as e: print_error(f"load: {e}")
    if not accounts and FALLBACK_UID and FALLBACK_PASSWORD:
        accounts.append({"uid": FALLBACK_UID, "password": FALLBACK_PASSWORD})
    return accounts

# ═══════════════════════════ MAIN ═══════════════════════════
async def main():
    _rbc_banner()

    print_info(f"Match interval: {START_MATCH_INTERVAL}s | Offline: {NEW_MATCH_DELAY}s")
    print_info("Mode: ULTRA FAST BATTLE ROYALE ONLY")
    print_info(f"Movement: AUTO_MOVE_ENABLED={AUTO_MOVE_ENABLED} (4/4 PER-ACCOUNT XIRUS hunt)")
    print_info(f"Auto-Equip: {'ENABLED' if EQUIP_AVAILABLE else 'DISABLED (equip.py missing)'}")
    print_info("[AUTH] get_access_token -> get_payload -> MajorLogin -> _extract_key_iv -> GetLoginData")
    print_info("[AUTH] refresh via GetPlayerPersonalShow")
    print_info(f"[LOGIN] trace={'ON' if LOGIN_DEBUG else 'OFF'} retries={LOGIN_MAX_RETRIES}")
    if TEAM_MODE:
        print_success(f"[SQUAD] size={TEAM_SIZE} peer_wait={TEAM_PEER_WAIT_TIMEOUT}s")
    print_colored("=" * 60, Colors.MAGENTA)

    if not os.environ.get("RBC_SKIP_WEB"):
        print_info("Starting standalone mode (no web dashboard)")

    accounts = load_accounts()
    if not accounts:
        print_warning(f"No accounts in {ACCOUNTS_FILE}.")
    else:
        print_success(f"[ACCOUNTS] Loaded {len(accounts)} account(s) — ALL will move + auto-equip")
    for acc in accounts:
        if acc.get("token"):
            t = asyncio.create_task(account_loop_token(acc["token"]))
            bot_state.account_workers[acc["token"][:10]] = t
        elif acc.get("uid") and acc.get("password"):
            u = str(acc["uid"])
            t = asyncio.create_task(account_loop_guest(u, acc["password"]))
            bot_state.account_workers[u] = t

    try:
        while True: await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print_warning("Shutting down...")
        for t in list(bot_state.account_workers.values()): t.cancel()
        await asyncio.gather(*bot_state.account_workers.values(), return_exceptions=True)
        print_success("Closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("stopped")