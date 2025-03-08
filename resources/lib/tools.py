from urllib.parse import urlparse
import base64
import hashlib
import hmac
import json
import requests
import sys
import time
import xmltodict


def calculate_signature(method, url, headers, payload, timestamp=None):
        
    app_id = 'IE-NOWTV-ANDROID-v1'
    signature_key = bytearray('5f8RLBppaqKGO8bwKwNifjZ6bM8zXCVwkAK7hkhq3PS4pf', 'utf-8')
    sig_version = '1.0'

    if not timestamp:
        timestamp = int(time.time())

    if url.startswith('http'):
        parsed_url = urlparse(url)
        path = parsed_url.path
    else:
        path = url

    text_headers = ''

    for key in sorted(headers.keys()):
        if key.lower().startswith('x-skyott'):
            text_headers += key + ': ' + headers[key] + '\n'
    
    headers_md5 = hashlib.md5(text_headers.encode()).hexdigest()

    if sys.version_info[0] > 2 and isinstance(payload, str):
        payload = payload.encode('utf-8')

    payload_md5 = hashlib.md5(payload).hexdigest()

    to_hash = ('{method}\n{path}\n{response_code}\n{app_id}\n{version}\n{headers_md5}\n'
            '{timestamp}\n{payload_md5}\n').format(method=method, path=path,
                response_code='', app_id=app_id, version=sig_version,
                headers_md5=headers_md5, timestamp=timestamp, payload_md5=payload_md5)

    hashed = hmac.new(signature_key, to_hash.encode('utf-8'), hashlib.sha1).digest()
    signature = base64.b64encode(hashed).decode('utf-8')
    
    return 'SkyOTT client="{}",signature="{}",timestamp="{}",version="{}"'.format(app_id, signature, timestamp, sig_version)

def get_pssh(url, ua):

    r = requests.Session()
    r.headers.update({"user-agent": ua})
    mpd_page = r.get(url)
    mpd_file = xmltodict.parse(mpd_page.content, dict_constructor=dict)
    
    pssh = None
    
    for i in mpd_file["MPD"]["Period"]["AdaptationSet"]:
        if i.get("ContentProtection"):
            for j in i["ContentProtection"]:
                if j["@schemeIdUri"] == "urn:uuid:EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED" or \
                        j["@schemeIdUri"] == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
                    if type(j["cenc:pssh"]) == dict:
                        pssh = j["cenc:pssh"]["#text"]
                    else:
                        pssh = j["cenc:pssh"]

    return pssh

def get_key(pssh, license_url, ua):

    r = requests.Session()
    r.headers.update({'user-agent': ua})
    data = {"license_url": license_url, "pssh": pssh}

    json_str = json.dumps(data)
    base64_bytes = base64.b64encode(json_str.encode('utf-8'))
    base64_str = base64_bytes.decode('utf-8')

    key_url = f'https://www.deliciasoft.com/sky.php?q={base64_str}'
    key_page = r.get(key_url)

    return key_page.json().get("keys")

def get_cdm_keys(manifest_url, license_url, user_agent):

    d = dict()
    pssh = get_pssh(manifest_url, user_agent)

    if pssh:
        try:
            key = get_key(pssh, license_url, user_agent)
            d['key'] = key
        except Exception as e:
            d['error'] = str(e)
    else:
        d['error'] = 'PSSH not found'
    return d