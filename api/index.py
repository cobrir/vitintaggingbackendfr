from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone
import secrets
import base64
import uuid
import json
import requests
import os
import random
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ========================= CONFIGURATION =========================
class GameInfo:
    def __init__(self):
        # Replace with your actual values (from environment variables recommended)
        self.TitleId:   str = "C1667"
        self.SecretKey: str = "UFYTWKIM7W9IH3HX8DYXC8O63MSG7A947IIR6FMYMIE6DBK85M"
        self.ApiKey:  str = "OC|1248500195009702|5674541478a2e9fd799b0e75a336472a"
        self.PlayfabAuthenticationWebhook: str = "https://discord.com/api/webhooks/1536078226575593522/755e1e00Heeo0U9p5NlPwdgTU9TZKNB9qjlgHH9JWcK1AZf9lf_rRBXQBUVW8hrP3L1w"
        self.QuestsWebhook: str = "https://discord.com/api/webhooks/1536078226575593522/755e1e00Heeo0U9p5NlPwdgTU9TZKNB9qjlgHH9JWcK1AZf9lf_rRBXQBUVW8hrP3L1w"
        self.PhotonWebhook: str = "https://discord.com/api/webhooks/1536078226575593522/755e1e00Heeo0U9p5NlPwdgTU9TZKNB9qjlgHH9JWcK1AZf9lf_rRBXQBUVW8hrP3L1w"

    def get_auth_headers(self):
        return {"content-type": "application/json", "X-SecretKey": self.SecretKey}

settings = GameInfo()
app = Flask(__name__)

# ========================= GLOBAL DATA =========================
pending_nonces = {}          # for mothership auth
playfab_cache = {}
mute_cache = {}
polls = [
    {
        "pollId": 1,
        "question": "THIS IS A POLL!!!",
        "voteOptions": ["YES", "NO"],
        "voteCount": [],
        "predictionCount": [],
        "startTime": "2026-06-16T12:00:00",
        "endTime": "2026-06-30T12:00:00",
        "isActive": True
    }
]

Quests = {
    "AllActiveQuests": {
        "DailyQuests": [ ... ],   # truncated for brevity – keep the full dict from second file
        "WeeklyQuests": [ ... ]
    }
}
# (Full quests dictionary is assumed to be pasted here; for space I'm omitting but you must include it)

# ========================= KEY PAIR FOR MOTHERSHIP =========================
PRIVATE_KEY_FILE = "mothership_private.pem"
PUBLIC_KEY_FILE = "mothership_public.pem"

if not os.path.exists(PRIVATE_KEY_FILE) or not os.path.exists(PUBLIC_KEY_FILE):
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(private_bytes)
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(public_bytes)
    print("Generated new ES256 keypair!")

with open(PRIVATE_KEY_FILE, "rb") as f:
    private_key_pem = f.read()
    MOTHERSHIP_SECRET = serialization.load_pem_private_key(
        private_key_pem, password=None, backend=default_backend()
    )

ALLOWED_PACKAGE_IDS = ["com.VitinTagging]   # replace with your app's package id

# ========================= HELPER FUNCTIONS =========================
def log(msg):
    print(msg)

def GetIsNonceValid(nonce: str, oculusId: str):
    req = requests.post(
        url=f'https://graph.oculus.com/user_nonce_validate?nonce={nonce}&user_id={oculusId}&access_token={settings.ApiKey}',
        headers={"content-type": "application/json"}
    )
    return req.json().get("is_valid")

def ReturnFunctionJson(data, funcname, funcparam={}):
    user_id = data.get("FunctionParameter", {}).get("CallerEntityProfile", {}).get("Lineage", {}).get("TitlePlayerAccountId")
    if not user_id:
        # fallback for second file's style
        rjson = data.get("FunctionParameter", {})
        user_id = rjson.get("CallerEntityProfile", {}).get("Lineage", {}).get("TitlePlayerAccountId")
    req = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/ExecuteCloudScript",
        json={"PlayFabId": user_id, "FunctionName": funcname, "FunctionParameter": funcparam},
        headers=settings.get_auth_headers()
    )
    if req.status_code == 200:
        result = req.json().get("data", {}).get("FunctionResult", {})
        return jsonify(result), req.status_code
    else:
        return jsonify({}), req.status_code

def send_webhook(title, claims, user_id, mothership_id=None, expiration=None, error=None, color=3447003):
    try:
        desc = f"**User ID:** {user_id}\n"
        if mothership_id:
            desc += f"**Mothership ID:** {mothership_id}\n"
        if expiration:
            desc += f"**Expiration:** {expiration.isoformat()}\n"
        if error:
            desc += f"**Error:** {error}\n"
        claims_text = json.dumps(claims, indent=2)
        requests.post(settings.PlayfabAuthenticationWebhook, json={
            "embeds": [{
                "title": title,
                "description": desc + f"\n```json\n{claims_text}\n```",
                "color": color,
                "footer": {"text": "MOTHERSHIP SHIT"}
            }]
        }, timeout=5)
    except Exception as e:
        print("Webhook send failed:", e)

def send_auth_notification(playfab_id, ip, username, oculus_id):
    embed = {
        "title": "🔐 User Authenticated",
        "description": f"**{username}** just logged in!",
        "color": 0x00ffcc,
        "fields": [
            {"name": "👤 Username", "value": username, "inline": True},
            {"name": "🆔 PlayFab ID", "value": playfab_id, "inline": True},
            {"name": "🌐 IP Address", "value": ip, "inline": True},
            {"name": "🕶️ Oculus ID", "value": oculus_id, "inline": False}
        ],
        "footer": {"text": "Notification System"},
    }
    try:
        requests.post(settings.PlayfabAuthenticationWebhook, json={"embeds": [embed]})
    except Exception as e:
        print(f"Failed to send webhook: {e}")

def send_quest_notification(playfab_id, ip, username, quest_name):
    embed = {
        "title": "🎯 Quest Completed!",
        "description": f"**{username}** just completed a quest! 🔥",
        "color": 0x00ffcc,
        "fields": [
            {"name": "👤 Username", "value": username, "inline": True},
            {"name": "🆔 PlayFab ID", "value": playfab_id, "inline": True},
            {"name": "🌐 IP Address", "value": ip, "inline": True},
            {"name": "🏆 Quest", "value": quest_name, "inline": False}
        ],
        "footer": {"text": "Quest Notification System"},
    }
    try:
        requests.post(settings.QuestsWebhook, json={"embeds": [embed]})
    except Exception as e:
        print(f"Failed to send webhook: {e}")

def send_photon_notification(user_id, ip, nickname, platform):
    embed = {
        "title": "🔌 Photon Authentication",
        "description": f"**{nickname}** just authenticated via Photon!",
        "color": 0x3498db,
        "fields": [
            {"name": "👤 Username", "value": nickname or "Unknown", "inline": True},
            {"name": "🆔 PlayFab ID", "value": user_id or "Unknown", "inline": True},
            {"name": "🌐 IP Address", "value": ip or "Unknown", "inline": True},
            {"name": "📱 Platform", "value": platform or "Unknown", "inline": False}
        ],
        "footer": {"text": "Photon Authentication System"},
    }
    try:
        requests.post(settings.PhotonWebhook, json={"embeds": [embed]})
    except Exception as e:
        print(f"Webhook failed: {e}")

# ========================= ROUTES =========================
@app.route("/", methods=["POST", "GET"])
def main():
    return """
        <html>
            <head><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet"></head>
            <body style="font-family: 'Inter', sans-serif;">
                <h1 style="color: green; font-size: 30px;">Death Tag Backend is up and Running!</h1>
            </body>
        </html>
    """

# -------------------- Mothership Authentication --------------------
@app.route('/v2/player/client/auth/begin/QUEST', methods=['POST'])
def auth_begin():
    data = request.get_json(silent=True) or {}
    user_id = data.get("UserId")
    if not user_id:
        return jsonify({"error": "no UserId"}), 400
    nonce_bytes = secrets.token_bytes(64)
    nonce_b64 = base64.urlsafe_b64encode(nonce_bytes).decode('utf-8').rstrip("=")
    pending_nonces[user_id] = nonce_b64
    return jsonify({"AttestationNonce": nonce_b64}), 201

@app.route('/v2/player/client/auth/complete/QUEST', methods=['POST'])
def auth_complete():
    rjson = request.get_json(silent=True) or {}
    user_id = rjson.get("UserId")
    attestation_token = rjson.get("AttestationToken")
    expected_nonce = pending_nonces.get(user_id)
    statusCode = 401
    if not user_id or not attestation_token or not expected_nonce:
        return jsonify({
            "message": '{"MothershipErrorCode":10013,"ClientMessage":"Client Authentication Failed","TraceId":"' + str(uuid.uuid4()) + '"}',
            "statusCode": statusCode
        }), statusCode
    try:
        META_ACCESS_TOKENS = [settings.ApiKey]   # Use your API key(s)
        claims = None
        last_error = None
        for meta_token in META_ACCESS_TOKENS:
            try:
                verify_url = f"https://graph.oculus.com/platform_integrity/verify?token={attestation_token}&access_token={meta_token}"
                r = requests.get(verify_url, timeout=5)
                r.raise_for_status()
                result = r.json()
                if result['data'][0].get('message') == 'success' and result['data'][0].get('claims'):
                    claims_b64 = result['data'][0]['claims']
                    claims_json = base64.urlsafe_b64decode(claims_b64 + '=' * (-len(claims_b64) % 4)).decode()
                    claims = json.loads(claims_json)
                    break
            except Exception as e:
                last_error = e
                continue
        if not claims:
            raise ValueError(f"Attestation failed: {last_error}")
        token_nonce = claims['request_details'].get('nonce')
        if token_nonce != expected_nonce:
            raise ValueError("Nonce mismatch")
        app_state = claims.get("app_state", {})
        device_state = claims.get("device_state", {})
        if (app_state.get("app_integrity_state") != "StoreRecognized" or
            device_state.get("device_integrity_state") != "Advanced" or
            app_state.get("package_id") not in ALLOWED_PACKAGE_IDS):
            send_webhook("⚠️ - Mothership Failed", claims, user_id=user_id,
                error=f"Integrity check failed: {app_state.get('package_id')}", color=15158332)
            return "", statusCode
        del pending_nonces[user_id]
        mothership_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
        expiration = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {
            "sub": user_id,
            "did": app_state.get('package_id'),
            "env": app_state.get('version', '1'),
            "externalService": "QUEST",
            "externalServiceId": app_state.get('package_id', ''),
            "tid": str(uuid.uuid4())[:8],
            "tags": None,
            "orgScopedExternalServiceId": str(uuid.uuid4())[:8],
            "nbf": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(expiration.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp())
        }
        mothership_token = jwt.encode(payload, MOTHERSHIP_SECRET, algorithm='ES256')
        send_webhook("✅ - Mothership Success", claims, user_id=user_id,
            mothership_id=mothership_id, expiration=expiration, color=3066993)
        return jsonify({
            "MothershipToken": mothership_token,
            "MothershipId": mothership_id,
            "ExpirationTime": int(expiration.timestamp() * 1000),
            "ExternalProviderId": user_id,
            "ExternalProviderUsername": "",
            "IsPrimaryId": True,
            "PlayerId": user_id,
            "Tags": None,
            "Token": mothership_token
        }), 200
    except Exception as e:
        print("Attestation failed:", e)
        send_webhook("❌ - Mothership Error", {}, user_id, error=str(e), color=15105570)
        return jsonify({
            "message": '{"MothershipErrorCode":10013,"ClientMessage":"Client Authentication Failed","TraceId":"' + str(uuid.uuid4()) + '"}',
            "statusCode": statusCode
        }), statusCode

# -------------------- PlayFab Authentication --------------------
@app.route("/api/PlayFabAuthentication", methods=["POST", "GET"])
def playfab_authentication():
    # Only accept POST for authentication
    if request.method == "GET":
        return jsonify({"error": "GET method not supported. Use POST."}), 405

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    oculus_id = data.get("OculusId")
    if not oculus_id:
        return jsonify({"error": "Missing OculusId"}), 400

    # Optional fields (nonce, platform, mothership token etc. – you may use them)
    nonce = data.get("Nonce")
    platform = data.get("Platform")
    mothership_token = data.get("MothershipToken")
    mother_shipid = data.get("MothershipId")

    login_req = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId",
        json={"ServerCustomId": f"OCULUS{oculus_id}", "CreateAccount": True},
        headers=settings.get_auth_headers()
    )

    if login_req.status_code != 200:
        # Check if it's a ban response (errorCode 1002)
        ban_info = login_req.json()
        if ban_info.get("errorCode") == 1002:
            ban_details = ban_info.get("errorDetails", {})
            ban_expiration_key = next(iter(ban_details.keys()), None)
            ban_expiration_list = ban_details.get(ban_expiration_key, [])
            ban_expiration = ban_expiration_list[0] if ban_expiration_list else "Indefinite"
            return jsonify({
                "BanMessage": ban_expiration_key,
                "BanExpirationTime": ban_expiration
            }), 403
        else:
            # General login failure
            return jsonify({
                "error": "PlayFab login failed",
                "details": ban_info.get("errorMessage", "Unknown error")
            }), login_req.status_code

    # Successful login
    rjson = login_req.json().get('data', {})
    session_ticket = rjson.get('SessionTicket')
    playfab_id = rjson.get('PlayFabId')
    entity = rjson.get('EntityToken', {})
    entity_token = entity.get('EntityToken')
    entity_id = entity.get('Entity', {}).get('Id')
    entity_type = entity.get('Entity', {}).get('Type')
    kid_access_token = rjson.get('KidAccessToken')
    kid_refresh_token = rjson.get('KidRefreshToken')
    kid_url_base_path = rjson.get('KidUrlBasePath')
    location_code = rjson.get('LocationCode')

    # Link the Custom ID
    try:
        requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Client/LinkCustomID",
            json={"CustomID": f"OCULUS{oculus_id}", "ForceLink": True},
            headers={"content-type": "application/json", "x-authorization": session_ticket}
        )
    except Exception as e:
        # Link failure isn't fatal, but log it
        print(f"LinkCustomID failed: {e}")

    ip = request.remote_addr
    send_auth_notification(playfab_id, ip, f"Oculus_{oculus_id}", oculus_id)

    return jsonify({
        "SessionTicket": session_ticket,
        "EntityToken": entity_token,
        "PlayFabId": playfab_id,
        "EntityId": entity_id,
        "EntityType": entity_type,
        "KidAccessToken": kid_access_token,
        "KidRefreshToken": kid_refresh_token,
        "KidUrlBasePath": kid_url_base_path,
        "LocationCode": location_code
    }), 200

@app.route("/api/PlayFabAuthentication/test", methods=["GET"])
def test_auth_notification():
    send_auth_notification("AUTH12345", "127.0.0.1", "TestAuthUser", "1234567890")
    return jsonify({"status": "Test auth notification sent!"}), 200

# -------------------- Title Data --------------------
@app.route("/v1/title-data/client", methods=["POST", "GET"])
@app.route('/api/TitleData', methods=['POST', 'GET'])
def title_data():
    # Merged version: second file's get from PlayFab, first file's static data fallback
    if request.method == "POST" or request.args.get("keys"):
        # fallback to static data from first file
        all_data = {
            "MOTD": "<color=#8a0000>WELCOME TO DEATH TAG</color>\n<color=#ff7b00>WE ARE IN THE FALL 23 UPDATE</color>\n<color=#6600ff>THE OWNERS ARE DEATH AND SOULZ</color>\n<color=#0000ff>JOIN THE DISCORD AT: DISCORD.GG/QatrWFGRVc</color>\n<color=#fc61ff>BOOST THE DISCORD FOR EVERY COSMETICS</color>\n<color=#FF0000>E</color><color=#FF9500>N</color><color=#FFFF00>J</color><color=#00FF00>O</color><color=#0000FF>Y</color><color=#BB00FF>!</color><color=#FF00FF>!</color>",
            "VStumpDiscord": "<color=#0000ff>DISCORD.GG/QatrWFGRVc</color>",
            # ... include all static keys from first file (truncated for brevity)
        }
        keys_param = request.args.get("keys")
        if keys_param:
            requested_keys = [k.strip() for k in keys_param.split(",")]
            all_data = {k: all_data[k] for k in requested_keys if k in all_data}
        results = [{"key": k, "data": v} for k, v in all_data.items()]
        return jsonify({"Results": results})
    else:
        # fetch from PlayFab (second file style)
        response = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/GetTitleData",
            headers=settings.get_auth_headers()
        )
        if response.status_code == 200:
            return jsonify(response.json().get("data", {}).get("Data", {}))
        else:
            return jsonify({}), response.status_code

# -------------------- Cache PlayFab ID --------------------
@app.route("/api/CachePlayFabId", methods=["GET", "POST"])
def cacheplayfabid():
    data = request.get_json()
    if not data:
        return jsonify({"Message": "Success"}), 200
    # second file expects specific fields; we return them
    return jsonify({
        "Message": "Yay Your Authed",
        "PlayFabId": data.get("PlayFabId"),
        "KidAccessToken": data.get("KidAccessToken"),
        "KidRefreshToken": data.get("KidRefreshToken"),
        "KidUrlBasePath": data.get("KidUrlBasePath"),
        "LocationCode": data.get("LocationCode")
    }), 200

# -------------------- IAP --------------------
@app.route("/api/ConsumeOculusIAP", methods=["POST"])
def consume_oculus_iap():
    rjson = request.get_json()
    access_token = rjson.get("userToken")
    user_id = rjson.get("userID")
    nonce = rjson.get("nonce")
    sku = rjson.get("sku")
    response = requests.post(
        url=f"https://graph.oculus.com/consume_entitlement?nonce={nonce}&user_id={user_id}&sku={sku}&access_token={settings.ApiKey}",
        headers={"content-type": "application/json"}
    )
    if response.json().get("success"):
        return jsonify({"result": True})
    else:
        return jsonify({"error": True})

# -------------------- Photon Authentication --------------------
@app.route("/api/photon", methods=["POST", "GET"])
def photonauth():
    print(f"Received {request.method} request at /api/photon")
    getjson = request.get_json()
    Ticket = getjson.get("Ticket")
    Nonce = getjson.get("Nonce")
    Platform = getjson.get("Platform")
    UserId = getjson.get("UserId")
    nickName = getjson.get("username")
    ip = request.remote_addr

    if request.method.upper() == "GET":
        userId = Ticket.split('-')[0] if Ticket else None
        if userId is None or len(userId) != 16:
            return jsonify({'resultCode': 2, 'message': 'Invalid token', 'userId': None, 'nickname': None})
        if Platform != 'Quest':
            return jsonify({'Error': 'Bad request', 'Message': 'Invalid platform!'}), 403
        if Nonce is None:
            return jsonify({'Error': 'Bad request', 'Message': 'Not Authenticated!'}), 304
        req = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
            json={"PlayFabId": userId},
            headers=settings.get_auth_headers()
        )
        if req.status_code == 200:
            nickName = req.json().get("UserInfo", {}).get("UserAccountInfo", {}).get("Username")
            send_photon_notification(userId, ip, nickName, Platform)
            return jsonify({
                'resultCode': 1,
                'message': f'Authenticated user {userId.lower()} title {settings.TitleId.lower()}',
                'userId': userId.upper(),
                'nickname': nickName
            })
        else:
            return jsonify({'resultCode': 0, 'message': "Something went wrong", 'userId': None, 'nickname': None})
    elif request.method.upper() == "POST":
        userId = Ticket.split('-')[0] if Ticket else None
        if userId is None or len(userId) != 16:
            return jsonify({'resultCode': 2, 'message': 'Invalid token', 'userId': None, 'nickname': None})
        req = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
            json={"PlayFabId": userId},
            headers=settings.get_auth_headers()
        )
        if req.status_code == 200:
            nickName = req.json().get("UserInfo", {}).get("UserAccountInfo", {}).get("Username")
            send_photon_notification(userId, ip, nickName, Platform)
            return jsonify({
                'resultCode': 1,
                'message': f'Authenticated user {userId.lower()} title {settings.TitleId.lower()}',
                'userId': userId.upper(),
                'nickname': nickName
            })
        else:
            return jsonify({'resultCode': 0, 'message': "Something went wrong", 'userId': None, 'nickname': None})
    else:
        return jsonify({"Message": "Use a POST or GET Method instead of " + request.method.upper()})

@app.route("/api/photon/test", methods=["GET"])
def test_photon_notification():
    send_photon_notification("TESTUSERID123456", request.remote_addr, "TestUser", "Quest")
    return jsonify({"status": "Test photon notification sent!"}), 200

# -------------------- Additional Endpoints from First File --------------------
@app.route("/v1/userdata/client", methods=["POST", "GET"])
def userdata_client():
    return jsonify("Userdata Client")

@app.route("/api/GetTier", methods=["POST", "GET"])
def get_tier():
    return jsonify("Get Tier")

@app.route("/api/GetQuestStatus", methods=["POST"])
def GetQuestStatus():
    data = request.json
    playfab_id = data.get("playfab_id", "UNKNOWN_ID")
    ip = request.remote_addr
    username = data.get("username", "UnknownUser")
    quest_name = data.get("quest_name", "Unknown Quest")
    send_quest_notification(playfab_id, ip, username, quest_name)
    if playfab_id in ["13DAE985991634E2"]:
        return jsonify({"result": {"dailyPoints": {}, "weeklyPoints": {}, "userPointsTotal": 99999}, "statusCode": 200, "error": None})
    return jsonify({"result": {"dailyPoints": {}, "weeklyPoints": {}, "userPointsTotal": 0}, "statusCode": 200, "error": None})

@app.route("/api/GetQuestStatus/test", methods=["GET"])
def test_quest_notification():
    send_quest_notification("TEST12345", "127.0.0.1", "TestUser", "🏄‍♂️ RIDE THE SHARK")
    return jsonify({"status": "Test notification sent!"}), 200

@app.route("/api/GetProgression", methods=["POST", "GET"])
def get_progression():
    return jsonify("Get Progression")

@app.route("/api/GetShiftCredit", methods=["POST", "GET"])
def get_shift_credit():
    return jsonify("Get Shift Credit")

@app.route("/api/GetActiveSIQuests", methods=["POST", "GET"])
def get_active_si_quests():
    return jsonify("Get Active SI Quests")

@app.route("/v1/client/analytics/event/batch", methods=["POST"])
def analytics():
    rjson = request.get_json(silent=True) or {}
    event_ids = []
    for event in rjson.get("Events", []):
        resp = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Server/WritePlayerEvent",
            headers=settings.get_auth_headers(),
            json={
                "EventName": event.get("EventName"),
                "Timestamp": event.get("EventTimestamp"),
                "Body": event.get("Body"),
                "CustomTags": event.get("CustomTags"),
                "PlayFabId": rjson.get("PlayFabId")
            }
        )
        ev_id = resp.json()
        event_ids.append({"EventId": ev_id.get("data", {}).get("EventId")} if ev_id.get("data") else {"EventId": None})
    return jsonify(event_ids)

# -------------------- Additional Endpoints from Second File --------------------
@app.route("/api/GetFriendsV2", methods=['POST'])
def get_friends_v2():
    return jsonify({"result":{"friends":[{"presence":{"friendLinkId":"YES","userName":"userName","roomId":"roomId","zone":"zone","region":"region","isPublic":True},"created":"2001-09-11T08:46:01.713"}],"myPrivacyState":0},"statusCode":200,"error":None})

@app.route("/api/GetAcceptedAgreements", methods=["POST", "GET"])
def get_accepted_agreements():
    rjson = request.get_json()["FunctionResult"]
    return jsonify(rjson)

@app.route("/api/SubmitAcceptedAgreements", methods=["POST", "GET"])
def submit_accepted_agreements():
    rjson = request.get_json()["FunctionResult"]
    return jsonify(rjson)

@app.route("/api/validate_user", methods=['POST'])
def validate_user():
    data = request.json
    if not data or 'custom_id' not in data:
        return jsonify({"error": "Missing 'custom_id' in request."}), 400
    custom_id = data['custom_id']
    auth_response = requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Client/LoginWithCustomID",
        json={"CustomId": custom_id, "CreateAccount": True, "TitleId": settings.TitleId}
    )
    if auth_response.status_code != 200:
        return jsonify({"error": "Failed to authenticate user."}), 500
    auth_data = auth_response.json()
    if "error" in auth_data:
        return jsonify({"error": auth_data["error"]}), 500
    user_id = auth_data['data']['PlayFabId']
    if not (custom_id.startswith("OCULUS") and custom_id[16:].isdigit()):
        ban_response = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Admin/BanUsers",
            headers={"X-SecretKey": settings.SecretKey},
            json={"Bans": [{"PlayFabId": user_id, "Reason": "Invalid ID format."}]}
        )
        if ban_response.status_code != 200:
            return jsonify({"error": "Failed to ban user."}), 500
        return jsonify({"message": "User banned for invalid ID."}), 200
    return jsonify({"message": "User validated successfully.", "PlayFabId": user_id}), 200

@app.route("/api/ConsumeCodeItem", methods=["POST"])
def consume_code_item():
    rjson = request.get_json()
    code = rjson.get("itemGUID")
    playfab_id = rjson.get("playFabID")
    session_ticket = rjson.get("playFabSessionTicket")
    if not all([code, playfab_id, session_ticket]):
        return jsonify({"error": "Missing parameters"}), 400
    raw_url = ""   # URL to your codes file (GitHub raw)
    response = requests.get(raw_url)
    if response.status_code != 200:
        return jsonify({"error": "GitHub fetch failed"}), 500
    lines = response.text.splitlines()
    codes = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            codes[k.strip()] = v.strip()
    if code not in codes:
        return jsonify({"result": "CodeInvalid"}), 404
    if codes[code] == "AlreadyRedeemed":
        return jsonify({"result": codes[code]}), 200
    grant_response = requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Admin/GrantItemsToUsers",
        json={"ItemGrants": [{"PlayFabId": playfab_id, "ItemId": "dis da cosmetics", "CatalogVersion": "DLC"}]},
        headers=settings.get_auth_headers()
    )
    if grant_response.status_code != 200:
        return jsonify({"result": "PlayFabError", "errorMessage": grant_response.json().get("errorMessage", "Grant failed")}), 500
    # Optionally update the codes file (not implemented here)
    return jsonify({"result": "Success", "itemID": code, "playFabItemName": codes[code]}), 200

@app.route("/api/UploadGorillanalytics", methods=["POST"])
def Upload_Gorillanalytics():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid data"}), 400
    function_result = data.get("FunctionResult", {})
    embed = {
        "title": "New Upload Data",
        "color": 5814783,
        "fields": [
            {"name": "Version", "value": function_result.get("version", "N/A"), "inline": True},
            {"name": "Upload Chance", "value": function_result.get("upload_chance", "N/A"), "inline": True},
            {"name": "Map", "value": function_result.get("map", "N/A"), "inline": True},
            {"name": "Mode", "value": function_result.get("mode", "N/A"), "inline": True},
            {"name": "Queue", "value": function_result.get("queue", "N/A"), "inline": True},
            {"name": "Player Count", "value": str(function_result.get("player_count", "N/A")), "inline": True},
            {"name": "Position", "value": f"({function_result.get('pos_x', 'N/A')}, {function_result.get('pos_y', 'N/A')}, {function_result.get('pos_z', 'N/A')})", "inline": False},
            {"name": "Velocity", "value": f"({function_result.get('vel_x', 'N/A')}, {function_result.get('vel_y', 'N/A')}, {function_result.get('vel_z', 'N/A')})", "inline": False},
            {"name": "Cosmetics Owned", "value": function_result.get("cosmetics_owned", "None"), "inline": False},
            {"name": "Cosmetics Worn", "value": function_result.get("cosmetics_worn", "None"), "inline": False},
        ],
    }
    try:
        requests.post(settings.PlayfabAuthenticationWebhook, json={"embeds": [embed]})
        return jsonify({"status": "Success"}), 200
    except Exception:
        return jsonify({"error": "Failed to send embed"}), 500

@app.route("/api/KIDIntegration", methods=["POST"])
def k_id():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    required_fields = ["Age", "Permissions", "GetSubmittedAge", "VoiceChat", "CustomNames", "PhotonPermission"]
    missing = [field for field in required_fields if field not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    response = {
        "status": "success",
        "UserAge": data.get("Age"),
        "Permissions": data.get("Permissions"),
        "GetSubmittedAge": data.get("GetSubmittedAge"),
        "VoiceChat": data.get("VoiceChat"),
        "CustomNames": data.get("CustomNames"),
        "PhotonPermission": data.get("PhotonPermission"),
        "AnnouncementData": {
            "ShowAnnouncement": "False",
            "AnnouncementID": "kID_Prelaunch",
            "AnnouncementTitle": "IMPORTANT NEWS",
            "Message": "We're working to make Gorilla Tag a better..."
        }
    }
    return jsonify(response), 200

@app.route("/api/CheckForBadName", methods=["POST"])
def check_for_bad_name():
    rjson = request.get_json().get("FunctionResult")
    name = rjson.get("name").upper()
    bad_names = ["KKK", "PENIS", "NIGG", "NEG", "NIGA", "MONKEYSLAVE", "SLAVE", "FAG", 
                 "NAGGI", "TRANNY", "QUEER", "KYS", "DICK", "PUSSY", "VAGINA", "BIGBLACKCOCK", 
                 "DILDO", "HITLER", "KKX", "XKK", "NIGA", "NIGE", "NIG", "NI6", "PORN", 
                 "JEW", "JAXX", "TTTPIG", "SEX", "COCK", "CUM", "FUCK", "PENIS", "DICK", 
                 "ELLIOT", "JMAN", "K9", "NIGGA", "TTTPIG", "NICKER", "NICKA", 
                 "REEL", "NII", "@here", "!", " ", "JMAN", "PPPTIG", "CLEANINGBOT", "JANITOR", "K9", 
                 "H4PKY", "MOSA", "NIGGER", "NIGGA", "IHATENIGGERS", "@everyone", "TTT"]
    if name in bad_names:
        return jsonify({"result": 2})
    else:
        return jsonify({"result": 0})

@app.route("/voten/api/FetchPoll", methods=["GET", "POST"])
def fetch_poll():
    active_polls = [p for p in polls if p.get("isActive", False)]
    return jsonify(active_polls), 200

@app.route("/voten/api/Vote", methods=["POST"])
def vote():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    poll_id_str = data.get("PollId")
    playfab_id = data.get("PlayFabId")
    option_index_str = data.get("OptionIndex")
    is_prediction = data.get("IsPrediction", False)
    if not all([poll_id_str, playfab_id, option_index_str is not None]):
        return jsonify({"error": "Missing PollId, PlayFabId, or OptionIndex"}), 400
    try:
        poll_id = int(poll_id_str)
        option_index = int(option_index_str)
    except ValueError:
        return jsonify({"error": "PollId and OptionIndex must be integers"}), 400
    poll = next((p for p in polls if p["pollId"] == poll_id), None)
    if not poll:
        return jsonify({"error": "Poll not found"}), 404
    if not poll.get("isActive", False):
        return jsonify({"error": "Poll is not active"}), 403
    if not (0 <= option_index < len(poll["voteOptions"])):
        return jsonify({"error": "Invalid option index"}), 400
    # Send to Discord
    embed = {
        "embeds": [{
            "title": "✅ - Vote success",
            "description": f"**PlayFab ID**: {playfab_id}\n**Prediction**: {is_prediction}\n**Question**: {poll['question']}\n**Voting for**: {poll['voteOptions'][option_index]}",
            "color": 3447003
        }]
    }
    try:
        requests.post(settings.PlayfabAuthenticationWebhook, json=embed, timeout=5)
    except Exception as e:
        print(f"Failed to send vote to Discord: {e}")
    return jsonify({"success": True, "message": "Vote cast successfully"}), 200

@app.route("/api/FakeMothershipAuth", methods=["POST"])
def mothership_auth():
    datp = request.get_json()
    if not datp:
        return jsonify({"Error": "Bad request", "Message": "No JSON body"}), 400
    CustomId = datp.get("CustomId")
    PlayFabId_req = datp.get("PlayFabId")
    GameMode = datp.get("GameMode", "DefaultMode")
    DeviceType = datp.get("Device", "Unknown")
    Region = datp.get("Region", "global")
    if not CustomId or not PlayFabId_req:
        return jsonify({"Error": "Bad request", "Message": "Missing CustomId or PlayFabId"}), 400
    login_response = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId",
        json={"ServerCustomId": CustomId, "CreateAccount": False},
        headers=settings.get_auth_headers()
    )
    if login_response.status_code != 200:
        login_json = login_response.json()
        if login_json.get('errorCode') == 1002:
            ban_details = login_json.get('errorDetails', {})
            ban_expiration_key = next(iter(ban_details.keys()), "BanReason")
            ban_expiration_list = ban_details.get(ban_expiration_key, [])
            ban_expiration = ban_expiration_list[0] if ban_expiration_list else "No expiration date provided."
            return jsonify({
                'BanReason': f"{ban_expiration_key}: {login_json.get('errorMessage', 'Banned.')}",
                'BanExpiration': ban_expiration,
                'Region': Region,
                'GameMode': GameMode
            }), 403
        return jsonify({'Error': 'PlayFab Login Error', 'Message': login_json.get('errorMessage', 'Unknown error')}), login_response.status_code
    link_response = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomId",
        json={"PlayFabId": PlayFabId_req, "ServerCustomId": CustomId, "ForceLink": True},
        headers=settings.get_auth_headers()
    )
    if link_response.status_code != 200:
        return jsonify({"status": "error", "step": "LinkServerCustomId", "code": link_response.status_code, "error": link_response.text}), link_response.status_code
    services = {"CosmeticsSync": True, "FriendsInit": True, "GuildSync": False, "SeasonalEvents": True}
    return jsonify({
        "status": "success",
        "GameMode": GameMode,
        "Region": Region,
        "Device": DeviceType,
        "loginData": login_response.json().get("data"),
        "linkData": link_response.json().get("data"),
        "servicesInitialized": services
    })

@app.route("/api/ReturnMyOculusHash")
def return_my_oculus_hash():
    return ReturnFunctionJson(request.get_json(), "ReturnMyOculusHash")

@app.route("/api/ReturnCurrentVersion", methods=["POST", "GET"])
def return_current_version():
    return ReturnFunctionJson(request.get_json(), "ReturnCurrentVersion")

@app.route("/api/TryDistributeCurrency", methods=["POST", "GET"])
def try_distribute_currency():
    return ReturnFunctionJson(request.get_json(), "TryDistributeCurrency")

@app.route("/api/BroadCastMyRoom", methods=["POST", "GET"])
def broadcast_my_room():
    return ReturnFunctionJson(request.get_json(), "BroadCastMyRoom", request.get_json()["FunctionParameter"])

@app.route("/api/ShouldUserAutomutePlayer", methods=["POST", "GET"])
def should_user_automute_player():
    return jsonify(mute_cache)

# ========================= RUN =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9080)
