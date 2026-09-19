# BACKEND POSTED FOR S4GE'S BEACH BOOSTERS BY L1RSON ON 10/03/2025! CREDITS TO WHOEVER ACTUALLY MADE THIS BACKEND :)

import requests
import random
from flask import Flask, jsonify, request
import json
import os
import base64

class GameInfo:
    def __init__(self):
        self.TitleId: str = "C1667"
        self.SecretKey: str = "UFYTWKIM7W9IH3HX8DYXC8O63MSG7A947IIR6FMYMIE6DBK85Mv"
        self.ApiKey: str = "OC|2|1248500195009705674541478a2e9fd799b0e75a336472a"
        self.DiscordWebhookUrl: str = ""

    def get_auth_headers(self):
        return {"content-type": "application/json", "X-SecretKey": self.SecretKey}


settings = GameInfo()
app = Flask(__name__)

def get_client_ip():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()

def GetOrgScopedId(oculus_id: str):
    url = f"https://graph.oculus.com/{oculus_id}?access_token={settings.ApiKey}&fields=org_scoped_id"
    headers = {"Content-Type": "application/json"}
    res = requests.get(url=url, headers=headers)
    if res.status_code == 200:
        return res.json().get("org_scoped_id")
    return None

def send_auth_webhook(success: bool, player_ip: str, custom_id: str = None, playfab_id: str = None, oculus_id: str = None, error_message: str = None):
    try:
        if success:
            embed_data = {
                "content": None,
                "embeds": [{
                    "color": 65280,  
                    "fields": [{
                        "name": "NORMAL FELLA LOGGED IN!",
                        "value": f"```ini\n[ Player's IP ]: {request.headers.get('X-Real-IP') or player_ip}\n[Custom ID]: {custom_id or 'N/A'}\n[Player ID]: {playfab_id or 'N/A'}\n[Orgscoped ID]: {oculus_id or 'N/A'}```"
                    }],
                    "author": {
                        "name": "Sigmer Auth"
                    }
                }]
            }
        else:
            embed_data = {
                "content": None,
                "embeds": [{
                    "color": 16711680,  
                    "fields": [{
                        "name": "INVALID FELLA TRIED TO AUTH!",
                        "value": f"```ini\n[ Player's IP ]: {request.headers.get('X-Real-IP') or player_ip}\n[Custom ID]: {custom_id or 'N/A'}\n[Orgscoped ID]: {oculus_id or 'N/A'}\n[Error]: {error_message or 'Unknown Error'}```"
                    }],
                    "author": {
                        "name": "Sigmer Auth"
                    }
                }]
            }
        
        requests.post(settings.DiscordWebhookUrl, json=embed_data, timeout=5)
    except Exception as e:
        print(f"Failed to send webhook: {e}")

def ReturnFunctionJson(data, funcname, funcparam={}):
    rjson = data["FunctionParameter"]
    userId: str = rjson.get("CallerEntityProfile").get("Lineage").get(
        "TitlePlayerAccountId")

    req = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/ExecuteCloudScript",
        json={
            "PlayFabId": userId,
            "FunctionName": funcname,
            "FunctionParameter": funcparam
        },
        headers=settings.GetAuthHeaders())

    if req.status_code == 200:
        return jsonify(
            req.json().get("data").get("FunctionResult")), req.status_code
    else:
        return jsonify({}), req.status_code


def GetIsNonceValid(nonce: str, oculusId: str):
    req = requests.post(
        url=f'https://graph.oculus.com/user_nonce_validate?nonce=' + nonce +
        '&user_id=' + oculusId + '&access_token=' + settings.ApiKey,
        headers={"content-type": "application/json"})
    return req.json().get("is_valid")


@app.route("/", methods=["POST", "GET"])
def main():
    return """
        <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
            </head>
            <body style="font-family: 'Inter', sans-serif;">
                <h1 style="color: red; font-size: 30px;">
                    WHAT DA SIGMER
                </h1>
            </body>
        </html>
    """

# Replace https://auth-prod.gtag-cf.com/api/PlayFabAuthentication with this endpoint
@app.route("/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():
    rjson = request.get_json()
    client_ip = get_client_ip()
    required_fields = ["Nonce", "AppId", "Platform", "OculusId"]
    missing_fields = [field for field in required_fields if not rjson.get(field)]

    if missing_fields:
        send_auth_webhook(False, client_ip, error_message=f"Missing parameter(s): {', '.join(missing_fields)}")
        return (
            jsonify(
                {
                    "Message": f"Missing parameter(s): {', '.join(missing_fields)}",
                    "Error": f"BadRequest-No{missing_fields[0]}",
                }
            ),
            401,
        )

    if rjson.get("AppId") != settings.TitleId:
        send_auth_webhook(False, client_ip, oculus_id=rjson.get("OculusId"), error_message="App ID mismatch")
        return (
            jsonify(
                {
                    "Message": "Request sent for the wrong App ID",
                    "Error": "BadRequest-AppIdMismatch",
                }
            ),
            400,
        )

    
    oculus_id = rjson.get("OculusId")
    org_scoped_id = GetOrgScopedId(oculus_id)
    if not org_scoped_id:
        send_auth_webhook(False, client_ip, oculus_id=oculus_id, error_message="Invalid Oculus ID or org-scoped ID verification failed")
        return (
            jsonify(
                {
                    "Message": "Invalid Oculus ID",
                    "Error": "BadRequest-InvalidOculusId",
                }
            ),
            400,
        )

    url = f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId"
    login_request = requests.post(
        url=url,
        json={
            "ServerCustomId": "OCULUS" + oculus_id,
            "CreateAccount": True,
        },
        headers=settings.get_auth_headers(),
    )

    if login_request.status_code == 200:
        data = login_request.json().get("data")
        session_ticket = data.get("SessionTicket")
        entity_token = data.get("EntityToken").get("EntityToken")
        playfab_id = data.get("PlayFabId")
        entity_type = data.get("EntityToken").get("Entity").get("Type")
        entity_id = data.get("EntityToken").get("Entity").get("Id")

        link_response = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomId",
            json={
                "ForceLink": True,
                "PlayFabId": playfab_id,
                "ServerCustomId": rjson.get("CustomId"),
            },
            headers=settings.get_auth_headers(),
        ).json()

        send_auth_webhook(True, client_ip, rjson.get("CustomId"), playfab_id, oculus_id)

        return (
            jsonify(
                {
                    "PlayFabId": playfab_id,
                    "SessionTicket": session_ticket,
                    "EntityToken": entity_token,
                    "EntityId": entity_id,
                    "EntityType": entity_type,
                }
            ),
            200,
        )
    else:
        if login_request.status_code == 403:
            ban_info = login_request.json()
            if ban_info.get("errorCode") == 1002:
                ban_message = ban_info.get("errorMessage", "No ban message provided.")
                ban_details = ban_info.get("errorDetails", {})
                ban_expiration_key = next(iter(ban_details.keys()), None)
                ban_expiration_list = ban_details.get(ban_expiration_key, [])
                ban_expiration = (
                    ban_expiration_list[0]
                    if len(ban_expiration_list) > 0
                    else "No expiration date provided."
                )
                send_auth_webhook(False, client_ip, rjson.get("CustomId"), error_message=f"User banned: {ban_message}", oculus_id=oculus_id)
                print(ban_info)
                return (
                    jsonify(
                        {
                            "BanMessage": ban_expiration_key,
                            "BanExpirationTime": ban_expiration,
                        }
                    ),
                    403,
                )
            else:
                error_message = ban_info.get(
                    "errorMessage", "Forbidden without ban information."
                )
                send_auth_webhook(False, client_ip, rjson.get("CustomId"), error_message=error_message, oculus_id=oculus_id)
                return (
                    jsonify({"Error": "PlayFab Error", "Message": error_message}),
                    403,
                )
        else:
            error_info = login_request.json()
            error_message = error_info.get("errorMessage", "An error occurred.")
            send_auth_webhook(False, client_ip, rjson.get("CustomId"), error_message=error_message, oculus_id=oculus_id)
            return (
                jsonify({"Error": "PlayFab Error", "Message": error_message}),
                login_request.status_code,
            )

# Replace https://auth-prod.gtag-cf.com/api/CachePlayFabId with this endpoint
@app.route("/api/CachePlayFabId", methods=["POST"])
def cache_playfab_id():
    return jsonify({"Message": "Success"}), 200


# Replace https://title-data.gtag-cf.com with this endpoint
@app.route('/api/TitleData', methods=['POST', 'GET'])
def titledata():
    response_data = {
        "AutoMuteCheckedHours": {
            "hours": 169
        },
        "AutoName_Adverbs": [
            "Cool", "Fine", "Bald", "Bold", "Half", 
            "Only", "Calm", "Fab", "Ice", "Mad", 
            "Rad", "Big", "New", "Old", "Shy"
        ],
        "AutoName_Nouns": [
            "Gorilla", "Chicken", "Darling", "Sloth", "King", 
            "Queen", "Royal", "Major", "Actor", "Agent", 
            "Elder", "Honey", "Nurse", "Doctor", "Rebel", 
            "Shape", "Ally", "Driver", "Deputy"
        ],
        "CreditsData": [
            {
                "Title": "<color=blue>UPDATE MAKERS/PLAYFAB MANAGERS</color>",
                "Entries": [
                    "L1RSON (UPDATE MAKER/PLAYFAB MANAGER)",
                    "KITTY (OWNER/PLAYFAB MANAGER)",
                    "Z3N (OWNER)"
                ]
            },
            {
                "Title": "<color=yellow>CREDITS TO</color>",
                "Entries": [
                    "TABLE",
                    "L1RSON",
                    "S4GE",
                    "IRES",
                    "QUIZX"
                ]
            },
            {
                "Title": "<color=red>GAY FELLAS</color>",
                "Entries": [
                    "DESK",
                    "TABLE",
                    "IRES",
                    "RASP",
                    "KEN"
                ]
            }
        ],
        "BundleBoardSign": "<color=#ff4141>DISCORD.GG/Vnkh3Hr9RE</color>",
        "BundleKioskButton": "<color=#ff4141>DISCORD.GG/Vnkh3Hr9RE</color>",
        "BundleKioskSign": "<color=#ff4141>DISCORD.GG/Vnkh3Hr9RE</color>",
        "BundleLargeSign": "<color=#ff4141>DISCORD.GG/Vnkh3Hr9RE</color>",
        "EmptyFlashbackText": "FLOOR TWO NOW OPEN\n FOR BUSINESS\n\nSTILL SEARCHING FOR\nBOX LABELED 2021",
        "EnableCustomAuthentication": True,
        "GorillanalyticsChance": 4320,
        "LatestPrivacyPolicyVersion": "2024.09.20",
        "LatestTOSVersion": "2024.09.20",
        "MOTD": "<color=#bb29ff>[ WELCOME TO ORIGINAL TAG REVIVED ]</color>\n <color=#07dde8>CHRISTMUH 23!</color>\n<color=#ffff00>CREATOR/FOUNDER : Z3N</color>\n<color=#969696>CREDITS TO: IRES, L1RSON, S4GE, SCREAMINGCAT, Z3N, RASP, TABLE</color>\n<color=#ff8800>DISCORD.GG/Vnkh3Hr9RE</color>\n<color=#000000>CHANGE YOUR NAME FROM oldgorilla AS IT'S BANNABLE!</color>",
        "SeasonalStoreBoardSign": "<color=yellow>RATE THE GAME 5 STARS!</color>\n\n<color=aqua>.GG/Vnkh3Hr9RE",
        "TOS_2024.09.20": "DISCORD.GG/Vnkh3Hr9RE",
        "TOBAlreadyOwnCompTxt": "DISCORD.GG/Vnkh3Hr9RE",
        "TOBAlreadyOwnPurchaseBundle": "RETRO",
        "TOBDefCompTxt": "DISCORD.GG/Vnkh3Hr9RE",
        "TOBDefPurchaseBtnDefTxt": "RETRO",
        "UseLegacyIAP": False
    }
    return jsonify(response_data)


# Replace https://iap.gtag-cf.com/api/ConsumeOculusIAP with this endpoint
@app.route("/api/ConsumeOculusIAP", methods=["POST"])
def consume_oculus_iap():
    rjson = request.get_json()

    access_token = rjson.get("userToken")
    user_id = rjson.get("userID")
    nonce = rjson.get("nonce")
    sku = rjson.get("sku")

    response = requests.post(
        url=f"https://graph.oculus.com/consume_entitlement?nonce={nonce}&user_id={user_id}&sku={sku}&access_token={settings.ApiKey}",
        headers={"content-type": "application/json"},
    )

    if response.json().get("success"):
        return jsonify({"result": True})
    else:
        return jsonify({"error": True})

@app.route("/api/GetAcceptedAgreements", methods=['POST', 'GET'])
def GetAcceptedAgreements():
  data = request.json

  return jsonify({"PrivacyPolicy":"1.1.28","TOS":"11.05.22.2"}), 200

@app.route("/api/SubmitAcceptedAgreements", methods=['POST', 'GET'])
def SubmitAcceptedAgreements():
  data = request.json

  return jsonify({}), 200

@app.route("/api/ConsumeCodeItem", methods=["POST"])
def consume_code_item():
    rjson = request.get_json()
    code = rjson.get("itemGUID")
    playfab_id = rjson.get("playFabID")
    session_ticket = rjson.get("playFabSessionTicket")

    if not all([code, playfab_id, session_ticket]):
        return jsonify({"error": "Missing parameters"}), 400

    raw_url = f"https://github.com/redapplegtag/backendsfrr" # make a github and put the raw here (Redeemed = not redeemed, u have to add discord webhookss and if your smart you can make it so it auto updates the github url (redeemed is not redeemed, AlreadyRedeemed is already redeemed, then dats it
    # code:Redeemed 
    response = requests.get(raw_url)

    if response.status_code != 200:
        return jsonify({"error": "GitHub fetch failed"}), 500

    lines = response.text.splitlines()
    codes = {split[0].strip(): split[1].strip() for line in lines if (split := line.split(":")) and len(split) == 2}

    if code not in codes:
        return jsonify({"result": "CodeInvalid"}), 404

    if codes[code] == "AlreadyRedeemed":
        return jsonify({"result": codes[code]}), 200

    grant_response = requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Admin/GrantItemsToUsers",
        json={
            "ItemGrants": [
                {
                    "PlayFabId": playfab_id,
                    "ItemId": item_id,
                    "CatalogVersion": "DLC"
                } for item_id in ["dis da cosmetics", "anotehr cposmetic", "anotehr"]
            ]
        },
        headers=settings.get_auth_headers()
    )


    if grant_response.status_code != 200:
        return jsonify({"result": "PlayFabError", "errorMessage": grant_response.json().get("errorMessage", "Grant failed")}), 500

    new_lines = [f"{split[0].strip()}:AlreadyRedeemed" if split[0].strip() == code else line.strip() 
             for line in lines if (split := line.split(":")) and len(split) >= 2]

    updated_content = "\n".join(new_lines).strip()

    return jsonify({"result": "Success", "itemID": code, "playFabItemName": codes[code]}), 200

@app.route('/api/v2/GetName', methods=['POST', 'GET'])
def GetNameIg():
    return jsonify({"result": f"GORILLA{random.randint(1000,9999)}"})

# Put your backend URL with this endpoint /api/photon into your photon and photon voice custom server!
@app.route("/api/photon", methods=["POST"])
def photonauth():
    print(f"Received {request.method} request at /api/photon")
    getjson = request.get_json()
    Ticket = getjson.get("Ticket")
    Nonce = getjson.get("Nonce")
    Platform = getjson.get("Platform")
    UserId = getjson.get("UserId")
    nickName = getjson.get("username")
    if request.method.upper() == "GET":
        rjson = request.get_json()
        print(f"{request.method} : {rjson}")

        userId = Ticket.split('-')[0] if Ticket else None
        print(f"Extracted userId: {UserId}")

        if userId is None or len(userId) != 16:
            print("Invalid userId")
            return jsonify({
                'resultCode': 2,
                'message': 'Invalid token',
                'userId': None,
                'nickname': None
            })

        if Platform != 'Quest':
            return jsonify({'Error': 'Bad request', 'Message': 'Invalid platform!'}),403

        if Nonce is None:
            return jsonify({'Error': 'Bad request', 'Message': 'Not Authenticated!'}),304

        req = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
            json={"PlayFabId": userId},
            headers={
                "content-type": "application/json",
                "X-SecretKey": secretkey
            })

        print(f"Request to PlayFab returned status code: {req.status_code}")

        if req.status_code == 200:
            nickName = req.json().get("UserInfo",
                                      {}).get("UserAccountInfo",
                                              {}).get("Username")
            if not nickName:
                nickName = None

            print(
                f"Authenticated user {userId.lower()} with nickname: {nickName}"
            )

            return jsonify({
                'resultCode': 1,
                'message':
                f'Authenticated user {userId.lower()} title {settings.TitleId.lower()}',
                'userId': f'{userId.upper()}',
                'nickname': nickName
            })
        else:
            print("Failed to get user account info from PlayFab")
            return jsonify({
                'resultCode': 0,
                'message': "Something went wrong",
                'userId': None,
                'nickname': None
            })

    elif request.method.upper() == "POST":
        rjson = request.get_json()
        print(f"{request.method} : {rjson}")

        ticket = rjson.get("Ticket")
        userId = ticket.split('-')[0] if ticket else None
        print(f"Extracted userId: {userId}")

        if userId is None or len(userId) != 16:
            print("Invalid userId")
            return jsonify({
                'resultCode': 2,
                'message': 'Invalid token',
                'userId': None,
                'nickname': None
            })

        req = requests.post(
             url=f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
             json={"PlayFabId": userId},
             headers={
                 "content-type": "application/json",
                 "X-SecretKey": settings.SecretKey
             })

        print(f"Authenticated user {userId.lower()}")
        print(f"Request to PlayFab returned status code: {req.status_code}")

        if req.status_code == 200:
             nickName = req.json().get("UserInfo",
                                       {}).get("UserAccountInfo",
                                               {}).get("Username")
             if not nickName:
                 nickName = None
             return jsonify({
                 'resultCode': 1,
                 'message':
                 f'Authenticated user {userId.lower()} title {settings.TitleId.lower()}',
                 'userId': f'{userId.upper()}',
                 'nickname': nickName
             })
        else:
             print("Failed to get user account info from PlayFab")
             successJson = {
                 'resultCode': 0,
                 'message': "Something went wrong",
                 'userId': None,
                 'nickname': None
             }
             authPostData = {}
             for key, value in authPostData.items():
                 successJson[key] = value
             print(f"Returning successJson: {successJson}")
             return jsonify(successJson)
    else:
         print(f"Invalid method: {request.method.upper()}")
         return jsonify({
             "Message":
             "Use a POST or GET Method instead of " + request.method.upper()
         })


def ReturnFunctionJson(data, funcname, funcparam={}):
    print(f"Calling function: {funcname} with parameters: {funcparam}")
    rjson = data.get("FunctionParameter", {})
    userId = rjson.get("CallerEntityProfile",
                       {}).get("Lineage", {}).get("TitlePlayerAccountId")

    print(f"UserId: {userId}")

    req = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/ExecuteCloudScript",
        json={
            "PlayFabId": userId,
            "FunctionName": funcname,
            "FunctionParameter": funcparam
        },
        headers={
            "content-type": "application/json",
            "X-SecretKey": secretkey
        })

    if req.status_code == 200:
        result = req.json().get("data", {}).get("FunctionResult", {})
        print(f"Function result: {result}")
        return jsonify(result), req.status_code
    else:
        print(f"Function execution failed, status code: {req.status_code}")
        return jsonify({}), req.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9080)
