import json
import random
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)


TITLE_ID = "1304FC"
SECRET_KEY = "X6MC6JECAYKFMC1N5KO9UTNIYNQF3A6IRXG4531GW4MSP197OH"
API_KEY = "OC|1248500195009702|5674541478a2e9fd799b0e75a336472a"

def get_auth_headers():
    return {"Content-Type": "application/json", "X-SecretKey": SECRET_KEY}


@app.route('/api/TitleData', methods=['POST'])
def titled_data():
    return jsonify({"MOTD":"give creds to death or im fucking up your game"})

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


@app.route(
    "/api/photon/authenticate",
    methods=["POST"]
)
def photon_authenticate():

    user_id = request.args.get(
        "username"
    )

    token = request.args.get(
        "token"
    )

    if not user_id or len(user_id) != 16:
        return jsonify({
            "resultCode": 2,
            "message": "Invalid token",
            "userId": None,
            "nickname": None
        })

    if not token:
        return jsonify({
            "resultCode": 3,
            "message": "Failed to parse token from request",
            "userId": None,
            "nickname": None
        })

    if not TITLE_ID or not SECRET_KEY:
        return jsonify({
            "resultCode": 0,
            "message": "Server configuration is incomplete",
            "userId": None,
            "nickname": None
        }), 500

    try:
        response = requests.post(
            url=(
                f"https://{TITLE_ID}.playfabapi.com/"
                "Server/GetUserAccountInfo"
            ),
            json={
                "PlayFabId": user_id
            },
            headers=playfab_headers(),
            timeout=10
        )

        response.raise_for_status()

    except requests.RequestException as e:
        return jsonify({
            "resultCode": 0,
            "message": f"Error: {str(e)}",
            "userId": None,
            "nickname": None
        })

    try:
        response_json = response.json()

        user_info = (
            response_json
            .get("data", {})
            .get("UserInfo", {})
        )

        title_info = (
            user_info
            .get("TitleInfo", {})
        )

        nickname = title_info.get(
            "DisplayName"
        )

    except (
        ValueError,
        KeyError,
        TypeError
    ) as e:
        return jsonify({
            "resultCode": 0,
            "message": (
                f"Error parsing response: {str(e)}"
            ),
            "userId": None,
            "nickname": None
        })

    return jsonify({
        "resultCode": 1,
        "message": (
            f"Authenticated user "
            f"{user_id.lower()} "
            f"title "
            f"{TITLE_ID.lower()}"
        ),
        "userId": user_id.upper(),
        "nickname": nickname
    })


if __name__ == "__main__":
    app.run(debug=True)


@app.route(
    "/",
    methods=["POST", "GET"]
)
def main():
    return "creds to death for this backend", 200
