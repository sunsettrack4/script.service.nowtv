from urllib.parse import urlparse
import base64
import hashlib
import hmac
import sys
import time


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
