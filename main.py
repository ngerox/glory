#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import sys, json, time, asyncio, subprocess, uuid, signal, random, threading
import urllib.parse, urllib.request, urllib.error
from typing import Dict, Optional
from aiohttp import web, WSMsgType

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUILD_INFO_API_IND = "https://star-guild-info.lovable.app/api/public/info"
GUILD_INFO_API_OTHER = "https://danger-guild-management-web.vercel.app/guild"
GUILD_JOIN_API = "https://danger-guild-management-web.vercel.app/join"
GUILD_MEMBERS_API = "https://danger-guild-management-web.vercel.app/members"
BIO_API = "https://star-bio-api.lovable.app/api/public/bio-upload"

GEN_FILE = os.path.join(BASE_DIR, "gen.py")
MAIN_FILE = os.path.join(BASE_DIR, "app.py")
GEN_OUT_DIR = os.path.join(BASE_DIR, "RBC1_GENS")
# On Railway: add a Volume mounted at /data and set DATA_DIR=/data so users/coupons/settings survive redeploys
DATA_DIR = os.environ.get("DATA_DIR") or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or BASE_DIR
os.makedirs(DATA_DIR, exist_ok=True)
RUNTIME_DIR = os.path.join(DATA_DIR, "runtime")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DB_FILE = os.path.join(DATA_DIR, "glory_groups.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
MANUAL_ACCS_FILE = os.path.join(DATA_DIR, "manual_accounts.json")
COUPONS_FILE = os.path.join(DATA_DIR, "coupons.json")

os.makedirs(RUNTIME_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(GEN_OUT_DIR, exist_ok=True)

VALID_REGIONS = ["IND","BD","ME","TH","ID","VN","PK","TW","CIS","RU","SAC","BR","EU","SG","NA","US"]
ADMIN_SECRET_PATH = "/admin-x9k2"

WEB_HOST = os.environ.get("RBC_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("PORT", os.environ.get("RBC_WEB_PORT", "26215")))
DEFAULT_REGION = os.environ.get("RBC_GEN_REGION", "IND").upper()
DEFAULT_PASSWORD = "RBC__"
GEN_BASE_TIMEOUT = int(os.environ.get("RBC_GEN_BASE_TIMEOUT", "90"))
GEN_PER_ACCOUNT_TIMEOUT = int(os.environ.get("RBC_GEN_PER_ACCOUNT_TIMEOUT", "60"))

SETTINGS = {
    "goal_hours": 8, "bot_count": 4, "bot_name_prefix": "RBC_",
    "bio_text": "Ｒ Ｂ Ｃ Ｇ Ｌ Ｏ Ｒ Ｙ",
    "max_launches": 10, "auto_restart_mins": 15, "join_retry_rounds": 5,
    "approval_wait_secs": 120, "member_check_secs": 8, "glory_refresh_secs": 60,
    "credit_per_launch": 1, "credit_price": 1,
    "refund_min_glory": 0, "refund_time_mins": 30,
    "global_banner": {"active": False, "title": "", "body": ""},
    "maintenance": {"glory": {}, "likes": {}, "level": {}},
}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return default
    return default

def _json_default(o):
    # live objects (e.g. subprocess.Popen in group["engine_proc"]) must not be saved as text,
    # otherwise after a restart proc.poll() crashes on a str
    if isinstance(o, subprocess.Popen): return None
    return str(o)

def save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=_json_default)
        os.replace(tmp, path)
    except Exception as e: print(f"save error {path}: {e}")

SETTINGS.update(load_json(SETTINGS_FILE, {}))
GROUPS_DB = load_json(DB_FILE, {})
USERS_DB = load_json(USERS_FILE, {})
MANUAL_ACCOUNTS = load_json(MANUAL_ACCS_FILE, {})
COUPONS_DB = load_json(COUPONS_FILE, {})

# ── Admin account (override with env ADMIN_USER / ADMIN_PASS) ──
ADMIN_USER = os.environ.get("ADMIN_USER", "NGANIL")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "NG1988")
PAY_FILE = os.path.join(DATA_DIR, "payments.json")          # verified/used UTRs
PAY_CFG_FILE = os.path.join(DATA_DIR, "pay_config.json")    # price, UPI id, gmail app password
PAY_DEFAULT = {"price": 20, "upi_id": "anileditz@fam", "payee": "Anil Kumar Meghwal",
               "gmail": "", "app_password": "", "sender_filter": "fampay",
               "credit_keywords": "received,credited,paid you,sent you,payment from,money in",
               "debit_keywords": "debited,you paid,paid to,sent to,you sent,payment to,withdrawn",
               "max_age_hours": 48, "min_credits": 1, "imap_host": "imap.gmail.com",
               "gateway_key": os.environ.get("RBC_PAY_API_KEY", ""), "gateway_base": os.environ.get("RBC_PAY_GATEWAY_URL", "")}
PAY_CFG = {**PAY_DEFAULT, **load_json(PAY_CFG_FILE, {})}
PAYMENTS = load_json(PAY_FILE, {})
if os.environ.get("RBC_PAY_API_KEY"): PAY_CFG["gateway_key"] = os.environ["RBC_PAY_API_KEY"]   # env wins over saved value
if os.environ.get("RBC_PAY_GATEWAY_URL"): PAY_CFG["gateway_base"] = os.environ["RBC_PAY_GATEWAY_URL"].rstrip("/")
COUPON_PREFIX = "FF"

USERS_DB.pop("admin", None) if USERS_DB.get("admin", {}).get("password") == "admin" else None  # drop insecure default
_adm = USERS_DB.get(ADMIN_USER, {})
USERS_DB[ADMIN_USER] = {**_adm, "username": ADMIN_USER, "password": ADMIN_PASS, "is_admin": True,
                        "unlimited": True, "credits": max(int(_adm.get("credits", 0) or 0), 999999),
                        "groups": _adm.get("groups", [])}
save_json(USERS_FILE, USERS_DB)

LOG_BUFFER = []
LOG_SUBSCRIBERS = set()
MAIN_LOOP = None

def push_log(level, msg, instance=None, user=None):
    entry = {"ts": time.time(), "level": level, "msg": str(msg), "instance": instance, "user": user}
    LOG_BUFFER.append(entry)
    if len(LOG_BUFFER) > 1000: LOG_BUFFER.pop(0)
    loop = MAIN_LOOP
    if loop is not None and LOG_SUBSCRIBERS:
        for ws in list(LOG_SUBSCRIBERS):
            try:
                # works both from the event loop and from executor threads (run_gen etc.)
                loop.call_soon_threadsafe(lambda w=ws: asyncio.ensure_future(_ws_send(w, entry)))
            except Exception: LOG_SUBSCRIBERS.discard(ws)
    print(f"[{level}] {msg}", flush=True)

async def _ws_send(ws, entry):
    try: await ws.send_json(entry)
    except Exception: LOG_SUBSCRIBERS.discard(ws)

GLOBAL_STATS = {"bots_total": 0, "bots_online": 0, "matches_started": 0,
                "total_gained_exp": 0, "total_glory_pushed": 0, "started_at": time.time()}

def group_dir(gid): d = os.path.join(RUNTIME_DIR, gid); os.makedirs(d, exist_ok=True); return d
def group_accounts_path(gid): return os.path.join(group_dir(gid), "accounts.json")
def group_log_path(gid): return os.path.join(group_dir(gid), "engine.log")
def group_accounts_meta_path(gid): return os.path.join(group_dir(gid), "accounts_meta.json")

SESSIONS: Dict[str, str] = {}
def new_session(u): t = uuid.uuid4().hex; SESSIONS[t] = u; return t

def user_from_request(request):
    tok = request.cookies.get("rbc_sess")
    if tok and tok in SESSIONS:
        u = USERS_DB.get(SESSIONS[tok])
        if u and u.get("banned") and not u.get("is_admin"):
            SESSIONS.pop(tok, None); return None
        return u
    return None

def admin_from_request(request):
    u = user_from_request(request)
    if u and u.get("is_admin"): return u
    return None

# ═══════════════ External API clients ═══════════════
def _http_get_json(url, timeout=20, no_cache=False):
    hdrs = {"User-Agent": "RBC-GLORY/30", "Accept": "application/json"}
    if no_cache: hdrs["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try: return resp.status, json.loads(body), body
            except Exception: return resp.status, None, body
    except urllib.error.HTTPError as e:
        try: body = e.read().decode("utf-8", errors="replace")
        except Exception: body = ""
        return e.code, None, body
    except Exception as e:
        return 0, None, str(e)

def fetch_guild_info(guild_id, region="IND"):
    url_new = f"{GUILD_INFO_API_OTHER}?guild_id={guild_id}&region={region}"
    code, js, _ = _http_get_json(url_new, 15, True)
    if code == 200 and isinstance(js, dict) and js.get("status") == "success":
        return _parse_new(js)
    if region.upper() == "IND":
        url_old = f"{GUILD_INFO_API_IND}?clan_id={guild_id}&region={region}"
        code2, js2, _ = _http_get_json(url_old, 15, True)
        if code2 == 200 and isinstance(js2, dict) and js2.get("status") == "success" and not js2.get("error_code"):
            return _parse_old(js2, guild_id, region)
    return None

def _parse_old(js, gid, region):
    return {"guild_name": js.get("clan_name") or f"Guild {gid}", "guild_id": str(js.get("clan_id") or gid),
            "guild_level": int(js.get("guild_level") or 1), "region": region,
            "leader_id": str(js.get("guild_leader_id") or ""), "leader_name": "",
            "slogan": str(js.get("guild_bio") or ""), "bio": str(js.get("guild_bio") or ""),
            "current_members": int(js.get("current_members") or 0),
            "max_members": int(js.get("total_members") or 35),
            "members_online": int(js.get("members_online") or 0),
            "total_glory": int(js.get("glory_points") or js.get("score") or 0),
            "weekly_glory": 0, "activity_points": int(js.get("guild_activity_points") or 0),
            "rank": int(js.get("rank") or 0), "auto_approval": True}

def _parse_new(js):
    leader = js.get("GuildLeader") or {}
    auto = str(js.get("AutoApprovalStatus", "ON")).upper() == "ON"
    return {"guild_name": js.get("GuildName") or "Unknown",
            "guild_id": str(js.get("GuildId") or ""),
            "guild_level": int(js.get("GuildLevel") or 1),
            "region": js.get("GuildRegion") or "",
            "leader_id": str(leader.get("Uid") or ""),
            "leader_name": str(leader.get("Name") or "Unknown"),
            "slogan": str(js.get("GuildSlogan") or ""),
            "bio": str(js.get("GuildSlogan") or ""),
            "current_members": int(js.get("CurrentMembers") or 0),
            "max_members": int(js.get("MaxMembers") or 35),
            "members_online": 0,
            "total_glory": int(js.get("TotalActivityPoints") or 0),
            "weekly_glory": int(js.get("WeeklyActivityPoints") or 0),
            "activity_points": int(js.get("TotalActivityPoints") or 0),
            "rank": 0, "auto_approval": auto}

def fetch_guild_members(guild_id, uid, password):
    params = urllib.parse.urlencode({"guild_id": guild_id, "uid": uid, "password": password})
    code, js, _ = _http_get_json(f"{GUILD_MEMBERS_API}?{params}", 20, True)
    if code != 200 or not isinstance(js, dict) or not js.get("success"): return None
    out = {}
    for m in js.get("members") or []:
        u = str(m.get("uid") or "")
        if not u: continue
        out[u] = {"nickname": m.get("nickname",""), "uid": u,
                  "totalGlory": int(m.get("totalGlory") or 0),
                  "weeklyGlory": int(m.get("weeklyGlory") or 0),
                  "level": int(m.get("level") or 1),
                  "role": m.get("role", "Member")}
    return out

def send_join(guild_id, uid, password, region):
    params = urllib.parse.urlencode({"guild_id": guild_id, "uid": uid, "password": password, "region": region})
    req = urllib.request.Request(f"{GUILD_JOIN_API}?{params}", headers={"User-Agent": "RBC-GLORY/30"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                js = json.loads(body)
                msg = str(js.get("message") or js.get("error") or "OK")
                ml = msg.lower(); st = str(js.get("status","")).lower()
                if js.get("success") is False or "error" in ml: return False, msg[:140]
                if st in ("failed","failure","error","invalid"): return False, f"{st}: {msg}"[:140]
                if "already" in ml or "pending" in ml or "request" in ml: return True, f"request_sent: {msg}"[:140]
                if js.get("success") is True or st in ("ok","success","joined"): return True, msg[:140]
                return 200 <= resp.status < 300, msg[:140]
            except Exception:
                return 200 <= resp.status < 300, "OK"
    except Exception as e:
        return False, str(e)[:140]

def send_bio(uid, password):
    params = urllib.parse.urlencode({"bio": SETTINGS["bio_text"], "uid": uid, "password": password})
    req = urllib.request.Request(f"{BIO_API}?{params}", headers={"User-Agent": "RBC-GLORY/30"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp: return 200 <= resp.status < 300
    except Exception: return False

def run_gen(count, region, out_file=None):
    """Run gen.py as a subprocess and stream its output into the log.
    Every real account is written by gen.py into out_file (unique per call), so parallel
    launches never mix accounts. Timeout scales with count; partial results are kept."""
    if not os.path.exists(GEN_FILE):
        push_log("error", "gen.py not found", instance="gen"); return False
    env = os.environ.copy(); env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    env["PYTHONUNBUFFERED"] = "1"
    if out_file: env["RBC_GEN_OUT"] = out_file
    # "y" = auto-activate new guests right after registration (needed before the guild join API can log in)
    args = [sys.executable, "-u", GEN_FILE, "gen", str(count), region, "y"]
    budget = GEN_BASE_TIMEOUT + GEN_PER_ACCOUNT_TIMEOUT * max(1, count)
    try:
        proc = subprocess.Popen(args, cwd=BASE_DIR, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors="replace")
    except Exception as e:
        push_log("error", f"gen start error: {e}", instance="gen"); return False
    timer = threading.Timer(budget, lambda: (proc.poll() is None) and proc.kill())
    timer.daemon = True; timer.start()
    try:
        for line in proc.stdout:
            line = line.strip()
            if line: push_log("debug", line[:300], instance="gen")
        proc.wait()
    except Exception as e:
        push_log("error", f"gen error: {e}", instance="gen")
        try: proc.kill()
        except Exception: pass
    finally:
        timer.cancel()
    if proc.returncode not in (0, None):
        push_log("warn", f"gen exited with code {proc.returncode} (budget {budget}s)", instance="gen")
    return proc.returncode == 0

def load_generated(region, path=None):
    path = path or os.path.join(GEN_OUT_DIR, f"accounts-{region.upper()}.json")
    if not os.path.exists(path): return []
    try:
        with open(path, encoding="utf-8") as f: raw = json.load(f)
    except Exception: return []
    if not isinstance(raw, list): return []
    out = []
    for a in raw:
        if isinstance(a, dict):
            u = str(a.get("uid") or a.get("account_id") or "").strip()
            p = str(a.get("password") or "").strip()
            if u and p:
                out.append({"uid": u, "password": p, "name": str(a.get("name") or "").strip(),
                            "account_id": str(a.get("account_id") or "").strip()})
    return out

def write_group_accounts(gid, accounts):
    path = group_accounts_path(gid)
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([{"uid": a["uid"], "password": a["password"]} for a in accounts], f, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        push_log("error", f"accounts write error: {e}", instance=gid); return False
    try:
        meta_tmp = group_accounts_meta_path(gid) + ".tmp"
        with open(meta_tmp, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=1)
        os.replace(meta_tmp, group_accounts_meta_path(gid))
    except Exception as e:
        push_log("warn", f"meta write error: {e}", instance=gid)
    return True

def start_engine_for_group(gid):
    if not os.path.exists(MAIN_FILE): return None, "app.py not found"
    env = os.environ.copy()
    env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    env["RBC_SKIP_WEB"] = "1"
    env["RBC_ACCOUNTS_FILE"] = group_accounts_path(gid)
    env["RBC_GROUP_ID"] = gid
    try:
        log_fh = open(group_log_path(gid), "ab", buffering=0)
        kwargs = {"cwd": group_dir(gid), "env": env, "stdout": log_fh, "stderr": subprocess.STDOUT}
        if sys.platform != "win32":
            try: kwargs["preexec_fn"] = os.setsid
            except Exception: pass
        proc = subprocess.Popen([sys.executable, MAIN_FILE], **kwargs)
        return proc, None
    except Exception as e:
        return None, str(e)

def stop_engine_process(proc):
    if not proc: return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill","/F","/T","/PID",str(proc.pid)], capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(1)
                try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception: pass
            except Exception: proc.kill()
    except Exception:
        try: proc.kill()
        except Exception: pass

# ═══════════════ Workers ═══════════════
async def _auto_restart_loop():
    while True:
        try:
            mins = SETTINGS.get("auto_restart_mins", 15)
            if mins > 0:
                await asyncio.sleep(mins * 60)
                for gid, g in list(GROUPS_DB.items()):
                    if g.get("status") != "RUNNING": continue
                    proc = g.get("engine_proc")
                    if proc:
                        stop_engine_process(proc)
                        g["engine_proc"] = None; g["engine_pid"] = None
                        await asyncio.sleep(2)
                    saved = [{"uid":a["uid"],"password":a.get("password",DEFAULT_PASSWORD),
                              "name":a.get("name",""),"account_id":a.get("account_id","")}
                             for a in g.get("accounts", []) if a.get("uid")]
                    if not saved: continue
                    write_group_accounts(gid, saved)
                    new_proc, err = start_engine_for_group(gid)
                    if not err:
                        g["engine_proc"] = new_proc; g["engine_pid"] = new_proc.pid
                        g["stage_note"] = f"Auto-restarted ({mins}m)"
                        save_json(DB_FILE, GROUPS_DB)
                        push_log("info", f"Auto-restarted engine", instance=gid)
            else:
                await asyncio.sleep(60)
        except Exception as e:
            push_log("error", f"Auto-restart error: {e}"); await asyncio.sleep(60)

def _refund_launch(g):
    """Give the launch credit back once if the launch failed before any bot started."""
    try:
        amt = g.get("credit_charged") or 0
        if not amt or g.get("credit_refunded"): return
        usr = USERS_DB.get(g.get("owner"))
        if not usr or usr.get("is_admin"): return
        usr["credits"] = usr.get("credits", 0) + amt
        g["credit_refunded"] = True
        save_json(USERS_FILE, USERS_DB)
        push_log("info", f"Launch failed — {amt} credit refunded", instance=g.get("group_id"), user=g.get("owner"))
    except Exception as e:
        push_log("error", f"auto-refund error: {e}")

async def create_and_join(region, guild_id, count, group):
    gid = group["group_id"]; start_time = time.time()
    def check_timeout():
        if time.time() - start_time > 600: raise TimeoutError("Global timeout 10m")
    def set_stage(stage, note=""):
        group["stage"] = stage; group["stage_note"] = note; group["stage_at"] = int(time.time())
        if stage in ("GENERATING","JOINING","WAITING_APPROVAL","STARTING_ENGINE"):
            group["status"] = "GENERATING"
        elif stage == "RUNNING": group["status"] = "RUNNING"
        elif stage == "FAILED": group["status"] = "FAILED"; _refund_launch(group)
        save_json(DB_FILE, GROUPS_DB)
        push_log("info", f"stage={stage} {note}", instance=gid)

    try:
        set_stage("GENERATING", f"spawning {count} guests")
        info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, guild_id, region)
        if not info:
            group["error"] = "Guild API down"; set_stage("FAILED"); return
        initial_count = info["current_members"]
        auto_app = info.get("auto_approval", True)
        group["initial_member_count"] = initial_count
        save_json(DB_FILE, GROUPS_DB)

        accs = []
        global MANUAL_ACCOUNTS
        # 1) admin-provided manual accounts first (use as many as available)
        manual_pool = MANUAL_ACCOUNTS.get(region, [])
        take = min(len(manual_pool), count)
        if take:
            for a in manual_pool[:take]:
                u_ = str(a.get("uid","")).strip(); p_ = str(a.get("pass") or a.get("password","")).strip()
                if u_ and p_: accs.append({"uid": u_, "password": p_})
            MANUAL_ACCOUNTS[region] = manual_pool[take:]
            save_json(MANUAL_ACCS_FILE, MANUAL_ACCOUNTS)
        # 2) top up with REAL accounts from gen.py (never fake UIDs)
        if len(accs) < count:
            gen_out = os.path.join(GEN_OUT_DIR, f"run-{gid}.json")
            try: os.remove(gen_out)
            except Exception: pass
            retries = SETTINGS.get("join_retry_rounds", 5)
            loop = asyncio.get_event_loop()
            for attempt in range(1, retries + 1):
                check_timeout()
                if GROUPS_DB.get(gid, {}).get("status") not in ("GENERATING","RUNNING"): return
                need = count - len(accs)
                if need <= 0: break
                set_stage("GENERATING", f"gen attempt {attempt}/{retries} (need {need})")
                before = len(load_generated(region, gen_out))
                await loop.run_in_executor(None, run_gen, need, region, gen_out)
                got = load_generated(region, gen_out)
                push_log("info", f"gen attempt {attempt}: +{len(got)-before} real accounts", instance=gid)
                seen = {a["uid"] for a in accs}
                for a in got:
                    if len(accs) >= count: break
                    if a["uid"] not in seen: accs.append(a); seen.add(a["uid"])
                if len(accs) >= count: break
                await asyncio.sleep(2)
            try: os.remove(gen_out)
            except Exception: pass

        if not accs:
            group["error"] = "Gen failed: no account could be generated (check gen logs)"; set_stage("FAILED"); return
        if len(accs) < count:
            push_log("warn", f"only {len(accs)}/{count} accounts available — continuing with those", instance=gid)

        pool = accs[-count:]
        group["pending_accounts"] = [{"uid":a["uid"],"password":a["password"],
                                       "name":a.get("name",""),"account_id":a.get("account_id",""),
                                       "status":"READY"} for a in pool]
        save_json(DB_FILE, GROUPS_DB)

        set_stage("JOINING", f"sending {len(pool)} join requests")
        sent_ok = 0
        for acc in pool:
            check_timeout()
            ok, msg = await asyncio.get_event_loop().run_in_executor(None, send_join, guild_id, acc["uid"], acc["password"], region)
            if ok: sent_ok += 1
            for pa in group["pending_accounts"]:
                if pa["uid"] == acc["uid"]: pa["status"] = "REQUESTED" if ok else "JOIN_FAILED"
            save_json(DB_FILE, GROUPS_DB)
            await asyncio.sleep(1.5)

        set_stage("WAITING_APPROVAL", f"{sent_ok} requests sent")
        if auto_app:
            await asyncio.sleep(5)
            joined = pool
        else:
            target_count = initial_count + count
            wait_start = time.time()
            while time.time() - wait_start < SETTINGS.get("approval_wait_secs", 120):
                check_timeout()
                if GROUPS_DB.get(gid, {}).get("status") not in ("GENERATING","RUNNING"): return
                await asyncio.sleep(SETTINGS.get("member_check_secs", 8))
                cur = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, guild_id, region)
                if cur and cur["current_members"] >= target_count: break
            members = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_members, guild_id, pool[0]["uid"], pool[0]["password"])
            joined_count = 0
            if members:
                our = set(a["uid"] for a in pool)
                joined_count = len([u for u in members.keys() if u in our])
            joined = pool[:max(1, joined_count)] if joined_count > 0 else pool

        for acc in joined:
            check_timeout()
            await asyncio.get_event_loop().run_in_executor(None, send_bio, acc["uid"], acc["password"])
            await asyncio.sleep(1)

        if not write_group_accounts(gid, joined):
            group["error"] = "Write failed"; set_stage("FAILED"); return

        set_stage("STARTING_ENGINE", f"spawning engine for {len(joined)} bots")
        proc, err = start_engine_for_group(gid)
        if err:
            group["error"] = f"Engine: {err}"; set_stage("FAILED"); return

        group["engine_pid"] = proc.pid; group["engine_proc"] = proc
        # === FIX: started_at must be in milliseconds ===
        group["started_at"] = int(time.time() * 1000)
        group["initial_glory"] = group["total_glory"]
        group["accounts"] = [{"uid":a["uid"],"password":a["password"],"auth_uid":a["uid"],
                              "name":a.get("name","") or f"Bot_{a['uid'][:6]}",
                              "account_id":a.get("account_id",""),
                              "nickname":a.get("name","") or f"Bot_{a['uid'][:6]}",
                              "level":1,"gained_exp":0,"glory_gained":0,"matches":0,"status":"ONLINE"}
                             for a in joined]
        group["auth_uids"] = [a["uid"] for a in joined]
        group["live_members"] = {}; group["members_fetched_at"] = 0
        set_stage("RUNNING", f"{len(joined)} bots online · {_goal_secs(group)/3600:g}h timer")
        GLOBAL_STATS["bots_total"] += len(joined)
        save_json(DB_FILE, GROUPS_DB)
        asyncio.create_task(_glory_worker(gid))
        push_log("info", f"RUNNING with {len(joined)} bots", instance=gid)
    except TimeoutError as e:
        group["error"] = str(e); set_stage("FAILED")
    except Exception as e:
        group["error"] = str(e); set_stage("FAILED")

def _goal_secs(g):
    try: h = float(g.get("goal_hours") or SETTINGS.get("goal_hours", 8))
    except Exception: h = float(SETTINGS.get("goal_hours", 8))
    return max(60.0, h * 3600)

async def _glory_worker(gid):
    group = GROUPS_DB.get(gid)
    if not group: return
    start_ts = group.get("started_at", int(time.time()*1000)) / 1000.0  # Convert back to seconds
    tick = 0; last_fetch = 0
    while True:
        g = GROUPS_DB.get(gid)
        if not g or g.get("status") != "RUNNING": break
        goal_secs = _goal_secs(g)
        elapsed = time.time() - start_ts
        if elapsed >= goal_secs:
            proc = g.get("engine_proc")
            if proc: stop_engine_process(proc)
            g["status"]="COMPLETED"; g["stage"]="COMPLETED"; g["stage_note"]="Goal reached"
            g["engine_pid"]=None; g["engine_proc"]=None
            save_json(DB_FILE, GROUPS_DB); push_log("info", f"{goal_secs/3600:g}h goal reached", instance=gid); return
        proc = g.get("engine_proc")
        if proc and proc.poll() is not None:
            # Engine process died unexpectedly
            g["engine_proc"]=None; g["engine_pid"]=None
            for a in g.get("accounts", []): a["status"]="OFFLINE"
            np, err = start_engine_for_group(gid)
            if not err:
                g["engine_proc"]=np; g["engine_pid"]=np.pid
            save_json(DB_FILE, GROUPS_DB)
            
        tick += 1
        try:
            info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, g["guild_id"], g["region"])
            if info:
                g["total_glory"] = info["total_glory"]
                # If API returns 0, glory_gained is 0
                g["glory_gained"] = max(0, info["total_glory"] - g["initial_glory"])
                g["current_members"] = info["current_members"]
                g["members_online"] = info.get("members_online", 0)
                g["rank"] = info.get("rank", 0)
                g["activity_points"] = info.get("activity_points", 0)
                g["elapsed_seconds"] = int(elapsed)
                g["remaining_seconds"] = int(max(0, goal_secs - elapsed))
                save_json(DB_FILE, GROUPS_DB)
        except Exception: pass
        if time.time() - last_fetch >= SETTINGS.get("glory_refresh_secs", 60):
            last_fetch = time.time()
            try:
                members = await asyncio.get_event_loop().run_in_executor(None, _fetch_members_for_group, gid)
                if members:
                    g = GROUPS_DB.get(gid)
                    if g is not None:
                        g["live_members"] = members; g["members_fetched_at"] = int(time.time())
                        for a in g.get("accounts", []):
                            u = a.get("uid", "")
                            if u in members:
                                m = members[u]
                                a["nickname"] = m.get("nickname") or a.get("nickname") or a.get("name")
                                a["total_glory"] = m.get("totalGlory", 0)
                                a["weekly_glory"] = m.get("weeklyGlory", 0)
                                a["glory_gained"] = m.get("totalGlory", 0)
                                a["level"] = m.get("level", 1)
                                a["role"] = m.get("role", "Member")
                        save_json(DB_FILE, GROUPS_DB)
            except Exception: pass
        await asyncio.sleep(45 if tick > 2 else 20)

def _fetch_members_for_group(gid):
    g = GROUPS_DB.get(gid)
    if not g: return None
    accs = g.get("accounts") or []
    if not accs: return None
    a = accs[0]
    return fetch_guild_members(g.get("guild_id"), a.get("uid"), a.get("password"))

# ═══════════════ Helpers ═══════════════
def _group_summary(gid, g):
    accounts = []
    meta = group_accounts_meta_path(gid)
    try:
        if os.path.exists(meta):
            with open(meta) as f:
                for a in json.load(f):
                    accounts.append({"name":a.get("name",""),"uid":a.get("uid",""),
                                     "password":a.get("password",""),"account_id":a.get("account_id","")})
    except Exception: pass
    if not accounts:
        for a in g.get("accounts", []):
            accounts.append({"name":a.get("name") or a.get("nickname") or "",
                             "uid":a.get("uid",""),"password":a.get("password",""),
                             "account_id":a.get("account_id","")})
    
    engine_alive = False
    proc = g.get("engine_proc")
    if proc:
        try: engine_alive = (proc.poll() is None)
        except Exception: pass
    
    live = g.get("live_members") or {}
    for a in accounts:
        u = a.get("uid","")
        if u in live:
            m = live[u]
            a["nickname"] = m.get("nickname") or a.get("name")
            a["name"] = m.get("nickname") or a.get("name")
            a["total_glory"] = m.get("totalGlory", 0)
            a["weekly_glory"] = m.get("weeklyGlory", 0)
            a["glory_gained"] = m.get("totalGlory", 0)
            a["level"] = m.get("level", 1)
            a["role"] = m.get("role", "Member")
            a["status"] = "ONLINE" if (g.get("status") == "RUNNING" and engine_alive) else "OFFLINE"
        else:
            a["nickname"] = a.get("nickname") or a.get("name") or "Bot"
            a["name"] = a.get("name") or a.get("nickname") or "Bot"
            a.setdefault("total_glory", 0); a.setdefault("weekly_glory", 0)
            a.setdefault("glory_gained", 0); a.setdefault("level", 1)
            a.setdefault("role", "Member")
            a["status"] = "ONLINE" if (g.get("status") == "RUNNING" and engine_alive) else "OFFLINE"

    # Calculate elapsed properly using ms
    now_ms = int(time.time() * 1000)
    started_ms = g.get("started_at")
    if started_ms:
        elapsed = int((now_ms - started_ms) / 1000)
    else:
        elapsed = g.get("elapsed_seconds", 0)
        
    goal = _goal_secs(g)
    remaining = max(0, goal - elapsed) if started_ms else g.get("remaining_seconds", goal)
    
    return {"group_id": gid, "guild_id": g.get("guild_id"),
            "guild_name": g.get("guild_name"), "guild_level": g.get("guild_level"),
            "region": g.get("region"), "leader_name": g.get("leader_name"),
            "leader_id": g.get("leader_id"), "bio": g.get("bio") or g.get("slogan"),
            "rank": g.get("rank",0), "activity_points": g.get("activity_points",0),
            "status": g.get("status"), "stage": g.get("stage"),
            "stage_note": g.get("stage_note"), "stage_at": g.get("stage_at"),
            "created_at": g.get("created_at"),
            "initial_member_count": g.get("initial_member_count",0),
            "current_members": g.get("current_members",0),
            "max_members": g.get("max_members",35),
            "members_online": g.get("members_online",0),
            "approved_count": g.get("approved_count",0),
            "total_glory": g.get("total_glory",0),
            "initial_glory": g.get("initial_glory",0),
            "glory_gained": g.get("glory_gained",0),
            "engine_pid": g.get("engine_pid"),
            "elapsed": elapsed, "remaining": remaining,
            "online_bots": len(accounts) if (g.get("status") == "RUNNING" and engine_alive) else 0,
            "target_bots": SETTINGS.get("bot_count", 4),
            "bot_count": len(accounts),
            "baseline_weekly": g.get("baseline_weekly", 0),
            "total_activity": g.get("activity_points", 0),
            "goal_hours": round(goal / 3600, 4),
            "started_at": started_ms,  # Return in MS for JS
            "members_fetched_at": g.get("members_fetched_at", 0),
            "accounts": accounts, "error": g.get("error"),
            "owner": g.get("owner", ADMIN_USER)}

# ═══════════════ Pages ═══════════════
async def page_index(request):
    try:
        with open(os.path.join(TEMPLATES_DIR, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
            return web.Response(text=html, content_type="text/html", charset="utf-8")
    except Exception:
        return web.Response(text="index.html missing", status=404)

async def page_admin(request):
    try:
        with open(os.path.join(TEMPLATES_DIR, "admin.html"), "r", encoding="utf-8") as f:
            html = f.read()
            return web.Response(text=html, content_type="text/html", charset="utf-8")
    except Exception:
        return web.Response(text="admin.html missing", status=404)

# ═══════════════ Auth ═══════════════
async def api_login(request):
    try:
        data = await request.json()
        u = USERS_DB.get(data.get("username"))
        if u and u.get("banned") and not u.get("is_admin"):
            return web.json_response({"ok": False, "error": "Account banned"}, status=403)
        if u and u.get("password") == data.get("password"):
            tok = new_session(u["username"])
            resp = web.json_response({"ok": True,
                "user": {k:v for k,v in u.items() if k != "password"}})
            resp.set_cookie("rbc_sess", tok, max_age=86400*7, httponly=True, samesite="Lax")
            return resp
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

# ═══════════════ Payments (FamPay / UPI, verified through Gmail IMAP) ═══════════════
import re as _re, imaplib, email as _email
from email.header import decode_header as _dh
from email.utils import parsedate_to_datetime as _pdt
from datetime import datetime as _dt, timedelta as _td, timezone as _tz

PAY_LOCK = asyncio.Lock()
_PAY_ATTEMPTS: Dict[str, list] = {}

def _mask(s): return (s[:2] + "•••" + s[-2:]) if s and len(s) > 6 else ("•••" if s else "")
def _dec(v):
    try: return "".join((p.decode(c or "utf-8", "ignore") if isinstance(p, bytes) else p) for p, c in _dh(v or ""))
    except Exception: return str(v or "")

def _mail_text(msg):
    parts = []
    for p in (msg.walk() if msg.is_multipart() else [msg]):
        if p.get_content_type() in ("text/plain", "text/html"):
            try: t = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "ignore")
            except Exception: continue
            if p.get_content_type() == "text/html":
                t = _re.sub(r"<(script|style).*?</\1>", " ", t, flags=_re.S | _re.I)
                t = _re.sub(r"<[^>]+>", " ", t)
            parts.append(t)
    return _re.sub(r"\s+", " ", " ".join(parts))

_AMT = _re.compile(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", _re.I)
def _extract_amount(text):
    best = None; best_score = -9
    for mt in _AMT.finditer(text):
        try: val = float(mt.group(1).replace(",", ""))
        except Exception: continue
        before = text[max(0, mt.start() - 45):mt.start()].lower()
        score = 0
        if any(k in before for k in ("balance", "bal ", "limit", "available")): score -= 5
        if any(k in before for k in ("received", "credited", "paid", "sent", "amount", "payment of", "money")): score += 3
        if score > best_score: best, best_score = val, score
    return best

def _imap_fetch(cfg, days=3, limit=60):
    """Return recent mails (INBOX + Spam) as dicts (blocking). Raises on login errors."""
    if not cfg.get("gmail") or not cfg.get("app_password"):
        raise RuntimeError("Gmail + app password not set in admin panel")
    M = imaplib.IMAP4_SSL(cfg.get("imap_host") or "imap.gmail.com", 993, timeout=25)
    out = []; seen = set()
    try:
        M.login(cfg["gmail"], cfg["app_password"].replace(" ", ""))
        since = (_dt.now(_tz.utc) - _td(days=days)).strftime("%d-%b-%Y")
        for folder, lim in (("INBOX", limit), ('"[Gmail]/Spam"', 20)):
            try:
                typ, _ = M.select(folder, readonly=True)
                if typ != "OK": continue
                typ, data = M.search(None, "SINCE", since)
                ids = (data[0].split() if data and data[0] else [])[-lim:]
                if not ids: continue
                typ, md = M.fetch(b",".join(ids).decode(), "(RFC822)")
                for part in md or []:
                    if not isinstance(part, tuple): continue
                    msg = _email.message_from_bytes(part[1])
                    try: when = _pdt(msg.get("Date")).astimezone(_tz.utc)
                    except Exception: when = None
                    txt = _mail_text(msg)
                    mid = (msg.get("Message-ID") or "").strip() or ("h:" + str(hash((msg.get("From"), msg.get("Date"), msg.get("Subject"), txt[:300]))))
                    if mid in seen: continue
                    seen.add(mid)
                    out.append({"from": _dec(msg.get("From")), "subject": _dec(msg.get("Subject")), "date": when,
                                "text": txt, "mail_id": mid, "folder": "Spam" if "Spam" in folder else "Inbox"})
            except Exception:
                if folder == "INBOX": raise
        out.sort(key=lambda x: x["date"] or _dt.min.replace(tzinfo=_tz.utc), reverse=True)
        return out
    finally:
        try: M.logout()
        except Exception: pass

def _id_patterns(pid):
    """FamPay txn id looks like FMPIB7007503780; also accept just the 10-12 digit part (and vice versa)."""
    pats = [r"(?<![A-Z0-9])" + _re.escape(pid) + r"(?![A-Z0-9])"]
    mm = _re.fullmatch(r"[A-Z]{2,8}(\d{10,12})", pid)
    digits = mm.group(1) if mm else (pid if _re.fullmatch(r"\d{10,12}", pid) else None)
    if digits: pats.append(r"(?<!\d)" + digits + r"(?!\d)")
    return [_re.compile(p) for p in pats]

def _mail_has_id(mm, pats):
    blob = " ".join((mm["from"], mm["subject"], mm["text"])).upper()
    return any(p.search(blob) for p in pats)

def _is_credit(cfg, mm):
    blob = " | ".join((mm["subject"], mm["text"])).lower()
    deb = [k.strip().lower() for k in str(cfg.get("debit_keywords") or "").split(",") if k.strip()]
    cre = [k.strip().lower() for k in str(cfg.get("credit_keywords") or "").split(",") if k.strip()]
    if any(k in blob for k in deb): return False
    return (not cre) or any(k in blob for k in cre)

def _filter_ok(cfg, mm):
    flt = str(cfg.get("sender_filter") or "").strip().lower()
    blob = (mm["from"] + " " + mm["subject"] + " " + mm["text"]).lower()
    if not flt:
        return True
    # FamPay notification emails may identify the product as "FamApp".
    if flt in ("fampay", "fam pay", "famapp", "fam app"):
        return any(alias in blob for alias in ("fampay", "fam pay", "famapp", "fam app"))
    return flt in blob

def _find_payment(cfg, utr):
    """-> (status, info). status: found | not_found | old | not_credit"""
    mails = _imap_fetch(cfg, days=max(2, int(cfg.get("max_age_hours", 48)) // 24 + 2))
    pats = _id_patterns(utr)
    saw_old = saw_debit = False
    for mm in mails:
        if not _mail_has_id(mm, pats) or not _filter_ok(cfg, mm): continue
        if mm["date"] and (_dt.now(_tz.utc) - mm["date"]) > _td(hours=float(cfg.get("max_age_hours", 48))):
            saw_old = True; continue
        if not _is_credit(cfg, mm):
            saw_debit = True; continue
        return "found", {"mail_id": mm["mail_id"], "amount": _extract_amount(mm["text"] + " " + mm["subject"]),
                         "from": mm["from"][:80], "subject": mm["subject"][:120]}
    return ("old" if saw_old else "not_credit" if saw_debit else "not_found"), {}

# ═══════════════ RBC PAY gateway (auto amount-match, no UTR) ═══════════════
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
ORDERS = load_json(ORDERS_FILE, {})
_GW_THROTTLE: Dict[str, float] = {}

def _gw_enabled(): return bool(PAY_CFG.get("gateway_key"))

def _gw_call(path, params=None, timeout=20):
    """GET to the gateway with Bearer auth. Returns (http_status, json_or_None)."""
    base = str(PAY_CFG.get("gateway_base") or "").rstrip("/")
    if not base.startswith("https://"): raise RuntimeError("Gateway base URL must start with https://")
    url = base + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + PAY_CFG["gateway_key"],
                                               "Accept": "application/json", "User-Agent": "FFGLORY/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace"); code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
        try: body = e.read().decode("utf-8", "replace")
        except Exception: body = ""
    try: return code, json.loads(body)
    except Exception: return code, None

def _settle_order(order_id):
    """Check order at the gateway; credit the user once. -> dict(status, credits?, balance?)"""
    o = ORDERS.get(order_id)
    if not o: return {"status": "unknown"}
    if o["status"] == "paid": return {"status": "paid", "credits": o["credits"]}
    code, js = _gw_call("/api/verify.php", {"order_id": order_id})
    if code != 200 or not isinstance(js, dict): return {"status": "pending", "gateway_error": code}
    d = js.get("data") or {}
    st = str(d.get("order_status") or "").upper()
    if js.get("status") == "success" and st == "SUCCESS":
        usr = USERS_DB.get(o["user"])
        if not usr: return {"status": "pending"}
        o["status"] = "paid"; o["utr"] = d.get("utr"); o["paid_at"] = time.time()
        usr["credits"] = usr.get("credits", 0) + o["credits"]
        PAYMENTS["ORD:" + order_id] = {"user": o["user"], "status": "verified", "ts": time.time(), "amount": o["payable"],
                                       "credits": o["credits"], "price": o["price"], "mail_id": "ORD:" + order_id,
                                       "mail_subject": "RBC PAY " + str(d.get("utr") or "")}
        save_json(USERS_FILE, USERS_DB); save_json(PAY_FILE, PAYMENTS); save_json(ORDERS_FILE, ORDERS)
        push_log("info", f"Gateway payment ₹{o['payable']} order {order_id} +{o['credits']} credits", user=o["user"])
        return {"status": "paid", "credits": o["credits"], "balance": usr["credits"]}
    if js.get("status") == "expired" or st in ("EXPIRED", "FAILED", "CANCELLED"):
        o["status"] = "expired"; save_json(ORDERS_FILE, ORDERS); return {"status": "expired"}
    return {"status": "pending"}

async def api_pay_order(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    if not _gw_enabled(): return web.json_response({"error": "Gateway not enabled"}, status=503)
    try:
        d = await request.json(); credits = int(d.get("credits") or 0)
        if credits < int(PAY_CFG.get("min_credits", 1)) or credits > 10000:
            return web.json_response({"error": f"Credits must be between {PAY_CFG.get('min_credits', 1)} and 10000"}, status=400)
        now = time.time()
        open_orders = [o for o in ORDERS.values() if o["user"] == u["username"] and o["status"] == "created" and now - o["ts"] < 1800]
        if len(open_orders) >= 3:
            return web.json_response({"error": "You have 3 unpaid orders open. Pay one or wait 30 minutes."}, status=429)
        price = float(PAY_CFG["price"]); amount = round(credits * price, 2)
        amt = f"{amount:.2f}".rstrip("0").rstrip(".")
        code, js = await asyncio.get_event_loop().run_in_executor(None, lambda: _gw_call("/api/create_order.php", {"amount": amt, "customer_name": u["username"]}))
        if code != 200 or not isinstance(js, dict) or js.get("status") != "success":
            msg = (js or {}).get("message") if isinstance(js, dict) else None
            push_log("error", f"Gateway create_order failed {code}: {msg}")
            return web.json_response({"error": msg or "Gateway error. Try again."}, status=502)
        g = js["data"]; oid = str(g.get("order_id"))
        ORDERS[oid] = {"user": u["username"], "credits": credits, "amount": amount, "price": price,
                       "payable": float(g.get("payable_amount") or amount), "status": "created", "ts": now}
        save_json(ORDERS_FILE, ORDERS)
        return web.json_response({"ok": True, "order_id": oid, "credits": credits, "amount": amount,
                                   "payable_amount": g.get("payable_amount") or amt, "qr_url": g.get("qr_url"),
                                   "checkout_url": g.get("checkout_url"), "upi_link": g.get("upi_link"),
                                   "upi_id": g.get("upi_id"), "expires_at": g.get("expires_at")})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_pay_order_status(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    oid = str(request.query.get("order_id") or "")
    o = ORDERS.get(oid)
    if not o or o["user"] != u["username"]: return web.json_response({"error": "Order not found"}, status=404)
    now = time.time()
    if o["status"] != "paid" and now - _GW_THROTTLE.get(oid, 0) < 3:
        return web.json_response({"status": o["status"] if o["status"] != "created" else "pending"})
    _GW_THROTTLE[oid] = now
    async with PAY_LOCK:
        r = await asyncio.get_event_loop().run_in_executor(None, _settle_order, oid)
    if r.get("status") == "paid": r["balance"] = u.get("credits", 0)
    return web.json_response(r)

async def api_pay_webhook(request):
    """Gateway calls this on payment.success. We never trust the body: the order is re-verified through the API."""
    try:
        d = await request.json(); oid = str(d.get("order_id") or "")
        if oid in ORDERS:
            async with PAY_LOCK:
                await asyncio.get_event_loop().run_in_executor(None, _settle_order, oid)
    except Exception: pass
    return web.json_response({"ok": True})

async def api_pay_pending(request):
    """Settle the user's recent unpaid orders (user paid then closed the page)."""
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    now = time.time(); done = 0
    recent = [oid for oid, o in ORDERS.items() if o["user"] == u["username"] and o["status"] == "created" and now - o["ts"] < 7200][-5:]
    for oid in recent:
        async with PAY_LOCK:
            r = await asyncio.get_event_loop().run_in_executor(None, _settle_order, oid)
        if r.get("status") == "paid": done += 1
    return web.json_response({"ok": True, "settled": done, "balance": u.get("credits", 0)})

async def api_admin_pay_gwtest(request):
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    if not _gw_enabled(): return web.json_response({"error": "Save the API key first"}, status=400)
    try:
        code, js = await asyncio.get_event_loop().run_in_executor(None, lambda: _gw_call("/api/verify.php", {"order_id": "ORD_TEST_CHECK"}))
        if code in (401, 403): return web.json_response({"error": f"Gateway rejected the key ({code}): {(js or {}).get('message', '')}"}, status=400)
        if code in (200, 404) or (isinstance(js, dict) and js): return web.json_response({"ok": True, "http": code, "message": (js or {}).get("message", "reachable")})
        return web.json_response({"error": f"Unexpected gateway response ({code})"}, status=502)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


def _cfg_public():
    c = dict(PAY_CFG); pw = c.pop("app_password", ""); gk = c.pop("gateway_key", "")
    c["has_password"] = bool(pw); c["password_hint"] = _mask(pw)
    c["has_gateway_key"] = bool(gk); c["gateway_hint"] = _mask(gk)
    return c

async def api_pay_info(request):
    return web.json_response({"price": PAY_CFG["price"], "upi_id": PAY_CFG["upi_id"], "payee": PAY_CFG["payee"],
                              "min_credits": PAY_CFG["min_credits"],
                              "gateway": _gw_enabled(),
                              "enabled": bool(PAY_CFG.get("gmail") and PAY_CFG.get("app_password"))})

async def api_pay_history(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    rows = [{"utr": k, **{x: v.get(x) for x in ("amount", "credits", "ts", "status")}}
            for k, v in PAYMENTS.items() if v.get("user") == u["username"]]
    rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    return web.json_response({"payments": rows[:50]})

async def api_pay_verify(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    try:
        data = await request.json()
        utr = _re.sub(r"[^A-Za-z0-9]", "", str(data.get("utr") or "")).upper()
        fampay_id = _re.sub(r"\D", "", str(data.get("fampay_id") or ""))
        if not (10 <= len(utr) <= 32) or sum(c.isdigit() for c in utr) < 4:
            return web.json_response({"error": "Enter a valid UTR / Transaction ID (10-12 digits, or the FamPay transaction ID)"}, status=400)
        if not (PAY_CFG.get("gmail") and PAY_CFG.get("app_password")):
            return web.json_response({"error": "Payments are not enabled yet. Contact admin."}, status=503)
        now = time.time(); hist = [t for t in _PAY_ATTEMPTS.get(u["username"], []) if now - t < 600]
        if len(hist) >= 8:
            return web.json_response({"error": "Too many attempts. Wait a few minutes."}, status=429)
        hist.append(now); _PAY_ATTEMPTS[u["username"]] = hist
        async with PAY_LOCK:                      # one verification at a time = no double spend
            if utr in PAYMENTS:
                return web.json_response({"error": "This UTR / Transaction ID was already used"}, status=409)
            if fampay_id and (len(fampay_id) != 10 or any(p.get("fampay_id") == fampay_id for p in PAYMENTS.values())):
                return web.json_response({"error": "FamPay ID must be 10 digits and can only be used once"}, status=409)
            try:
                st, info = await asyncio.get_event_loop().run_in_executor(None, _find_payment, dict(PAY_CFG), utr)
            except Exception as e:
                push_log("error", f"Payment mailbox error: {e}")
                return web.json_response({"error": "Could not check payment right now. Try again in a minute."}, status=502)
            if st == "not_found":
                return web.json_response({"error": "Payment not found yet. Wait 1-2 minutes after paying and try again."}, status=404)
            if st == "old":
                return web.json_response({"error": "This payment is too old to verify. Contact admin."}, status=400)
            if st == "not_credit":
                return web.json_response({"error": "This UTR is not a received payment."}, status=400)
            if any(p.get("mail_id") and p.get("mail_id") == info.get("mail_id") for p in PAYMENTS.values()):
                return web.json_response({"error": "This payment was already claimed (same payment, different ID)"}, status=409)
            amount = info.get("amount"); price = float(PAY_CFG["price"])
            if amount is None:                    # mail found but amount unreadable -> admin approves manually
                PAYMENTS[utr] = {"user": u["username"], "status": "pending", "ts": now, "amount": None, "credits": 0, "mail_id": info.get("mail_id"), "fampay_id": fampay_id or None}
                save_json(PAY_FILE, PAYMENTS)
                return web.json_response({"error": "Payment found but amount unreadable. Sent to admin for approval."}, status=202)
            credits = int((amount + 1e-6) // price)
            if credits < int(PAY_CFG.get("min_credits", 1)):
                return web.json_response({"error": f"Paid ₹{amount:g}; minimum is {PAY_CFG['min_credits']} credit(s) = ₹{price * PAY_CFG['min_credits']:g}. Contact admin."}, status=400)
            u["credits"] = u.get("credits", 0) + credits
            PAYMENTS[utr] = {"user": u["username"], "status": "verified", "ts": now, "amount": amount,
                             "credits": credits, "price": price, "mail_id": info.get("mail_id"), "fampay_id": fampay_id or None, "mail_from": info.get("from"), "mail_subject": info.get("subject")}
            save_json(USERS_FILE, USERS_DB); save_json(PAY_FILE, PAYMENTS)
            push_log("info", f"Payment ₹{amount:g} UTR {utr} +{credits} credits", user=u["username"])
            return web.json_response({"ok": True, "credits": credits, "amount": amount, "balance": u["credits"]})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_pay(request):
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    rows = [{"utr": k, **v} for k, v in PAYMENTS.items()]
    rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    return web.json_response({"config": _cfg_public(), "payments": rows[:200],
                              "total": round(sum(r.get("amount") or 0 for r in rows if r.get("status") == "verified"), 2)})

async def api_admin_pay_config(request):
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    try:
        d = await request.json()
        if "price" in d:
            p = float(d["price"])
            if p <= 0: return web.json_response({"error": "Price must be above 0"}, status=400)
            PAY_CFG["price"] = int(p) if p == int(p) else p
        for k in ("upi_id", "payee", "gmail", "sender_filter", "credit_keywords", "debit_keywords", "imap_host"):
            if k in d: PAY_CFG[k] = str(d[k] or "").strip()
        for k in ("max_age_hours", "min_credits"):
            if k in d: PAY_CFG[k] = max(1, int(d[k]))
        if "gateway_base" in d:
            gb = str(d["gateway_base"] or "").strip().rstrip("/")
            if gb and not gb.startswith("https://"): return web.json_response({"error": "Gateway URL must start with https://"}, status=400)
            if gb: PAY_CFG["gateway_base"] = gb
        if str(d.get("gateway_key") or "").strip(): PAY_CFG["gateway_key"] = str(d["gateway_key"]).strip()
        if d.get("clear_gateway"): PAY_CFG["gateway_key"] = ""
        if str(d.get("app_password") or "").strip(): PAY_CFG["app_password"] = str(d["app_password"]).replace(" ", "")
        if d.get("clear_password"): PAY_CFG["app_password"] = ""
        save_json(PAY_CFG_FILE, PAY_CFG)
        push_log("info", f"Payment settings updated (price ₹{PAY_CFG['price']})")
        return web.json_response({"ok": True, "config": _cfg_public()})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_pay_test(request):
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    try:
        mails = await asyncio.get_event_loop().run_in_executor(None, lambda: _imap_fetch(dict(PAY_CFG), days=3, limit=40))
        sample = []
        for mm in mails[:12]:
            blob = mm["from"] + " " + mm["subject"] + " " + mm["text"]
            ids = _re.findall(r"(?<![A-Za-z0-9])(?:[A-Za-z]{2,8})?\d{10,12}(?!\d)", blob)
            sample.append({"from": mm["from"][:45], "subject": mm["subject"][:60], "folder": mm["folder"],
                           "ids": ids[:3], "amount": _extract_amount(mm["text"] + " " + mm["subject"]),
                           "filter_ok": _filter_ok(PAY_CFG, mm),
                           "kind": "credit" if _is_credit(PAY_CFG, mm) else "ignored (debit)"})
        return web.json_response({"ok": True, "mails_3d": len(mails), "recent": sample})
    except imaplib.IMAP4.error:
        return web.json_response({"error": "Gmail login failed. Use a 16-char App Password (2-Step Verification must be on) and enable IMAP."}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_pay_lookup(request):
    """Admin debug: why is this UTR / transaction id not accepted?"""
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    try:
        d = await request.json()
        pid = _re.sub(r"[^A-Za-z0-9]", "", str(d.get("id") or "")).upper()
        if len(pid) < 6: return web.json_response({"error": "Enter the ID"}, status=400)
        mails = await asyncio.get_event_loop().run_in_executor(None, lambda: _imap_fetch(dict(PAY_CFG), days=max(3, int(PAY_CFG.get("max_age_hours", 48)) // 24 + 2)))
        pats = _id_patterns(pid)
        hits = []
        for mm in mails:
            if not _mail_has_id(mm, pats): continue
            age = (_dt.now(_tz.utc) - mm["date"]).total_seconds() / 3600 if mm["date"] else None
            hits.append({"from": mm["from"][:60], "subject": mm["subject"][:80], "folder": mm["folder"],
                         "filter_ok": _filter_ok(PAY_CFG, mm), "credit": _is_credit(PAY_CFG, mm),
                         "amount": _extract_amount(mm["text"] + " " + mm["subject"]),
                         "age_hours": round(age, 1) if age is not None else None})
        if not hits: why = f"No mail in the last days (Inbox+Spam, {len(mails)} scanned) contains this ID. The payment email has not arrived in this Gmail."
        elif not any(h["filter_ok"] for h in hits): why = "Mail found but Sender filter (" + str(PAY_CFG.get("sender_filter")) + ") does not match. Clear or change the filter."
        elif not any(h["credit"] for h in hits): why = "Mail found but treated as a debit. Edit credit/debit keywords."
        elif all((h["age_hours"] or 0) > float(PAY_CFG.get("max_age_hours", 48)) for h in hits): why = "Mail found but older than Max payment age."
        else: why = "OK: this ID would be accepted."
        used = pid in PAYMENTS
        return web.json_response({"ok": True, "why": why, "already_used": used, "matches": hits})
    except imaplib.IMAP4.error:
        return web.json_response({"error": "Gmail login failed"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_pay_approve(request):
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    try:
        d = await request.json(); utr = str(d.get("utr") or ""); credits = int(d.get("credits") or 0)
        async with PAY_LOCK:
            p = PAYMENTS.get(utr)
            if not p or p.get("status") != "pending" or credits < 1:
                return web.json_response({"error": "Nothing to approve"}, status=400)
            usr = USERS_DB.get(p["user"])
            if not usr: return web.json_response({"error": "User missing"}, status=400)
            usr["credits"] = usr.get("credits", 0) + credits
            p.update({"status": "verified", "credits": credits, "approved_by": "admin"})
            save_json(USERS_FILE, USERS_DB); save_json(PAY_FILE, PAYMENTS)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def page_qr(request):
    try:
        with open(os.path.join(TEMPLATES_DIR, "qr.png"), "rb") as f:
            return web.Response(body=f.read(), content_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        return web.Response(status=404)

async def api_signup(request):
    try:
        data = await request.json()
        user, pwd = data.get("username"), data.get("password")
        if not user or not pwd: return web.json_response({"error": "Empty"}, status=400)
        if len(pwd) < 8: return web.json_response({"error": "Password min 8 chars"}, status=400)
        if user in USERS_DB: return web.json_response({"error": "User exists"}, status=409)
        USERS_DB[user] = {"username": user, "password": pwd,
                          "email": data.get("email",""),
                          "is_admin": False, "credits": 0, "groups": []}
        save_json(USERS_FILE, USERS_DB)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_me(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    return web.json_response({"user": {k:v for k,v in u.items() if k != "password"}})

async def api_logout(request):
    tok = request.cookies.get("rbc_sess")
    if tok: SESSIONS.pop(tok, None)
    resp = web.json_response({"ok": True}); resp.del_cookie("rbc_sess")
    return resp

# ═══════════════ Core API (index.html) ═══════════════
async def api_stats(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    groups = [g for gid, g in GROUPS_DB.items() if u.get("is_admin") or g.get("owner") == u["username"]]
    online = sum(len(g.get("accounts", [])) for g in groups if g.get("status") == "RUNNING")
    running = sum(1 for g in groups if g.get("status") == "RUNNING")
    glory = sum(g.get("glory_gained", 0) for g in groups)
    return web.json_response({"total_accounts": sum(len(g.get("accounts", [])) for g in groups),
                              "online_bots": online, "matches_started": 0,
                              "total_gained_exp": 0, "total_glory_pushed": glory,
                              "uptime": int(time.time() - GLOBAL_STATS["started_at"]),
                              "groups_total": len(groups), "groups_running": running,
                              "credits": u.get("credits", 0), "total_glory": glory})

async def api_groups(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    out = [_group_summary(gid, g) for gid, g in GROUPS_DB.items()
           if u.get("is_admin") or g.get("owner") == u["username"]]
    return web.json_response({"groups": out})

async def api_group_log(request):
    gid = str(request.query.get("group_id","")).strip()
    if gid not in GROUPS_DB: return web.json_response({"ok": False, "error": "not found"}, status=404)
    s = _group_summary(gid, GROUPS_DB[gid])
    return web.json_response({"ok": True, "bots": s["accounts"],
                              "total_bot_glory": sum(b.get("total_glory", 0) for b in s["accounts"])})

async def api_guild_info(request):
    gid = str(request.query.get("guild_id","")).strip()
    region = str(request.query.get("region", DEFAULT_REGION)).upper()
    if region not in VALID_REGIONS: region = DEFAULT_REGION
    if not gid.isdigit(): return web.json_response({"ok": False, "error": "Invalid guild_id"}, status=400)
    info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, gid, region)
    if not info: return web.json_response({"ok": False, "error": f"Guild {gid} not found in {region}"}, status=404)
    return web.json_response({"ok": True, "info": {
        "clan_name": info["guild_name"], "guild_id": info["guild_id"], "region": info["region"],
        "guild_level": info["guild_level"], "leader_id": info["leader_id"],
        "leader_name": info["leader_name"],
        "current_members": info["current_members"], "max_members": info["max_members"],
        "slogan": info["slogan"], "score": info["total_glory"],
        "weekly_activity": info["weekly_glory"], "rank": info["rank"],
        "members_online": info["members_online"],
        "auto_approval": info.get("auto_approval", True)}})

async def _launch_glory(u, guild_id, region, hours=None):
    """Shared launcher used by /glory and /functions/v1/start-glory"""
    if not u: return {"error": "Unauthorized", "_code": 401}
    if not u.get("is_admin") and u.get("credits", 0) < SETTINGS.get("credit_per_launch", 1):
        return {"error": "Not enough credits", "_code": 402}
    try: hours = float(hours) if hours not in (None, "") else None
    except Exception: hours = None
    if not u.get("is_admin"): hours = None                      # only admin may choose the running time
    elif hours is not None and not (0.02 <= hours <= 720): return {"error": "Run time must be between 0.02 and 720 hours", "_code": 400}
    if region not in VALID_REGIONS: region = DEFAULT_REGION
    if not guild_id.isdigit(): return {"error": "Invalid guild_id", "_code": 400}

    if SETTINGS.get("maintenance", {}).get("glory", {}).get(region):
        return {"error": f"{region} under maintenance", "_code": 503}

    running_for_guild = [gid for gid, g in GROUPS_DB.items()
                         if g.get("guild_id") == guild_id and g.get("status") in ("GENERATING","RUNNING")]
    if len(running_for_guild) >= SETTINGS.get("max_launches", 10):
        return {"error": f"Limit reached ({SETTINGS.get('max_launches',10)})", "_code": 409}

    info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, guild_id, region)
    if not info: return {"error": f"Guild {guild_id} not found", "_code": 404}

    group_id = f"GRP-{uuid.uuid4().hex[:6].upper()}"
    GROUPS_DB[group_id] = {
        "group_id": group_id, "guild_id": guild_id, "region": region,
        "guild_name": info["guild_name"], "guild_level": info["guild_level"],
        "leader_id": info["leader_id"], "leader_name": info["leader_name"],
        "slogan": info["slogan"], "bio": info.get("bio",""),
        "rank": info.get("rank",0), "activity_points": info.get("activity_points",0),
        "current_members": info["current_members"], "max_members": info["max_members"],
        "members_online": info.get("members_online",0),
        "initial_member_count": info["current_members"], "approved_count": 0,
        "initial_glory": info["total_glory"], "total_glory": info["total_glory"],
        "baseline_weekly": info.get("weekly_glory", 0),
        "glory_gained": 0, "elapsed_seconds": 0,
        "remaining_seconds": (hours or SETTINGS.get("goal_hours", 8)) * 3600,
        **({"goal_hours": hours} if hours else {}),
        "status": "GENERATING", "stage": "GENERATING", "stage_note": "queued",
        "stage_at": int(time.time()), "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "auth_uids": [], "accounts": [], "pending_accounts": [],
        "engine_pid": None, "engine_proc": None, "engine_log": group_log_path(group_id),
        "live_members": {}, "members_fetched_at": 0, "owner": u["username"]}
    save_json(DB_FILE, GROUPS_DB)

    # Deduct credits properly for non-admins
    if not u.get("is_admin"):
        cost = SETTINGS.get("credit_per_launch", 1)
        u["credits"] = u.get("credits", 0) - cost
        GROUPS_DB[group_id]["credit_charged"] = cost
        u.setdefault("groups", []).append(group_id)
        save_json(USERS_FILE, USERS_DB)
        push_log("info", f"Credit deducted. New balance: {u['credits']}", user=u["username"])

    asyncio.create_task(create_and_join(region, guild_id, SETTINGS.get("bot_count", 4), GROUPS_DB[group_id]))
    push_log("info", f"Launch requested guild={guild_id} region={region}",
             instance=group_id, user=u["username"])
    return {"ok": True, "group_id": group_id, "group_key": group_id, "region": region,
            "guild_id": guild_id, "guild_name": info["guild_name"], "bots": SETTINGS.get("bot_count",4)}

async def api_glory(request):
    u = user_from_request(request)
    res = await _launch_glory(u,
        str(request.query.get("guild_id","")).strip(),
        str(request.query.get("region", DEFAULT_REGION)).upper(), request.query.get("hours"))
    code = res.pop("_code", 200)
    return web.json_response(res, status=code)

async def fn_start_glory(request):
    u = user_from_request(request)
    try: data = await request.json()
    except Exception: data = {}
    res = await _launch_glory(u, str(data.get("guild_id","")).strip(),
                              str(data.get("region", DEFAULT_REGION)).upper(), data.get("hours"))
    code = res.pop("_code", 200)
    return web.json_response(res, status=code)

async def fn_guild_preview(request):
    try:
        data = await request.json()
        gid = str(data.get("guild_id","")).strip()
        region = str(data.get("region", DEFAULT_REGION)).upper()
        if not gid.isdigit(): return web.json_response({"error": "Invalid guild_id"}, status=400)
        info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, gid, region)
        if not info: return web.json_response({"error": f"Guild not found in {region}"}, status=404)
        return web.json_response({"info": {
            "guild_name": info["guild_name"], "guild_id": info["guild_id"],
            "region": info["region"], "guild_level": info["guild_level"],
            "leader_name": info["leader_name"], "leader_id": info["leader_id"],
            "current_members": info["current_members"],
            "max_members": info["max_members"],
            "weekly_activity": info["weekly_glory"],
            "total_activity": info["activity_points"],
            "auto_approval": info.get("auto_approval", True)}})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def _stop_group(u, gid):
    g = GROUPS_DB.get(gid)
    if not g: return {"error": "not found", "_code": 404}
    if not u or (not u.get("is_admin") and g.get("owner") != u["username"]):
        return {"error": "Forbidden", "_code": 403}
    g["status"]="STOPPED"; g["stage"]="STOPPED"; g["stage_note"]="stopped"
    proc = g.get("engine_proc")
    if proc: await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
    g["engine_pid"]=None; g["engine_proc"]=None
    for acc in g.get("accounts", []): acc["status"]="OFFLINE"
    save_json(DB_FILE, GROUPS_DB)
    push_log("info", "Stopped", instance=gid, user=(u or {}).get("username"))
    return {"ok": True, "group_id": gid, "status": "STOPPED"}

async def api_stop(request):
    u = user_from_request(request)
    gid = str(request.query.get("group_id","")).strip() or str(request.query.get("group_key","")).strip()
    res = await _stop_group(u, gid)
    code = res.pop("_code", 200)
    return web.json_response(res, status=code)

async def fn_stop_glory(request):
    u = user_from_request(request)
    try: data = await request.json()
    except Exception: data = {}
    gid = data.get("instance_id") or data.get("group_id") or ""
    res = await _stop_group(u, gid)
    code = res.pop("_code", 200)
    return web.json_response(res, status=code)

async def _restart_group(u, gid):
    g = GROUPS_DB.get(gid)
    if not g: return {"error": "not found", "_code": 404}
    if not u or (not u.get("is_admin") and g.get("owner") != u["username"]):
        return {"error": "Forbidden", "_code": 403}
    if g.get("status") == "RUNNING": return {"error": "already running", "_code": 409}
    proc = g.get("engine_proc")
    if proc:
        await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
        g["engine_proc"]=None; g["engine_pid"]=None
        await asyncio.sleep(2)
    saved = [{"uid":a["uid"],"password":a.get("password",DEFAULT_PASSWORD),
              "name":a.get("name",""),"account_id":a.get("account_id","")}
             for a in g.get("accounts", []) if a.get("uid")]
    if saved:
        if not write_group_accounts(gid, saved): return {"error": "write failed", "_code": 500}
        proc, err = start_engine_for_group(gid)
        if err: return {"error": err, "_code": 500}
        g["status"]="RUNNING"; g["stage"]="RUNNING"; g["stage_note"]="restarted"
        g["engine_pid"]=proc.pid; g["engine_proc"]=proc
        g["started_at"] = int(time.time() * 1000)
        save_json(DB_FILE, GROUPS_DB)
        asyncio.create_task(_glory_worker(gid))
        push_log("info", "Restarted (same bots)", instance=gid, user=(u or {}).get("username"))
        return {"ok": True, "group_id": gid, "restarted_with_same": len(saved)}
    g["status"]="GENERATING"; g["stage"]="GENERATING"
    g["auth_uids"]=[]; g["accounts"]=[]; save_json(DB_FILE, GROUPS_DB)
    asyncio.create_task(create_and_join(g["region"], g["guild_id"], SETTINGS.get("bot_count",4), g))
    push_log("info", "Restarted (fresh bots)", instance=gid, user=(u or {}).get("username"))
    return {"ok": True, "group_id": gid, "restarted_with_fresh": True}

async def api_restart(request):
    u = user_from_request(request)
    gid = str(request.query.get("group_id","")).strip() or str(request.query.get("group_key","")).strip()
    res = await _restart_group(u, gid)
    code = res.pop("_code", 200)
    return web.json_response(res, status=code)

async def fn_restart_glory(request):
    u = user_from_request(request)
    try: data = await request.json()
    except Exception: data = {}
    gid = data.get("instance_id") or data.get("group_id") or ""
    res = await _restart_group(u, gid)
    code = res.pop("_code", 200)
    return web.json_response(res, status=code)

async def api_refund(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    gid = str(request.query.get("group_id","")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return web.json_response({"error": "not found"}, status=404)
    if not u.get("is_admin") and g.get("owner") != u["username"]:
        return web.json_response({"error": "Forbidden"}, status=403)
    if g.get("status") == "REFUNDED" or g.get("credit_refunded"):
        return web.json_response({"error": "Already refunded"}, status=409)
    if not g.get("started_at"):
        return web.json_response({"error": "Instance has not started yet"}, status=400)
    elapsed = (time.time() * 1000 - g.get("started_at", 0)) / 1000.0
    if elapsed < SETTINGS.get("refund_time_mins", 30) * 60:
        return web.json_response({"error": "Too early"}, status=400)
    if g.get("glory_gained", 0) > SETTINGS.get("refund_min_glory", 0):
        return web.json_response({"error": "Glory gained"}, status=400)
    g["status"]="REFUNDED"; g["stage"]="REFUNDED"; g["stage_note"]="refunded"; g["credit_refunded"]=True
    proc = g.get("engine_proc")
    if proc: await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
    g["engine_pid"]=None; g["engine_proc"]=None
    u["credits"] = u.get("credits", 0) + SETTINGS.get("credit_per_launch", 1)
    save_json(USERS_FILE, USERS_DB); save_json(DB_FILE, GROUPS_DB)
    push_log("info", "Refunded", instance=gid, user=u["username"])
    return web.json_response({"ok": True, "group_id": gid, "refunded": True})

# ═══════════════ Settings ═══════════════
async def api_settings_get(request):
    return web.json_response(SETTINGS)

async def api_settings_save(request):
    try:
        data = await request.json()
        if not admin_from_request(request):
            return web.json_response({"error": "Forbidden"}, status=403)
        SETTINGS.update(data)
        save_json(SETTINGS_FILE, SETTINGS)
        push_log("info", "Settings updated")
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

# ═══════════════ Coupons ═══════════════
async def api_redeem(request):
    u = user_from_request(request)
    if not u: return web.json_response({"error": "Unauthorized"}, status=401)
    try:
        data = await request.json()
        code = str(data.get("code") or "").strip().upper()
        coupon = COUPONS_DB.get(code)
        if not coupon or coupon.get("used"):
            return web.json_response({"error": "Invalid or used coupon"}, status=400)
        credits = coupon.get("credits", 1)
        u["credits"] = u.get("credits", 0) + credits
        coupon["used"] = True; coupon["used_by"] = u["username"]
        coupon["used_at"] = time.time()
        save_json(USERS_FILE, USERS_DB); save_json(COUPONS_FILE, COUPONS_DB)
        push_log("info", f"Coupon {code} +{credits}", user=u["username"])
        return web.json_response({"ok": True, "credits": credits})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def fn_redeem_coupon(request):
    return await api_redeem(request)

# ═══════════════ Admin APIs ═══════════════
async def api_admin_overview(request):
    if not admin_from_request(request):
        return web.json_response({"error": "Forbidden"}, status=403)
    return web.json_response({
        "users": len(USERS_DB),
        "running": sum(1 for g in GROUPS_DB.values() if g.get("status") == "RUNNING"),
        "bots_online": sum(len(g.get("accounts", [])) for g in GROUPS_DB.values()
                           if g.get("status") == "RUNNING"),
        "total_glory": sum(g.get("glory_gained", 0) for g in GROUPS_DB.values()),
        "sandbox": False,
        "recent_logs": LOG_BUFFER[-30:]})

async def api_group_time(request):
    """Admin: change a group's running time. body: {group_id, minutes: +/-N} (adjust) or {group_id, hours: N} (set total)."""
    if not admin_from_request(request): return web.json_response({"error": "Forbidden"}, status=403)
    try:
        d = await request.json(); g = GROUPS_DB.get(str(d.get("group_id") or d.get("instance_id") or ""))
        if not g: return web.json_response({"error": "not found"}, status=404)
        if g.get("status") not in ("GENERATING", "RUNNING"):
            return web.json_response({"error": "Only running instances can be changed"}, status=400)
        cur = _goal_secs(g) / 3600
        if d.get("hours") not in (None, ""): new = float(d["hours"])
        else: new = cur + float(d.get("minutes", 0)) / 60
        new = round(min(720, max(0.02, new)), 4)
        g["goal_hours"] = new
        save_json(DB_FILE, GROUPS_DB)
        push_log("info", f"Run time set to {new:g}h (was {cur:g}h)", instance=g.get("group_id"))
        return web.json_response({"ok": True, "goal_hours": new})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_instances(request):
    if not admin_from_request(request):
        return web.json_response({"error": "Forbidden"}, status=403)
    if request.method == "GET":
        items = []
        for gid, g in GROUPS_DB.items():
            s = _group_summary(gid, g)
            items.append({"id": gid, "guild_id": s["guild_id"], "guild_name": s["guild_name"],
                          "region": s["region"], "status": s["status"],
                          "bot_count": s["bot_count"], "glory_gained": s["glory_gained"],
                          "total_activity": s["total_activity"], "owner": s["owner"],
                          "goal_hours": s["goal_hours"], "remaining": s["remaining"]})
        return web.json_response({"instances": items})
    try:
        data = await request.json()
        gid = data.get("instance_id"); action = data.get("action")
        g = GROUPS_DB.get(gid)
        if not g: return web.json_response({"error": "not found"}, status=404)
        u = admin_from_request(request)
        if action == "stop": await _stop_group(u, gid)
        elif action == "restart": await _restart_group(u, gid)
        elif action == "delete":
            proc = g.get("engine_proc")
            if proc: await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
            GROUPS_DB.pop(gid, None); save_json(DB_FILE, GROUPS_DB)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_bots(request):
    if not admin_from_request(request):
        return web.json_response({"error": "Forbidden"}, status=403)
    iid = str(request.query.get("instance_id","")).strip()
    g = GROUPS_DB.get(iid)
    if not g: return web.json_response({"error": "not found"}, status=404)
    s = _group_summary(iid, g)
    bots = [{"index": i, "uid": a.get("uid"), "status": a.get("status"),
             "glory": a.get("total_glory", 0)}
            for i, a in enumerate(s["accounts"])]
    return web.json_response({"instance": s, "bots": bots})

async def api_admin_users(request):
    if not admin_from_request(request):
        return web.json_response({"error": "Forbidden"}, status=403)
    if request.method == "GET":
        return web.json_response({"users": [{k:v for k,v in u.items() if k != "password"}
                                            for u in USERS_DB.values()]})
    try:
        data = await request.json()
        action = data.get("action", "create")
        username = data.get("username")
        if action == "create":
            pwd = data.get("password"); credits = int(data.get("credits", 0))
            if not username or not pwd: return web.json_response({"error": "Empty"}, status=400)
            if username in USERS_DB: return web.json_response({"error": "User exists"}, status=409)
            USERS_DB[username] = {"username": username, "password": pwd,
                                   "is_admin": False, "credits": credits, "groups": []}
        else:
            u = USERS_DB.get(username)
            if not u: return web.json_response({"error": "not found"}, status=404)
            if action == "add_credits":
                u["credits"] = max(0, u.get("credits", 0) + int(data.get("amount", 0)))
            elif action == "ban": u["banned"] = True
            elif action == "unban": u["banned"] = False
            elif action == "make_admin": u["is_admin"] = True
            elif action == "remove_admin": u["is_admin"] = False
            elif action == "delete": USERS_DB.pop(username, None)
        save_json(USERS_FILE, USERS_DB)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_coupons(request):
    if not admin_from_request(request):
        return web.json_response({"error": "Forbidden"}, status=403)
    if request.method == "GET":
        return web.json_response({"coupons": list(COUPONS_DB.values())})
    try:
        data = await request.json()
        action = data.get("action", "generate")
        if action == "generate":
            credits = int(data.get("credits", 1))
            count = max(1, int(data.get("count", data.get("quantity", 1))))  # no upper limit for admin
            codes = []
            for _ in range(count):
                while True:
                    code = f"{COUPON_PREFIX}-{uuid.uuid4().hex[:3].upper()}-{uuid.uuid4().hex[:3].upper()}-{uuid.uuid4().hex[:3].upper()}"
                    if code not in COUPONS_DB: break
                COUPONS_DB[code] = {"code": code, "credits": credits,
                                     "used": False, "created_at": time.time()}
                codes.append(code)
            save_json(COUPONS_FILE, COUPONS_DB)
            return web.json_response({"ok": True, "codes": codes})
        if action == "delete":
            COUPONS_DB.pop(data.get("code"), None)
            save_json(COUPONS_FILE, COUPONS_DB)
            return web.json_response({"ok": True})
        return web.json_response({"error": "unknown action"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_manual(request):
    if not admin_from_request(request):
        return web.json_response({"error": "Forbidden"}, status=403)
    if request.method == "GET":
        return web.json_response({"accounts": MANUAL_ACCOUNTS})
    try:
        data = await request.json()
        region = str(data.get("region","")).upper()
        accs = data.get("accounts", [])
        if region not in VALID_REGIONS: return web.json_response({"error": "Invalid region"}, status=400)
        MANUAL_ACCOUNTS[region] = accs
        save_json(MANUAL_ACCS_FILE, MANUAL_ACCOUNTS)
        return web.json_response({"ok": True, "count": len(accs)})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def ws_logs(request):
    if not admin_from_request(request):
        return web.Response(status=403)
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    LOG_SUBSCRIBERS.add(ws)
    try:
        for entry in LOG_BUFFER[-100:]:
            await ws.send_json(entry)
        async for msg in ws:
            if msg.type == WSMsgType.TEXT and msg.data == "ping":
                await ws.send_json({"ts": time.time(), "level": "debug", "msg": "pong"})
    finally:
        LOG_SUBSCRIBERS.discard(ws)
    return ws

def _recover_groups():
    """After a restart no engine/worker exists any more: clean stale state and resume RUNNING groups."""
    changed = False
    for gid, g in list(GROUPS_DB.items()):
        if not isinstance(g, dict): GROUPS_DB.pop(gid, None); changed = True; continue
        if g.get("engine_proc") or g.get("engine_pid"):
            g["engine_proc"] = None; g["engine_pid"] = None; changed = True
        st = g.get("status")
        if st == "GENERATING":
            g["error"] = "Server restarted while generating"; g["status"] = "FAILED"; g["stage"] = "FAILED"
            _refund_launch(g); changed = True
        elif st == "RUNNING":
            saved = [{"uid": a["uid"], "password": a.get("password", DEFAULT_PASSWORD),
                      "name": a.get("name", ""), "account_id": a.get("account_id", "")}
                     for a in g.get("accounts", []) if a.get("uid")]
            if saved and write_group_accounts(gid, saved):
                proc, err = start_engine_for_group(gid)
                if not err:
                    g["engine_proc"] = proc; g["engine_pid"] = proc.pid
                    asyncio.create_task(_glory_worker(gid))
                    push_log("info", "Resumed after server restart", instance=gid); changed = True
                    continue
            g["status"] = "STOPPED"; g["stage"] = "STOPPED"; g["stage_note"] = "stopped (restart)"; changed = True
    if changed: save_json(DB_FILE, GROUPS_DB)

# ═══════════════ App ═══════════════
async def main():
    print(f"""
FF GLORY ENGINE — UNIFIED
Port: {WEB_PORT}  |  Admin: http://{WEB_HOST}:{WEB_PORT}{ADMIN_SECRET_PATH}
""", flush=True)

    app = web.Application()
    async def _health(request): return web.json_response({"ok": True})
    app.router.add_get("/health", _health)
    app.router.add_get("/", page_index)
    app.router.add_get(ADMIN_SECRET_PATH, page_admin)
    app.router.add_get("/admin", page_admin)
    app.router.add_get("/api/pay/info", api_pay_info)
    app.router.add_post("/api/pay/order", api_pay_order)
    app.router.add_get("/api/pay/order/status", api_pay_order_status)
    app.router.add_post("/api/pay/webhook", api_pay_webhook)
    app.router.add_post("/api/pay/pending", api_pay_pending)
    app.router.add_post("/api/admin/pay/gwtest", api_admin_pay_gwtest)
    app.router.add_post("/api/pay/verify", api_pay_verify)
    app.router.add_get("/api/pay/history", api_pay_history)
    app.router.add_get("/api/admin/pay", api_admin_pay)
    app.router.add_post("/api/admin/pay/config", api_admin_pay_config)
    app.router.add_post("/api/admin/pay/test", api_admin_pay_test)
    app.router.add_post("/api/admin/pay/lookup", api_admin_pay_lookup)
    app.router.add_post("/api/admin/pay/approve", api_admin_pay_approve)
    app.router.add_get("/qr.png", page_qr)

    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/signup", api_signup)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/redeem", api_redeem)

    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/groups", api_groups)
    app.router.add_get("/api/groups/log", api_group_log)
    app.router.add_get("/api/guild_info", api_guild_info)
    app.router.add_get("/glory", api_glory)
    app.router.add_get("/stop", api_stop)
    app.router.add_get("/restart", api_restart)
    app.router.add_get("/refund", api_refund)
    app.router.add_get("/api/settings/get", api_settings_get)
    app.router.add_post("/api/settings/save", api_settings_save)

    app.router.add_post("/functions/v1/start-glory", fn_start_glory)
    app.router.add_post("/functions/v1/stop-glory", fn_stop_glory)
    app.router.add_post("/functions/v1/restart-glory", fn_restart_glory)
    app.router.add_post("/functions/v1/guild-preview", fn_guild_preview)
    app.router.add_post("/functions/v1/redeem-coupon", fn_redeem_coupon)

    app.router.add_get("/api/admin/overview", api_admin_overview)
    app.router.add_get("/api/admin/instances", api_admin_instances)
    app.router.add_post("/api/admin/instances", api_admin_instances)
    app.router.add_post("/api/group/time", api_group_time)
    app.router.add_get("/api/admin/bots", api_admin_bots)
    app.router.add_get("/api/admin/users", api_admin_users)
    app.router.add_post("/api/admin/users", api_admin_users)
    app.router.add_get("/api/admin/coupons", api_admin_coupons)
    app.router.add_post("/api/admin/coupons", api_admin_coupons)
    app.router.add_get("/api/admin/manual", api_admin_manual)
    app.router.add_post("/api/admin/manual", api_admin_manual)
    app.router.add_get("/api/logs/ws", ws_logs)
    
    app.router.add_get("/api/overview", api_admin_overview)
    app.router.add_get("/api/instances", api_admin_instances)
    app.router.add_post("/api/instances", api_admin_instances)
    app.router.add_get("/api/bots", api_admin_bots)
    app.router.add_get("/api/users", api_admin_users)
    app.router.add_post("/api/users", api_admin_users)
    app.router.add_get("/api/coupons", api_admin_coupons)
    app.router.add_post("/api/coupons", api_admin_coupons)
    app.router.add_get("/api/manual", api_admin_manual)
    app.router.add_post("/api/manual", api_admin_manual)
    app.router.add_get("/api/logs/ws/", ws_logs)
    app.router.add_get("/api/settings", api_settings_get)

    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    _recover_groups()
    asyncio.create_task(_auto_restart_loop())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()
    print(f"✅ Ready → http://{WEB_HOST}:{WEB_PORT}\n", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠ Stopped")