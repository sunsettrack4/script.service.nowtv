from bottle import request, response, route, run, static_file
from datetime import datetime, timezone
from resources.lib import tools
from urllib.parse import quote
import json, random, requests, string, time, urllib, xbmc, xbmcaddon, xbmcgui, xbmcvfs, xmltodict


release_pids = {}

### NOW PARAMS
    
headers = {
    "x-skyott-device": "TV",
    "x-skyott-language": "de",
    "x-skyott-platform": "ANDROIDTV",
    "x-skyott-proposition": "NOWTV",
    "x-skyott-provider": "NOWTV",
    "x-skyott-territory": "DE",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    'sec-ch-ua-platform': '"Windows"',
    "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    "sec-ch-ua-Mobile": "?0"
}

ui_url = "http://rango.id.wowtv.de"
persona_url = "https://persona-store.sky.com"
auth_url = "https://auth.client.ott.sky.com"
p_url = "https://p.sky.com"
graph_url = "https://graphql.ott.sky.com"

live_hash = "356b08a537f119347994744194e5c42f61fba5ccf5ffbd31bd25af626a2043b5"
watchlist_hash = "bf69938e7d2b6e17aeb4aeb438253b0afbfae04454447ee0143373abd93f04da"
continue_hash = "bf69938e7d2b6e17aeb4aeb438253b0afbfae04454447ee0143373abd93f04da"


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
    
    def get_watchlist(self):
        try:
            watchlist = personalized_content(self.session, "watchlist")
        except:
            watchlist = None

        if not watchlist:
            self.session = login()

            if not self.session:
                return
            else:
                watchlist = personalized_content(self.session, "watchlist")
        
        return watchlist

    def get_continue(self):
        try:
            continue_watching = personalized_content(self.session, "continue")
        except:
            continue_watching = None

        if not continue_watching:
            self.session = login()

            if not self.session:
                return
            else:
                continue_watching = personalized_content(self.session, "continue")
        
        return continue_watching

    def playback_position(self, c_id, position):
        if release_pids.get(c_id, {}).get("track") is None:
            return

        tracked = track_playback_position(self.session, release_pids[c_id]["track"], int(position))
        if not tracked:
            self.session = login()

            if not self.session:
                return
            else:
                track_playback_position(self.session, release_pids[c_id]["track"], int(position))

    def stop_kodi(self):
        # IT'S NOT THE BEST SOLUTION... BUT IT WORKS.
        requests.get("http://localhost:4800")


@route("/api/file/status.json", method="GET")
def status():
    response.set_header("Content-Type", "application/json")
    return json.dumps({"territory": __addon__.getSetting("platform_id")})

@route("/api/file/channels.m3u", method="GET")
def m3u():
    response.set_header("Content-Type", "application/m3u8")
    return w.get_ch_list()

@route("/api/file/epg.xml", method="GET")
def epg():
    response.set_header("Content-Type", "application/xml")
    return w.get_ch_list(True)

@route("/api/file/watchlist.json", method="GET")
def watchlist():
    response.set_header("Content-Type", "application/json")
    return w.get_watchlist()

@route("/api/file/continue.json", method="GET")
def continue_watching():
    response.set_header("Content-Type", "application/json")
    return w.get_continue()

@route("/api/<content_type>/<content_id>/manifest.mpd", method="GET")
def play_channel(content_type, content_id):
    response.set_header("Content-Type", "application/dash+xml")
    return w.get_content(content_type, content_id)

@route("/api/<content_type>/<content_id>/license", method="POST")
def proxy_license(content_type, content_id):
    response.set_header("Content-Type", "application/octet-stream")
    return w.get_license(content_id, request.body.read())

@route("/api/<content_type>/<content_id>/license", method="GET")
def proxy_license(content_type, content_id):
    response.set_header("Content-Type", "text")
    return w.get_license(content_id)

@route("/auth", method="GET")
def auth_get():
    q = dict(request.query.decode())

    if all(i in q for i in ("auth_token", "persona_id", "device_id")):
        session = dict()

        # SETUP NEW SESSION
        session.update({
            "persona_id": q["persona_id"],    # PERSONA ID
            "auth_token": q["auth_token"],    # AUTH TOKEN
            "device_id": q["device_id"]       # DEVICE ID
        })

        # SAVE NEW SESSION
        try:
            with open(f"{__addondir__}session.json", "w") as f:
                f.write(json.dumps(session))
        except:
            xbmc.log(f"WARNING: Failed to save session file")
            pass
        
        return "Your cookies have been transmitted to your device. Please restart Kodi."
    else:
        return static_file("input.html", root=__addonpath__)

@route("/key", method="GET")
def auth_key():
    return static_file("key.html", root=__addonpath__)

@route("/key", method="POST")
def auth_key_upload():
    try:
        session = dict()
        messo = None

        f = json.loads(request.files.key.file.read())["data"].split(";")
        
        for i in f:
            if "personaId" in i:
                session.update({"persona_id": i.split("=")[1]})
            elif "skyCEsidexsso01" in i:
                session.update({"auth_token": i.split("=")[1]})
            elif "deviceid" in i:
                session.update({"device_id": i.split("=")[1]})
            elif "skyCEsidismesso01" in i:
                messo = i.split("=")[1]
        
        if not session.get("persona_id") and messo:
            r = requests.Session()
            r.headers = headers
            r.headers.update({"x-skyott-territory": __addon__.getSetting("platform_id")})
            r.headers.update({
                'X-Skyid-Token': messo,
                'X-Skyott-Tokentype': 'MESSO',
                "Accept": "application/vnd.persona.v1+json"
            })

            persona = r.get(f'{persona_url}/persona-store/personas')
            
            try:
                session.update({"persona_id": persona.json()['personas'][0]['personaId']})
            except Exception:
               return "Failed to obtain the personaId."
            
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

    __username = __addon__.getSetting("username")
    __password = __addon__.getSetting("password")
    cc = __addon__.getSetting("platform_id")

    if not __username or not __password:
        xbmcgui.Dialog().notification(__addonname__, "Please add your credentials in add-on settings.", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log("ERROR: Please add your credentials in add-on settings.")
        return

    # RETRIEVE SESSION DATA
    r = requests.Session()
    r.headers = headers
    r.headers.update({"x-skyott-territory": cc})

    if session.get("auth_token") and session.get("persona_id") and session.get("device_id"):

        auth_token = session["auth_token"]
        persona_id = session["persona_id"]
        device_id  = session["device_id"]

    else:

        data = {"rememberMe": True, "userIdentifier": __username, "password": __password}

        account = r.post(f"{ui_url}/signin/service/international", data=data)

        if account.status_code == 422:
            xbmcgui.Dialog().notification(__addonname__, "Error: Authentication failure - invalid credentials", xbmcgui.NOTIFICATION_ERROR)
            xbmc.log("ERROR: Authentication failure - invalid credentials")
            return
        elif account.status_code == 403:
            xbmcgui.Dialog().notification(__addonname__, "Error: Resource unavailable, please check your IP address.", xbmcgui.NOTIFICATION_ERROR)
            xbmc.log("ERROR: Resource unavailable, please check your IP address.")
            return

        try:
            device_uuid = account.json()["properties"]["data"]["deviceid"]

            cookies = r.cookies.get_dict()
            token_temp = cookies['skySSO']
            x_sky_id_token = cookies['skyCEsidismesso01']
            auth_token = cookies['skyCEsidexsso01']
        except Exception as e:
            if "289" in str(account.content):
                xbmcgui.Dialog().notification(__addonname__, f"Error: Login failed - captcha challenge is required", xbmcgui.NOTIFICATION_ERROR)
                xbmc.log(f"ERROR: Login failed - captcha challenge is required")
            else:
                xbmcgui.Dialog().notification(__addonname__, f"Error: Unable to retrieve device id/cookie values: {str(e)} / {str(account.content)}", xbmcgui.NOTIFICATION_ERROR)
                xbmc.log(f"ERROR: Unable to retrieve device id/cookie values: {str(e)} / {str(account.content)}")
            return

        # RETRIEVE PERSONA ID
        r.headers.update({
            'X-Skyid-Token': x_sky_id_token,
            'X-Skyott-Tokentype': 'MESSO',
            "Accept": "application/vnd.persona.v1+json"
        })

        persona = r.get(f'{persona_url}/persona-store/personas')
        del r.headers["Accept"], r.headers["X-Skyott-Tokentype"], r.headers["X-Skyid-Token"]
        
        try:
            persona_id = persona.json()['personas'][0]['personaId']
        except Exception as e:
            xbmcgui.Dialog().notification(__addonname__, f"Error: Unable to retrieve persona id: {str(e)} / {str(persona.content)}", xbmcgui.NOTIFICATION_ERROR)
            xbmc.log(f"ERROR: Unable to retrieve persona id: {str(e)} / {str(persona.content)}")
            return
        
        device_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

    # RETRIEVE USER TOKEN
    messo_data = {"auth":{"authScheme":"MESSO","authIssuer":"NOWTV","provider":"NOWTV","providerTerritory":cc,"proposition":"NOWTV","authToken":auth_token,"personaId":persona_id},"device":{"type":"TV","platform":"ANDROIDTV","id":device_id,"drmDeviceId":"UNKNOWN"}}
    
    signature = tools.calculate_signature('POST', f'{p_url}/auth/tokens', r.headers, json.dumps(messo_data))
    r.headers.update({'x-sky-signature': signature, 'Content-Type': 'application/vnd.tokens.v1+json'})
    
    token = r.post(f'{p_url}/auth/tokens', data=json.dumps(messo_data))
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
    sections = []
    
    r = requests.Session()
    r.headers = headers
    r.headers.update({"x-skyott-usertoken": session["user_token"]})
    
    # RETRIEVE PACKAGES
    signature = tools.calculate_signature('GET', f'{p_url}/auth/users/me', r.headers, "")
    r.headers.update({'x-sky-signature': signature, 'Content-Type': 'application/vnd.userinfo.v2+json', 'Accept': 'application/vnd.userinfo.v2+json'})
    
    me = r.get(f"{p_url}/auth/users/me")
    del r.headers["x-skyott-usertoken"], r.headers["x-sky-signature"], r.headers["Content-Type"], r.headers["Accept"]
    
    try:
        packages = [i["name"] for i in me.json()["segmentation"]["content"]]
    except:
        xbmcgui.Dialog().notification(__addonname__, "Failed to load channel packages", xbmcgui.NOTIFICATION_ERROR)
        return
    
    if "MOVIES" in packages:
        sections.append("CINEMA")
    if "ENTERTAINMENT" in packages:
        sections.extend(["ENTERTAINMENT", "KIDS"])
    if "SPORTS" in packages:
        sections.append("SPORT")

    # GET SERVICE KEYS
    extensions = '{"persistedQuery":{"version":1,"sha256Hash":"'+live_hash+'"}}'
    
    cc = __addon__.getSetting("platform_id")
    lang = "de" if cc == "DE" else "" if cc == "IT" else "en"
    r.headers.update({'x-skyott-language': lang})

    output = {"tv": {}} if epg else "#EXTM3U\n" 
    ch = {"channel": []}
    pr = {"programme": []}
    
    try:
        for package in sections:
            variables  = '{"sectionNavigation":"'+package+'","formatType":null,"defaultFormat":"HD"}'
            url = f'{graph_url}/graphql?extensions={quote(extensions)}&variables={quote(variables)}'

            ch_list = r.get(url)
            
            for chan in ch_list.json()["data"]["linearChannels"]:

                if epg:
                    ch_id   = chan["serviceKey"]
                    ch_name = chan["name"].replace(" SD", "")
                    ch_logo = chan["logos"][0]["template"].replace("light", "dark").replace("{width}", "300").replace("{height}", "300")

                    ch_part = {"@id": ch_name, "display-name": {"@lang": "de", "#text": ch_name}, "icon": {"@src": ch_logo}}
                    ch["channel"].append(ch_part)

                    for i in ["now", "next"]:
                        pr_start = datetime.fromtimestamp(float(chan[i]["startTimeEpoch"]), timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                        pr_stop  = datetime.fromtimestamp(float(chan[i]["startTimeEpoch"] + chan[i]["durationInSeconds"]), timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                        pr_title = chan[i]["title"]
                        pr_genre = "Magazines / Reports / Documentary" if ch_id in ["13","112","113","118","130","402"] \
                            else "Sports" if package == "SPORTS" or "Sport" in ch_name \
                            else "Movie / Drama" if package in ["ENTERTAINMENT", "CINEMA"] \
                            else "Children's / Youth programs" if package == "KIDS" \
                            else None
                        pr_desc  = chan[i].get("synopsis")
                        pr_image = chan[i].get("imageUrl")
                        pr_sr_no = chan[i].get("seasonNumber")
                        pr_ep_no = chan[i].get("episodeNumber")
                        pr_fsk   = chan[i].get("ottCertificate")

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

                    if not xbmc.getCondVisibility('system.platform.android'):

                        output = \
                            f'{output}' \
                            f'#KODIPROP:inputstreamclass=inputstream.adaptive\n' \
                            f'#KODIPROP:inputstream.adaptive.manifest_type=mpd\n' \
                            f'#EXTINF:0001 tvg-id="{chan["name"].replace(" SD", "")}" tvg-logo="{chan["logos"][0]["template"].replace("light", "dark").replace("{width}", "300").replace("{height}", "300")}", {chan["name"].replace(" SD", "")}\n' \
                            f'plugin://plugin.video.nowtv/?type=live&location={chan["serviceKey"]}\n'

                    else:

                        output = \
                            f'{output}' \
                            f'#KODIPROP:inputstreamclass=inputstream.adaptive\n' \
                            f'#KODIPROP:inputstream.adaptive.manifest_type=mpd\n' \
                            f'#KODIPROP:inputstream.adaptive.license_type=com.widevine.alpha\n' \
                            f'#KODIPROP:inputstream.adaptive.license_key=http://localhost:4800/api/live/{chan["serviceKey"]}/license||R' + '{SSM}|\n' \
                            f'#EXTINF:0001 tvg-id="{chan["name"].replace(" SD", "")}" tvg-logo="{chan["logos"][0]["template"].replace("light", "dark").replace("{width}", "300").replace("{height}", "300")}", {chan["name"].replace(" SD", "")}\n' \
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

    if release_pids.get(c_id, {"exp": 0})["exp"] <= int(datetime.now().timestamp()):

        dolby_enabled = True if __addon__.getSetting("dolby_enabled") == "true" else False
        hd_enabled = True if __addon__.getSetting("hd_enabled") == "true" else False

        r = requests.Session()
        r.headers = headers
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
            "model": "PC",
            "hdcpEnabled": "false",
            "supportedColourSpaces": []
        },
        "client": {
            "thirdParties": []
        },
        "parentalControlPin": None
        }

        if c_type == "live":
            data["serviceKey"] = c_id
        elif c_type == "vod":
            data["contentId"] = c_id
            data["providerVariantId"] = c_id

        if dolby_enabled:
            data["device"]["capabilities"].extend([
                {
                "transport": "DASH",
                "protection": "WIDEVINE",
                "vcodec": "H264",
                "acodec": "EAC",
                "container": "TS"
                },
                {
                "transport": "DASH",
                "protection": "WIDEVINE",
                "vcodec": "H264",
                "acodec": "EAC",
                "container": "ISOBMFF"
                }  
            ])

        if hd_enabled:
            data["device"]["maxVideoFormat"] = "UHD"

        signature = tools.calculate_signature('POST', f'{p_url}/video/playouts/{c_type}', headers, json.dumps(data))
        r.headers.update({'x-sky-signature': signature})

        ch = r.post(f'{p_url}/video/playouts/{c_type}', json=data)

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
                i["BaseURL"] = f"{mpd_url.split('/index')[0]}/" 
        else:        
            xml["MPD"]["Period"]["BaseURL"] = f"{mpd_url.split('/index')[0]}/" 
    elif c_type == "vod":
        xml["MPD"]["Period"]["BaseURL"] = f"{mpd_url.split('/manifest')[0]}/"

    release_pids[c_id] = {"wv": wv_url, "mpd": mpd_url, "track": track_url, "exp": exp}

    return xmltodict.unparse(xml, pretty=True)


#
# CHANNEL/VOD LICENSE
#

def content_license(c_id, cdm_payload):
    if not cdm_payload:
       try:
            d = tools.get_cdm_keys(release_pids[c_id]["mpd"], release_pids[c_id]["wv"].split('|')[0], headers["user-agent"])
            return d['key']
       except:
           xbmcgui.Dialog().notification(__addonname__, f"Failed to load the license: {str(d['error'])}", xbmcgui.NOTIFICATION_ERROR)
           return

    x = 10
    while True:
        if release_pids.get(c_id):
            try:
                signature = tools.calculate_signature('POST', release_pids[c_id]["wv"], {}, cdm_payload)
                drm_headers = {'x-sky-signature': signature}
                cdm_request = requests.post(release_pids[c_id]["wv"], headers=drm_headers, data=cdm_payload)
                try:
                    j = json.loads(cdm_request.content)
                    if j.get("description"):
                        raise Exception(f"{j.get('errorCode', 'ERROR')}: {j['description']}")
                except:
                    pass
                return cdm_request.content
            except Exception as e:
                if "Robustness" in str(e):
                    xbmcgui.Dialog().notification(__addonname__, f"Unfortunately, your device does not support HD streams. Please disable the HD streams in add-on settings.", xbmcgui.NOTIFICATION_ERROR)
                    return
                elif "Unsupported" in str(e):
                    xbmcgui.Dialog().notification(__addonname__, f"Unfortunately, WOW does not support your device.", xbmcgui.NOTIFICATION_ERROR)
                    return
                else:
                    xbmcgui.Dialog().notification(__addonname__, f"Failed to load the wv license: {str(e)}", xbmcgui.NOTIFICATION_ERROR)
                    return
        else:
            x = x - 1
        if x == 0:
            break
        time.sleep(0.3)
    xbmcgui.Dialog().notification(__addonname__, f"No license url found for content id {c_id}.", xbmcgui.NOTIFICATION_ERROR)
    return


#
# PERSONALIZED - WATCHLIST/CONTINUE WATCHING
#

def personalized_content(session, p_type="watchlist"):

    getWatchlist = "true" if p_type == "watchlist" else "false"
    getContinueWatching = "true" if p_type == "continue" else "false"
    sha256Hash = watchlist_hash if p_type == "watchlist" else continue_hash

    extensions = '{"persistedQuery":{"version":1,"sha256Hash":"'+sha256Hash+'"}}'
    variables  = '{"fullWidthHeroImages":false,"getContinueWatching":'+getContinueWatching+',"getWatchlist":'+getWatchlist+',"getFavourites":false,"getBecauseYouWatched":false,"getPersonalisedGenres":false}'
    
    url = f"{graph_url}/personalised?extensions={quote(extensions)}&variables={quote(variables)}"
    
    r = requests.Session()
    r.headers = headers
    r.headers.update({"x-skyott-usertoken": session["user_token"]})

    me = r.get(url)
    del r.headers["x-skyott-usertoken"]

    try:
        return me.json()
    except Exception as e:
        xbmcgui.Dialog().notification(__addonname__, f"Failed to load personalized content: {str(e)}", xbmcgui.NOTIFICATION_ERROR)
        return

#
# TRACK PLAYBACK POSITION
#
def track_playback_position(session, url, position):

    data = {"streamPosition": position}

    r = requests.Session()
    r.headers = headers
    r.headers.update({"x-skyott-usertoken": session["user_token"]})
    r.headers.update({"Content-Type": "application/vnd.stopstream.v1+json"})
    signature = tools.calculate_signature('PUT', url, headers, json.dumps(data))
    r.headers.update({'x-sky-signature': signature})

    res = r.put(url, json=data)
    del r.headers["x-skyott-usertoken"], r.headers["Content-Type"], r.headers["x-sky-signature"]

    if res.status_code == 204:
        return True
    else:
        return False

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
