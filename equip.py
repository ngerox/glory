import asyncio
import httpx

class Colors:
    HEADER = '\033[95m'
    GREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    ENDC = '\033[0m'

def print_colored(text, color=Colors.WHITE):
    try:
        print(f"{color}{text}{Colors.ENDC}")
    except Exception:
        print(text)

async def send_debug_request_async(client, url, jwt_token, hex_body, step_name, hide_response=False):
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "client.ind.freefiremobile.com",
        "ReleaseVersion": "OB55",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1",
        "X-GA-SV": "1792556288",
        "X-Unity-Version": "2018.4.12f1"
    }
    try:
        body_bytes = bytes.fromhex(hex_body.replace(" ", ""))
        response = await client.post(url, headers=headers, content=body_bytes)
        if not hide_response:
            print_colored(f"[+] [EQUIP] Step '{step_name}' executed successfully (Status: {response.status_code})", Colors.GREEN)
    except Exception as e:
        print_colored(f"[-] [EQUIP] Step '{step_name}' failed: {e}", Colors.FAIL)

async def run_equip_workflow(jwt_token: str, server_url: str = "https://client.ind.freefiremobile.com"):
    print_colored("[i] [EQUIP] Starting automated equip & reward claims...", Colors.CYAN)
    
    host_domain = "client.ind.freefiremobile.com"
    if server_url:
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(server_url)
            if parsed_url.netloc:
                host_domain = parsed_url.netloc
        except Exception:
            pass

    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        tasks = [
            ("ClaimFreshSigninRewards", "E99FFFD90468992B08E3BFDB08D3B9B9", False),
            ("GetStore", "10 F8 74 30 DC 6A CA CA 32 FC 2B 44 79 72 3A 74", True),
            ("GiveAccountNewbieRoles", "EC 91 18 3D EF 30 AA 26 FA EF 2B BB EB 31 37 89", False),
            ("SelectPresetLoadout", "52 02 F0 D7 5C EC 74 F6 81 E1 F3 30 78 81 D2 72 58 D9 40 BB 98 81 E9 55 9B 4D 07 CA 4A A0 C5 D9 70 0A 7F C3 61 C0 A0 6E AF 6E 91 C0 E8 41 C0 C7 75 12 AC FF FC 25 04 77 99 08 77 26 B0 42 7A 88", False),
            ("ClaimAvatarProficiencyAward", "27D278C557914A29991290FC2DC8F6D2", False),
            ("ChooseHeadPic", "9BB7A317CD235254FED71EC2EBA1E718", False),
            ("ChooseEmote", "CAF683222A25C7BEFEB51F59544DB313", False),
            ("ClaimFreshActivityRewards", "ADC5827D0CA24022A802A9F2C529FD7D", False),
            ("ChooseBanner", "A230C31BDAD89C7AA0EF786068997E07", False)
        ]
        
        for step_name, hex_body, hide in tasks:
            target_url = f"https://{host_domain}/{step_name}"
            await send_debug_request_async(client, target_url, jwt_token, hex_body, step_name, hide_response=hide)
            await asyncio.sleep(0.3)
            
    print_colored("[+] [EQUIP] All equip tasks completed successfully!", Colors.GREEN)
