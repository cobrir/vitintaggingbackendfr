import json
import random
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)


TITLE_ID = "C1667"
SECRET_KEY = "UFYTWKIM7W9IH3HX8DYXC8O63MSG7A947IIR6FMYMIE6DBK85M"
API_KEY = "OC|2|1248500195009705674541478a2e9fd799b0e75a336472a"

def get_auth_headers():
    return {"Content-Type": "application/json", "X-SecretKey": SECRET_KEY}


@app.route('/api/TD', methods=['POST'])
def titled_data():
    return jsonify({"MOTD":" Put your motd u want like (suck my dick and join the discord) "})

@app.route("/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():
    data = request.get_json()
    oculus_id = data.get("OculusId", "Null")
    nonce = data.get("Nonce", "Null")
    platform = data.get("Platform", "Null")

    login_req = requests.post(
        url=f"https://{TITLE_ID}.playfabapi.com/Server/LoginWithServerCustomId",
        json={
            "ServerCustomId": f"OCULUS{oculus_id}",
            "CreateAccount": True
        },
        headers=get_auth_headers()
    )

    if login_req.status_code == 200:
        rjson = login_req.json().get('data', {})
        session_ticket = rjson.get('SessionTicket')
        playfab_id = rjson.get('PlayFabId')
        entity = rjson.get('EntityToken', {})
        entity_token = entity.get('EntityToken')
        entity_id = entity.get('Entity', {}).get('Id')
        entity_type = entity.get('Entity', {}).get('Type')

        
        requests.post(
            url=f"https://{TITLE_ID}.playfabapi.com/Client/LinkCustomID",
            json={"CustomID": f"OCULUS{oculus_id}", "ForceLink": True},
            headers={
                "content-type": "application/json",
                "x-authorization": session_ticket
            }
        )

        return jsonify({
            "PlayFabId": playfab_id,
            "SessionTicket": session_ticket,
            "EntityToken": entity_token,
            "EntityId": entity_id,
            "EntityType": entity_type,
            "Nonce": nonce,
            "OculusId": oculus_id,
            "Platform": platform
        }), 200
    else:
        ban_info = login_req.json()
        if ban_info.get("errorCode") == 1002:
            details = ban_info.get("errorDetails", {})
            ban_reason = next(iter(details.keys()), "Banned")
            ban_time = details.get(ban_reason, ["Indefinite"])[0]
            return jsonify({
                "BanMessage": ban_reason,
                "BanExpirationTime": ban_time,
            }), 403
        return jsonify({"Message": "Login failed"}), 403
        

@app.route("/api/CheckForBadName", methods=["POST"])
def check_for_bad_name():
    rjson = request.get_json().get("FunctionResult")
    name = rjson.get("name").upper()

    if name in ["KKK", "PENIS", "NIGG", "NEG", "NIGA", "MONKEYSLAVE", "SLAVE", "FAG",
        "NAGGI", "TRANNY", "QUEER", "KYS", "DICK", "PUSSY", "VAGINA", "BIGBLACKCOCK",
        "DILDO", "HITLER", "KKX", "XKK", "NIGA", "NIGE", "NIG", "NI6", "PORN",
        "JEW", "JAXX", "TTTPIG", "SEX", "COCK", "CUM", "FUCK", "PENIS", "DICK",
        "ELLIOT", "JMAN", "K9", "NIGGA", "TTTPIG", "NICKER", "NICKA",
        "REEL", "NII", "@here", "!", " ", "JMAN", "PPPTIG", "CLEANINGBOT", "JANITOR", "K9",
        "H4PKY", "MOSA", "NIGGER", "NIGGA", "IHATENIGGERS", "@everyone", "TTT"]:
        return jsonify({"result": 2})
    else:
        return jsonify({"result": 0})

@app.route("/api/CachePlayFabId", methods=["POST"])
def cache_playfab_id():
    data = request.get_json()
    session_ticket = data.get("SessionTicket")
    if session_ticket:
        playfab_id = session_ticket.split("-")[0]
        return jsonify({"Message": "Authed", "PlayFabId": playfab_id}), 200
    return jsonify({"Message": "Try Again Later."}), 404

@app.route("/api/ConsumeOculusIAP", methods=["POST"])
def consume_oculus_iap():
    data = request.get_json()
    access_token = data.get("userToken")
    user_id = data.get("userID")
    nonce = data.get("nonce")
    sku = data.get("sku")

    response = requests.post(
        url=f"https://graph.oculus.com/consume_entitlement?nonce={nonce}&user_id={user_id}&sku={sku}&access_token={API_KEY}",
        headers={"content-type": "application/json"}
    )

    if response.json().get("success"):
        return jsonify({"result": True})
    return jsonify({"error": True})


@app.route("/api/photon", methods=["POST"])
def photonauth():
    AA = request.get_json()
    PlayFabId = AA.get("PlayFabId")
    OrgScopedID = AA.get("OrgScopedId")
    CustomId = AA.get("CustomID")
    Platform = AA.get("Platform")
    Nonce = AA.get("Nonce")
    UserId = AA.get("UserId")
    MasterPlayer = AA.get("Master")
    GorillaTagger = AA.get("GorillaTagger")
    CosmeticsInRoom = AA.get("CosmeticsInRoom")
    SharedGroupData = AA.get("SharedGroupData")
    UpdatePlayerCosmetics = AA.get("UpdatePlayerCosmetics")
    MasterClient = AA.get("MasterClient")
    ItemIds = AA.get("ItemIds")
    PlayerCount = AA.get("PlayerCount")
    CosmeticAuthenticationV2 = AA.get("CosmeticAuthenticationV2")
    RPCS = AA.get("RPCS")
    BroadcastMyRoomV2 = AA.get("BroadcastMyRoomV2")
    DLCOwnerShipV2 = AA.get("DLCOwnerShipV2")
    GorillaCorpCurrencyV1 = AA.get("GorillaCorpCurrencyV1")
    DeadMonke = AA.get("DeadMonke")
    GhostCounter = AA.get("GhostCounter")
    DirtyCosmeticSpawnnerV2 = AA.get("DirtyCosmeticSpawnnerV2")
    RoomJoined = AA.get("RoomJoined")
    VirtualStump = AA.get("VirtualStump")
    PlayerRoomCount = AA.get("PlayerRoomCount")
    AppVersion = AA.get("AppVersion")
    AppId = AA.get("AppId")
    TaggedDistance = AA.get("TaggedDistance")
    TaggedClient = AA.get("TaggedClient")
    OculusId = AA.get("OCULUSId")
    TitleId = AA.get("TITLE_ID")

    return jsonify({
        "ResultCode": 1,
        "StatusCode": 200,
        "Message": "authed with photon",
        "Result": 0,
        "UserId": UserId,
        "AppId": AppId,
        "AppVersion": AppVersion,
        "Ticket": AA.get("Ticket"),
        "Token": AA.get("Token"),
        "Nonce": Nonce,
        "Platform": Platform,
        "Username": AA.get("Username"),
        "PlayerRoomCount": PlayerRoomCount,
        "GorillaTagger": GorillaTagger,
        "CosmeticAuthentication": CosmeticAuthenticationV2,
        "CosmeticsInRoom": CosmeticsInRoom,
        "UpdatePlayerCosmetics": UpdatePlayerCosmetics,
        "DLCOwnerShip": DLCOwnerShipV2,
        "Currency": GorillaCorpCurrencyV1,
        "RoomJoined": RoomJoined,     
        "VirtualStump": VirtualStump,
        "DeadMonke": DeadMonke,
        "GhostCounter": GhostCounter,
        "BroadcastRoom": BroadcastMyRoomV2,
        "TaggedClient": TaggedClient,
        "TaggedDistance": TaggedDistance,
        "RPCS": RPCS
    }), 200


if __name__ == "__main__":
    app.run(debug=True)


@app.route("/", methods=["GET"])
def main():
    image_url = "https://imgs.search.brave.com/50ma5iuDOgB3FXoOqkmidyp8U88p3Y1MA-PnQBpyqio/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9iaWdz/dGFyYmlvLmNvbS93/cC1jb250ZW50L3Vw/bG9hZHMvMjAyMi8w/MS9Kb2UtQmFydG9s/b3p6aS5qcGc"
    
    return f"""
    <html>
      <head>
        <title></title>
        <style>
          body {{
            background-color: #111;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
          }}
          img {{
            max-width: 90vw;
            max-height: 90vh;
            border-radius: 12px;
            box-shadow: 0 0 20px rgba(255,255,255,0.2);
          }}
        </style>
      </head>
      <body>
        <img src="{image_url}" alt="Clean Image" />
      </body>
    </html>
    """
