import json
import re
from urllib.parse import urlsplit,urlunsplit

from aiohttp import ClientSession,ClientTimeout


async def forward_room_call(cfg,method,payload=None):
    payload=payload or {}
    fields={'room_id','session_id','request_id','source_extension','target_node_id','target_user_id','caller_user_id','caller_user_name','source_auto_mode','timeout_sec'}
    if method=='POST':
        if set(payload)-fields or payload.get('target_node_id')!=cfg.node_id:
            return {'error':'Choose this site and supported room fields'},400
        if not all(isinstance(payload.get(key),str) and 0<len(payload[key])<=128 for key in fields-{'timeout_sec','caller_user_name'}):
            return {'error':'Room, request and participant identities are required'},400
        if not re.fullmatch(r'[0-9]{1,12}',payload['source_extension']) or payload['source_auto_mode'] not in ('off','answer','speaker') or type(payload.get('timeout_sec')) is not int or not 5<=payload['timeout_sec']<=120:
            return {'error':'Choose a valid SIP extension, answer mode and timeout'},400
    elif method!='GET':
        return {'error':'Method not allowed'},405
    parts=urlsplit(cfg.server_url)
    if parts.scheme not in ('ws','wss','http','https') or not parts.netloc:
        return {'error':'The VPS address is not configured'},503
    url=urlunsplit(('https' if parts.scheme in ('wss','https') else 'http',parts.netloc,'/node/room-calls','',''))
    headers={'X-Simson-Account-ID':cfg.account_id,'X-Simson-Node-ID':cfg.node_id,'X-Simson-Install-Token':cfg.install_token}
    try:
        async with ClientSession(timeout=ClientTimeout(total=12,connect=3)) as session:
            async with session.request(method,url,json=payload if method=='POST' else None,headers=headers) as response:
                raw=await response.content.read(16385)
                try:data=json.loads(raw) if len(raw)<=16384 else None
                except (ValueError,UnicodeError):data=None
                if not isinstance(data,dict):
                    return {'error':'Room SIP service returned an invalid response; check current calls before retrying'},502
                if response.status>=400:
                    return {'error':str(data.get('error') or 'Room SIP service is unavailable')[:500],**({'call_id':data['call_id']} if isinstance(data.get('call_id'),str) else {})},response.status
                return data,response.status
    except Exception:
        return {'error':'Room SIP request timed out or could not connect; its result may be uncertain. Check room status before retrying.','code':'room_create_uncertain' if method=='POST' else 'room_capability_unavailable'},504
