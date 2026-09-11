import requests
import random
from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')

TITLE_ID = "C1667"
SECRET_KEY = "UFYTWKIM7W9IH3HX8DYXC8O63MSG7A947IIR6FMYMIE6DBK85M"
OCULUS_KEY = "OC|1248500195009702|5674541478a2e9fd799b0e75a336472a" 
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1536078226575593522/755e1e00Heeo0U9p5NlPwdgTU9TZKNB9qjlgHH9JWcK1AZf9lf_rRBXQBUVW8hrP3L1w"

def get_ip():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()

def verify_oculus_id(oid):
    try:
        r = requests.get(f"https://graph.oculus.com/{oid}?access_token={OCULUS_KEY}&fields=org_scoped_id", timeout=10)
        if r.status_code == 200:
            return r.json().get("org_scoped_id")
    except:
        pass
    return None

def send_discord(success, ip, custom_id=None, pfid=None, oid=None, err=None):
    try:
        if success:
            payload = {
                "embeds": [{
                    "color": 65280,
                    "fields": [{
                        "name": "SOMEONE LOGGED IN!",
                        "value": f"```\nIP: {ip}\nCustomID: {custom_id or 'N/A'}\nPlayFabID: {pfid or 'N/A'}\nOculusID: {oid or 'N/A'}```"
                    }]
                }]
            }
        else:
            payload = {
                "embeds": [{
                    "color": 16711680,
                    "fields": [{
                        "name": "SOMEONES GETTING RAPED!",
                        "value": f"```\nIP: {ip}\nCustomID: {custom_id or 'N/A'}\nOculusID: {oid or 'N/A'}\nError: {err or 'idk'}```"
                    }]
                }]
            }
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
    except:
        print("discord webhook failed lol")

@app.route("/", methods=["POST", "GET"])
def home():
    return """
        <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
                <style>
                    * { margin: 0; padding: 0; }
                    body { 
                        font-family: 'Inter', sans-serif;
                        background-image: url('/static/profile.jpg');
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                        background-attachment: fixed;
                        width: 100vw;
                        height: 100vh;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                        align-items: center;
                    }
                    .footer {
                        color: white;
                        font-size: 48px;
                        font-weight: 700;
                        margin-bottom: 30px;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
                    }
                </style>
            </head>
            <body>
                <div style="flex: 1;"></div>
                <div class="footer">25 MAXX</div>
            </body>
        </html>
    """

@app.route("/api/PlayFabAuthentication", methods=["POST"])
def auth():
    data = request.get_json()
    ip = get_ip()
    
    if not data:
        return jsonify({"Message": "no data sent", "Error": "BadRequest"}), 400
    
    if not data.get("Nonce") or not data.get("AppId") or not data.get("OculusId"):
        missing = []
        if not data.get("Nonce"): missing.append("Nonce")
        if not data.get("AppId"): missing.append("AppId")
        if not data.get("OculusId"): missing.append("OculusId")
        send_discord(False, ip, err=f"missing: {', '.join(missing)}")
        return jsonify({"Message": f"Missing: {', '.join(missing)}", "Error": "BadRequest"}), 400
    
    if data.get("AppId") != TITLE_ID:
        send_discord(False, ip, oid=data.get("OculusId"), err="wrong app id")
        return jsonify({"Message": "wrong app id lol", "Error": "BadRequest-AppIdMismatch"}), 400
    
    oid = data.get("OculusId")
    org_id = verify_oculus_id(oid)
    if not org_id:
        send_discord(False, ip, oid=oid, err="invalid oculus id")
        return jsonify({"Message": "invalid oculus id", "Error": "BadRequest-InvalidOculusId"}), 400
    
    hdrs = {"content-type": "application/json", "X-SecretKey": SECRET_KEY}
    
    login_res = requests.post(
        f"https://{TITLE_ID}.playfabapi.com/Server/LoginWithServerCustomId",
        json={"ServerCustomId": "OCULUS" + oid, "CreateAccount": True},
        headers=hdrs
    )
    
    if login_res.status_code != 200:
        err_data = login_res.json()
        err_msg = err_data.get("errorMessage", "playfab error")
        
        if login_res.status_code == 403 and err_data.get("errorCode") == 1002:
            details = err_data.get("errorDetails", {})
            ban_key = next(iter(details.keys()), "N/A")
            ban_val = details.get(ban_key, ["N/A"])[0] if details else "N/A"
            send_discord(False, ip, data.get("CustomId"), err=f"BANNED: {err_msg}", oid=oid)
            return jsonify({"BanMessage": ban_key, "BanExpirationTime": ban_val}), 403
        
        send_discord(False, ip, data.get("CustomId"), err=err_msg, oid=oid)
        return jsonify({"Error": "PlayFab Error", "Message": err_msg}), login_res.status_code
    
    pf_data = login_res.json()["data"]
    pf_id = pf_data["PlayFabId"]
    ticket = pf_data["SessionTicket"]
    ent_token = pf_data["EntityToken"]["EntityToken"]
    ent_id = pf_data["EntityToken"]["Entity"]["Id"]
    ent_type = pf_data["EntityToken"]["Entity"]["Type"]
    
    requests.post(
        f"https://{TITLE_ID}.playfabapi.com/Server/LinkServerCustomId",
        json={"ForceLink": True, "PlayFabId": pf_id, "ServerCustomId": data.get("CustomId", "")},
        headers=hdrs
    )
    
    send_discord(True, ip, data.get("CustomId"), pf_id, oid)
    
    return jsonify({
        "PlayFabId": pf_id,
        "SessionTicket": ticket,
        "EntityToken": ent_token,
        "EntityId": ent_id,
        "EntityType": ent_type
    }), 200

@app.route("/api/TitleData", methods=["GET", "POST"])
def titledata():
    return jsonify({
        "AutoMuteCheckedHours": {"hours": 169},
        "AutoName_Adverbs": ["Cool", "Fine", "Bald", "Bold", "Half", "Only", "Calm", "Fab", "Ice", "Mad", "Rad", "Big", "New", "Old", "Shy"],
        "AutoName_Nouns": ["Gorilla", "Chicken", "Darling", "Sloth", "King", "Queen", "Royal", "Major", "Actor", "Agent", "Elder", "Honey", "Nurse", "Doctor", "Rebel", "Shape", "Ally", "Driver", "Deputy"],
        "CreditsData": [
            {"Title": "<color=blue>DEVS</color>", "Entries": ["ME", "YOU", "THEM"]},
            {"Title": "<color=yellow>CREDITS</color>", "Entries": ["SOME PEOPLE", "IDK"]}
        ],
        "BundleBoardSign": "<color=red>DISCORD.GG/TGj2tFxs4w</color>",
        "BundleKioskButton": "<color=red>DISCORD.GG/TGj2tFxs4w</color>",
        "BundleKioskSign": "<color=red>DISCORD.GG/TGj2tFxs4w</color>",
        "BundleLargeSign": "<color=red>DISCORD.GG/TGj2tFxs4w</color>",
        "EnableCustomAuthentication": True,
        "GorillanalyticsChance": 4320,
        "LatestPrivacyPolicyVersion": "2025.01.01",
        "LatestTOSVersion": "2025.01.01",
        "MOTD": "<color=green>WELCOME TO MY SERVER!</color>\n<color=yellow>JOIN THE DISCORD!</color>",
        "SeasonalStoreBoardSign": "<color=white>HAVE FUN</color>",
        "UseLegacyIAP": False
    })

@app.route("/api/photon", methods=["POST", "GET"])
def photon():
    if request.method == "GET":
        data = request.get_json()
    else:
        data = request.get_json()
    
    if not data:
        return jsonify({"resultCode": 0, "message": "no data"})
    
    ticket = data.get("Ticket", "")
    nonce = data.get("Nonce")
    platform = data.get("Platform")
    user_id = data.get("UserId")
    
    pfid = ticket.split("-")[0] if "-" in ticket else ticket
    
    if not pfid or len(pfid) != 16:
        return jsonify({"resultCode": 2, "message": "bad ticket", "userId": None, "nickname": None})
    
    if platform and platform != "Quest":
        return jsonify({"resultCode": 2, "message": "wrong platform"}), 403
    
    hdrs = {"content-type": "application/json", "X-SecretKey": SECRET_KEY}
    
    r = requests.post(
        f"https://{TITLE_ID}.playfabapi.com/Server/GetUserAccountInfo",
        json={"PlayFabId": pfid},
        headers=hdrs
    )
    
    if r.status_code == 200:
        nick = r.json().get("UserInfo", {}).get("UserAccountInfo", {}).get("Username", None)
        return jsonify({
            "resultCode": 1,
            "message": f"authed {pfid}",
            "userId": pfid.upper(),
            "nickname": nick
        })
    
    return jsonify({"resultCode": 0, "message": "something went wrong", "userId": None, "nickname": None})

@app.route("/api/ConsumeOculusIAP", methods=["POST"])
def consume_iap():
    data = request.get_json()
    if not data:
        return jsonify({"error": True})
    
    r = requests.post(
        f"https://graph.oculus.com/consume_entitlement?nonce={data.get('nonce')}&user_id={data.get('userID')}&sku={data.get('sku')}&access_token={OCULUS_KEY}",
        headers={"content-type": "application/json"}
    )
    
    if r.json().get("success"):
        return jsonify({"result": True})
    return jsonify({"error": True})

@app.route("/api/ConsumeCodeItem", methods=["POST"])
def redeem_code():
    data = request.get_json()
    code = data.get("itemGUID")
    pfid = data.get("playFabID")
    ticket = data.get("playFabSessionTicket")
    
    if not all([code, pfid, ticket]):
        return jsonify({"error": "missing params"}), 400
    
    GITHUB_RAW = "https://raw.githubusercontent.com/YOURUSER/YOURREPO/main/codes.txt"
    
    try:
        r = requests.get(GITHUB_RAW, timeout=10)
    except:
        return jsonify({"error": "couldnt fetch codes"}), 500
    
    if r.status_code != 200:
        return jsonify({"error": "github failed"}), 500
    
    lines = r.text.strip().split("\n")
    codes_map = {}
    for line in lines:
        if ":" in line:
            parts = line.split(":", 1)
            codes_map[parts[0].strip()] = parts[1].strip()
    
    if code not in codes_map:
        return jsonify({"result": "CodeInvalid"}), 404
    
    if codes_map[code] == "AlreadyRedeemed":
        return jsonify({"result": "AlreadyRedeemed"}), 200
    
    ITEMS_TO_GRANT = ["cosmetic_id_1", "cosmetic_id_2"]
    
    hdrs = {"content-type": "application/json", "X-SecretKey": SECRET_KEY}
    
    grant = requests.post(
        f"https://{TITLE_ID}.playfabapi.com/Admin/GrantItemsToUsers",
        json={
            "ItemGrants": [
                {"PlayFabId": pfid, "ItemId": item, "CatalogVersion": "DLC"}
                for item in ITEMS_TO_GRANT
            ]
        },
        headers=hdrs
    )
    
    if grant.status_code != 200:
        return jsonify({"result": "PlayFabError", "error": grant.json().get("errorMessage", "idk")}), 500
    
    return jsonify({"result": "Success", "code": code}), 200

@app.route("/api/GetAcceptedAgreements", methods=["GET", "POST"])
def get_agreements():
    return jsonify({"PrivacyPolicy": "1.0.0", "TOS": "1.0.0"}), 200

@app.route("/api/SubmitAcceptedAgreements", methods=["GET", "POST"])
def submit_agreements():
    return jsonify({}), 200

@app.route("/api/v2/GetName", methods=["GET", "POST"])
def get_name():
    return jsonify({"result": f"GORILLA{random.randint(1000, 9999)}"})

@app.route("/api/CachePlayFabId", methods=["POST"])
def cache():
    return jsonify({"Message": "Success"}), 200

if __name__ == "__main__":
    print("starting backend on port 9080...")
    app.run(host="0.0.0.0", port=9080)
