from bottle import request, response, route, run, static_file
from datetime import datetime, timezone
from dateutil import tz
from resources.lib import tools
from urllib.parse import quote
import json, os, requests, time, xbmc, xbmcaddon, xbmcgui, xbmcvfs, xmltodict


release_pids = {}

### NOW PARAMS
   
headers = {   
    'x-skyott-client-version': '4.3.12',
    'x-skyott-device': 'TV',
    'x-skyott-platform': 'ANDROIDTV',
    'x-skyott-proposition': 'NOWOTT',
    'x-skyott-provider': 'NOWTV',
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
}

ovp_url = "https://ovp"
web_url = "https://web.clients"

cc_urls = {
    "DE": "wowtv.de", 
    "GB": "nowtv.com", 
    "IT": "nowtv.it"
}

cc_headers = {
    "DE": {
        'x-skyott-activeterritory': 'DE',
        'x-skyott-language': 'de-DE',
        'x-skyott-territory': 'DE'
    },
    "GB": {
        'x-skyott-activeterritory': 'GB',
        'x-skyott-language': 'en-GB',
        'x-skyott-territory': 'GB'
    },
    "IT": {
        'x-skyott-activeterritory': 'IT',
        'x-skyott-language': 'it-IT',
        'x-skyott-territory': 'IT'
    }
}

# KODI PARAMS
__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
__addondir__    = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
__addonpath__   = xbmcvfs.translatePath(__addon__.getAddonInfo('path'))


#
# WEB SERVER
#

def init_config(t):
    global w
    w = t


class WebServer():

    def __init__(self):
        init_config(self)

        self.session = login()
        
        run(host='0.0.0.0', port=4800, debug=False, quiet=True)

    def get_ch_list(self, epg=False):
        try:
            ch_list = channel_list(self.session, epg)
        except:
            ch_list = None

        if not ch_list:
            self.session = login()

            if not self.session:
                return
            else:
                ch_list = channel_list(self.session, epg)
        
        return ch_list

    def get_content(self, c_type, c_id):
        try:
            mpd = content_mpd(self.session, c_type, c_id)
        except:
            mpd = None
        
        if not mpd:
            self.session = login()

            if not self.session:
                return
            else:
                mpd = content_mpd(self.session, c_type, c_id)
        
        return mpd

    def get_license(self, c_id, cdm_payload=None):
        return content_license(c_id, cdm_payload)
    def stop_kodi(self):
        # IT'S NOT THE BEST SOLUTION... BUT IT WORKS.
        requests.get("http://localhost:4800")


@route("/api/file/channels.m3u", method="GET")
def m3u():
    response.set_header("Content-Type", "application/m3u8")
    return w.get_ch_list()

@route("/api/file/epg.xml", method="GET")
def epg():
    response.set_header("Content-Type", "application/xml")
    return w.get_ch_list(True)

@route("/api/<content_type>/<content_id>/manifest.mpd", method="GET")
def play_channel(content_type, content_id):
    response.set_header("Content-Type", "application/dash+xml")
    return w.get_content(content_type, content_id)

@route("/api/<content_type>/<content_id>/license", method="POST")
def proxy_license(content_type, content_id):
    response.set_header("Content-Type", "application/octet-stream")
    return w.get_license(content_id, request.body.read())

@route("/key", method="GET")
def auth_key():
    return static_file("key.html", root=__addonpath__)

@route("/auth", method="GET")
def auth_json():
    return static_file("auth.html", root=__addonpath__)

@route("/key", method="POST")
@route("/auth", method="POST")
def auth_key_upload():
    try:
        os.mkdir(__addondir__)
    except:
        pass

    try:
        session = dict()
        f = []

        # KEY FILE
        try:
            f = json.loads(request.files.key.file.read())["data"].split(";")
        except:
            pass
        
        # JSON FILE
        if len(f) == 0:
            try:
                f = [f"{i['name']}={i['value']}" for i in json.loads(request.files.json.file.read())]
            except:
                return f"Unable to read the uploaded file"
        
        messo = None
        for i in f:
            if "personaId" in i:
                session.update({"persona_id": i.split("=")[1]})
            elif "skyCEsidexsso01" in i:
                session.update({"auth_token": i.split("=")[1]})
            elif "deviceid" in i:
                session.update({"device_id": i.split("=")[1]})
            elif "skyCEsidismesso01" in i or ("skyCEsidmesso01" in i and not messo):
                messo = i.split("=")[1]
        
        if not session.get("persona_id") and messo:
            if not session.get("auth_token"):
                xbmcgui.Dialog().notification(__addonname__, f"Error: Missing auth token in cookie file", xbmcgui.NOTIFICATION_ERROR)
                xbmc.log(f"ERROR: Missing auth token in cookie file")
                return "Missing auth token in cookie file"
            
            cc = __addon__.getSetting("platform_id")
            r = requests.Session()
            r.headers = headers
            r,headers.update(cc_headers[cc])
            r.headers.update({'Accept': 'application/json, text/javascript, */*; q=0.01'})
            r.cookies.update({i.split("=")[0]: i.split("=")[1] for i in f})
            persona = r.post(f'{web_url}.{cc_urls[cc]}/bff/personas/v2')
            
            try:
                persona_id = persona.json()['personas'][0]['id']
                session.update({"persona_id": persona_id})
            except Exception as e:
                xbmcgui.Dialog().notification(__addonname__, f"Error: Unable to retrieve persona id: {str(e)} / {str(persona.content)}", xbmcgui.NOTIFICATION_ERROR)
                xbmc.log(f"ERROR: Unable to retrieve persona id: {str(e)} / {str(persona.content)}")
                return "Unable to retrieve persona id"
            
        # SAVE NEW SESSION
        if "persona_id" in session and "auth_token" in session and "device_id" in session:
            try:
                with open(f"{__addondir__}session.json", "w") as f:
                    f.write(json.dumps(session))
            except:
                return "Failed to save session file."
        else:
            return "Failed to retrieve the cookie data."
        
        return "Your cookies have been transmitted to your device. Please restart Kodi."
            
    except Exception as e:
        return f"Invalid file {str(e)}"

@route("/api/<content_id>/playback/<position>", method="POST")
def playback_position(content_id, position):
    w.playback_position(content_id, position)

#
# LOGIN
#

def login():

    # LOAD CACHED SESSION DATA
    try:
        with open(f"{__addondir__}session.json", "r") as f:
            session = json.load(f)
    except:
        xbmc.log("INFO: Failed to read the session file")
        session = {}

    if session.get("user_t_exp"):
        try:
            if datetime(*(time.strptime(session["user_t_exp"].split(".")[0], "%Y-%m-%dT%H:%M:%S")[0:6])).timestamp() >= datetime.now().timestamp() - 300:
                return session
            else:
                xbmc.log("INFO: Session token expired")
                del session["user_t_exp"]
                del session["user_token"]
        except:
            session = {}

    cc = __addon__.getSetting("platform_id")
    r = requests.Session()
    
    # RETRIEVE SESSION DATA
    if session.get("auth_token") and session.get("persona_id") and session.get("device_id"):

        auth_token = session["auth_token"]
        persona_id = session["persona_id"]
        device_id  = session["device_id"]

    else:

        xbmc.log(f"ERROR: Unable to retrieve auth data")
        return

    # RETRIEVE USER TOKEN
    r.headers = {'Accept': 'application/vnd.tokens.v1+json', 'Content-Type': 'application/vnd.tokens.v1+json'}
    url = f'{ovp_url}.{cc_urls[cc]}/auth/throttled/tokens'
    oauth_data = {"auth":{"authScheme":"MESSO","authIssuer":"NOWTV","authToken":auth_token,"personaId":persona_id,"provider":"NOWTV","providerTerritory":cc,"proposition":"NOWOTT"},"device":{"type":"TV","platform":"ANDROIDTV","id":device_id,"drmDeviceId":"UNKNOWN"}}
    
    signature = tools.calculate_signature('POST', url, r.headers, json.dumps(oauth_data))
    r.headers.update({'x-sky-signature': signature})
    
    token = r.post(url, data=json.dumps(oauth_data))
    del r.headers["Content-Type"], r.headers["x-sky-signature"]
    
    try:
        user_token = token.json()['userToken']
    except Exception as e:
        xbmcgui.Dialog().notification(__addonname__,f"Error: Unable to retrieve user token: {str(e)} / {str(token.content)}", xbmcgui.NOTIFICATION_ERROR)        
        xbmc.log(f"ERROR: Unable to retrieve user token: {str(e)} / {str(token.content)}")
        return
    
    session = dict()

    # SETUP SESSION
    session.update({
        "user_token": user_token,    # USER TOKEN
        "user_t_exp": token.json()["recommendedTokenReacquireTime"],  # USER TOKEN EXPIRATION TIME
        "persona_id": persona_id,    # PERSONA ID
        "auth_token": auth_token,    # AUTH TOKEN
        "device_id": device_id       # DEVICE ID
    })

    # SAVE SESSION
    try:
        with open(f"{__addondir__}session.json", "w") as f:
            f.write(json.dumps(session))
    except:
        xbmc.log(f"WARNING: Failed to save session file")
        pass
    
    return session


#
# CHANNEL LIST / EPG
#

def channel_list(session, epg=False):
    cc = __addon__.getSetting("platform_id")
    
    r = requests.Session()
    r.headers = headers
    r.headers.update(cc_headers[cc])
    r.headers.update({"x-skyott-usertoken": session["user_token"]})
    
    # RETRIEVE PACKAGES
    url = f'{ovp_url}.{cc_urls[cc]}/auth/users/me'
    signature = tools.calculate_signature('GET', url, r.headers, "")
    r.headers.update({'x-sky-signature': signature, 'Content-Type': 'application/vnd.userinfo.v2+json', 'Accept': 'application/vnd.userinfo.v2+json'})
    
    me = r.get(url)
    del r.headers["x-skyott-usertoken"], r.headers["x-sky-signature"], r.headers["Content-Type"], r.headers["Accept"]
    
    try:
        packages = ",".join([i["name"] for i in me.json()["segmentation"]["content"]])
    except:
        xbmcgui.Dialog().notification(__addonname__, "Failed to load channel packages", xbmcgui.NOTIFICATION_ERROR)
        return

    # GET SERVICE KEYS
    now  = datetime.now(tz.tzlocal())
    now  = now.replace(minute=0, second=0, microsecond=0)
    date = now.strftime('%Y-%m-%dT%H:%M%z')
    date = date[:-2] + ':' + date[-2:]
    url  = f"{web_url}.{cc_urls[cc]}/bff/channel_guide?startTime={quote(date)}"
    url += '&playout_content_segments={0}&discovery_content_segments={0}'.format(packages)

    r.headers.update({'x-skyott-endorsements': 'videoFormat; caps="UHD",colorSpace; caps="HDR",audioFormat; caps="Stereo"'})
    ch_list = r.get(url)

    output = {"tv": {}} if epg else "#EXTM3U\n" 
    ch = {"channel": []}
    pr = {"programme": []}
    
    try:
        certificate = (
            'Cr4CCAMSEN41PnjoV2GYRkwx+pafn3AYkt/ygAYijgIwggEKAoIBAQDU59zNRn0kxM00V4uLWYqN'
            '47dMLA9i3GDotI+yEJPQ76khlvFPlfevr3n0I9/M4Oiy2ub97y4MGkiB37Btgz5cvKQbVc7iJBlS'
            'LmZ58R8Pebkj6uG/RLtXN+zs/UQn7vDDqKcc2qDKiZO9pkiAK5RhZHCXvIzW4gGGO2HPSCNduSrM'
            '5mDEOWs3L46u1lmf1lOda/T46PiNE5e4OPzcncf8opRyvN2kw34IY6R20fwtQRTnkDdj7gyqOcVt'
            'YfUQ5NNdqhg84OH72y12a0vi1qqrLv/6Frp9HLbqIdHM7zKUmrsrVSlUjjdlrg/YF3lTRy6kn/Jb'
            'jdVZOrganZqecK9nAgMBAAE6DXBlYWNvY2t0di5jb21AAUgBEoADCbIGMPBYtiPuHYg4WPCVgJIt'
            'KgsrIiwO9/GX+0dpYbaRSiq+2rNcybsl0juP+jRGantYOsylf0j2BYFHVEnVkb9mfsW36YlHYBsH'
            'GTNt6IsK7GeV6BiPc0S2s2ll9N8ofU3cqRTzPvGojs5LoQ1HWO9tDrgYLohwFG+2BIimJERdbkSy'
            'nR0NoTZjeBIzTVW8tdDQ+yPZqUtWu3SpDBeksvcDmrTCvQZMZNb3aSh2Q1bKA8/DV7UGMMBtJvjs'
            '5hn2tVNJ+7n6oW878y9ThzqtpMvGnsS8iMit5e/Wzku0KwgHNwjfsNtVCJo1fLsmE9wAs7SOY1ql'
            'UtnCD37Bh0e7v1HYzhwAqLvorqzpRGB7sy97XEzhDllFnUuM57kaS6aPAy04Il35DQKYWWt/FeAp'
            '/hw8CTCX0hhNaWOMp38Tiuj+mSsUmwkq/71R9VsY0EN+k+BDXpaJHIJO9Dk+mm08P0ILWT7/sMJy'
            '225r81jyLmvsth4Kw47T4NqkJlP0/Tvs'
        )

        for chan in ch_list.json()["channels"]:

            if epg:
                ch_id   = chan["serviceKey"]
                ch_name = chan["name"]
                ch_logo = chan["logo"]["Dark"].replace("{width}", "300").replace("{height}", "300")

                ch_part = {"@id": ch_name, "display-name": {"@lang": "de", "#text": ch_name}, "icon": {"@src": ch_logo}}
                ch["channel"].append(ch_part)

                for i in range(0, len(chan["scheduleItems"])):
                    pr_start = datetime.fromtimestamp(float(chan["scheduleItems"][i]["startTimeUTC"]), timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                    pr_stop  = datetime.fromtimestamp(float(chan["scheduleItems"][i]["startTimeUTC"] + chan["scheduleItems"][i]["durationSeconds"]), timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                    pr_title = chan["scheduleItems"][i]["data"]["title"]
                    pr_genre = "Magazines / Reports / Documentary" if ch_id in ["13","112","113","118","130","402"] \
                        else "Sports" if "SPORTS" in packages or "Sport" in ch_name \
                        else "Movie / Drama" if "ENTERTAINMENT" in packages or "CINEMA" in packages \
                        else "Children's / Youth programs" if "KIDS" in packages \
                        else None
                    pr_desc  = chan["scheduleItems"][i]["data"].get("description")
                    pr_image = chan["scheduleItems"][i]["data"].get("images", {"16-9": None}).get("16-9")
                    pr_sr_no = chan["scheduleItems"][i]["data"].get("seasonNumber")
                    pr_ep_no = chan["scheduleItems"][i]["data"].get("episodeNumber")
                    pr_fsk   = chan["scheduleItems"][i]["data"].get("ageRating", {"display": None}).get("display")

                    prg = {
                        "@start": pr_start, 
                        "@stop": pr_stop, 
                        "@channel": ch_name,
                        "title": pr_title
                    }

                    if pr_desc:
                        prg["desc"] = {"@lang": "de", "#text": pr_desc}
                    if pr_image:
                        prg["icon"] = {"@src": pr_image}
                    if pr_sr_no and pr_ep_no:
                        prg["episode-num"] = {"@system": "xmltv_ns", "#text": f"{int(pr_sr_no) - 1} . {int(pr_ep_no) - 1} . "}
                    if pr_fsk:
                        prg["rating"] = {"@system": "FSK", "value": {"#text": str(pr_fsk)}}
                    if pr_genre:
                        prg["category"] = [{"@lang": "en", "#text": pr_genre}]
                    
                    pr["programme"].append(prg)

            else:

                output = \
                    f'{output}' \
                    f'#KODIPROP:inputstreamclass=inputstream.adaptive\n' \
                    f'#KODIPROP:inputstream.adaptive.manifest_type=mpd\n' \
                    f'#KODIPROP:inputstream.adaptive.license_type=com.widevine.alpha\n' \
                    f'#KODIPROP:inputstream.adaptive.server_certificate={certificate}\n' \
                    f'#KODIPROP:inputstream.adaptive.license_key=http://localhost:4800/api/live/{chan["serviceKey"]}/license||R' + '{SSM}|\n' \
                    f'#EXTINF:0001 tvg-id="{chan["name"]}" tvg-logo="{chan["logo"]["Dark"].replace("{width}", "300").replace("{height}", "300")}", {chan["name"]}\n' \
                    f'http://localhost:4800/api/live/{chan["serviceKey"]}/manifest.mpd\n'
        
        if epg:
            output["tv"]["channel"] = ch["channel"]
            output["tv"]["programme"] = pr["programme"]
        
        return xmltodict.unparse(output, pretty=True, encoding="UTF-8", full_document=True) if epg else output
    
    except Exception as e:
        xbmcgui.Dialog().notification(__addonname__, f"Failed to create the channel list / EPG file: {str(e)}", xbmcgui.NOTIFICATION_ERROR)
        return


#
# CHANNEL/VOD MPD
#

def content_mpd(session, c_type, c_id):
    cc = __addon__.getSetting("platform_id")

    if release_pids.get(c_id, {"exp": 0})["exp"] <= int(datetime.now().timestamp()):

        hd_enabled = True if __addon__.getSetting("hd_enabled") == "true" else False

        r = requests.Session()
        r.headers = headers
        r.headers.update(cc_headers[cc])

        r.headers.update({"x-skyott-usertoken": session["user_token"], 'x-skyott-pinoverride': 'true', 'Content-Type': f'application/vnd.play{c_type}.v1+json'})

        data = {
            "device": {
            "capabilities": [
                {
                "transport": "DASH",
                "protection": "WIDEVINE",
                "vcodec": "H264",
                "acodec": "AAC",
                "container": "TS"
                },
                {
                "transport": "DASH",
                "protection": "WIDEVINE",
                "vcodec": "H264",
                "acodec": "AAC",
                "container": "ISOBMFF"
                }           
            ],
            "maxVideoFormat": "HD",
            "model": "Pixel",
            "hdcpEnabled": "false",
            "supportedColourSpaces": ["SDR"]
        },
        "client": {
            "thirdParties": ["FREEWHEEL"]
        },
        "parentalControlPin": "null",
        "personaParentalControlRating": "19"
        }

        if c_type == "live":
            data["serviceKey"] = c_id

        if hd_enabled:
            data["device"]["maxVideoFormat"] = "UHD"

        url = f'{ovp_url}.{cc_urls[cc]}/video/playouts/{c_type}'
        signature = tools.calculate_signature('POST', url, headers, json.dumps(data))
        r.headers.update({'x-sky-signature': signature})

        ch = r.post(url, json=data)

        try:
            mpd_url = ch.json()['asset']['endpoints'][0]['url'].split("?")[0]
            wv_url = ch.json()['protection']['licenceAcquisitionUrl']
            track_url = ch.json()['events']['heartbeat']['url']
            exp = int(datetime.now().timestamp()) + 300

        except Exception as e:
            if "necessary role" in str(ch.content):
                xbmcgui.Dialog().notification(__addonname__, f"Missing subscription for the requested content", xbmcgui.NOTIFICATION_ERROR)
            else:
                xbmcgui.Dialog().notification(__addonname__, f"Failed to load the playlist: {str(e)} / {str(ch.content)}", xbmcgui.NOTIFICATION_ERROR)
            return

    else:
        mpd_url = release_pids[c_id]["mpd"]
        wv_url = release_pids[c_id]["wv"]
        track_url = release_pids[c_id]["track"]
        exp = release_pids[c_id]["exp"]

    mpd = requests.get(mpd_url)
    xml = xmltodict.parse(mpd.content)

    if c_type == "live":
        if type(xml["MPD"]["Period"]) == list:
            for i in xml["MPD"]["Period"]:
                i["BaseURL"] = f"{mpd_url.split('/master')[0]}/" 
        else:        
            xml["MPD"]["Period"]["BaseURL"] = f"{mpd_url.split('/master')[0]}/"

    release_pids[c_id] = {"wv": wv_url, "mpd": mpd_url, "track": track_url, "exp": exp}

    return xmltodict.unparse(xml, pretty=True)


#
# CHANNEL/VOD LICENSE
#

def content_license(c_id, cdm_payload):
    x = 10
    while True:
        if release_pids.get(c_id):
            lic_headers = {'User-Agent': headers["user-agent"], 'Content-Type': 'application/octet-stream'}
            cdm_request = requests.post(release_pids[c_id]["wv"], headers=lic_headers, data=cdm_payload)
            try:
                j = json.loads(cdm_request.content)
                if j.get("description"):
                    xbmc.log(f"WV API ERROR: {j.get('errorCode', 'ERROR')}: {j['description']}")
            except:
                pass
            return cdm_request.content
        else:
            x = x - 1
        if x == 0:
            break
        time.sleep(0.3)
    xbmc.log(f"No license url found for content id {c_id}.")
    return


#
# MAIN PROCESS
#

def start():
    
    t = WebServer()

    # START SERVER (+ STOP SERVER BEFORE CLOSING KODI)
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
    t.stop_kodi()


if __name__ == "__main__":
    start()
