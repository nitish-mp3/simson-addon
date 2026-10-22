import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import web
from unittest.mock import AsyncMock,Mock,patch

sys.path.insert(0,str(Path(__file__).parents[1]/'app'))


@pytest.mark.asyncio
async def test_room_proxy_preserves_identity_and_does_not_retry_conflicts_or_html():
    from room_calls import forward_room_call
    received=[]
    async def upstream(request):
        received.append((request.headers.get('X-Simson-Install-Token'),await request.json()))
        if len(received)==1:
            return web.json_response({'call_id':'one','session_id':'room-one','sip_bridge_id':'bridge-one'},status=202)
        if len(received)==2:return web.json_response({'error':'phone busy'},status=409)
        return web.Response(text='<html>private proxy details</html>',status=502,content_type='text/html')
    app=web.Application();app.router.add_post('/node/room-calls',upstream)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    cfg=SimpleNamespace(server_url='ws://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])+'/ws',node_id='node',account_id='site',install_token='test-secret')
    payload={'room_id':'living','session_id':'room-one','request_id':'press-one','source_extension':'1040','target_node_id':'node','target_user_id':'pika','caller_user_id':'resident','caller_user_name':'Living room','source_auto_mode':'speaker','timeout_sec':30}
    try:
        data,status=await forward_room_call(cfg,'POST',payload)
        assert status==202 and data['call_id']=='one'
        assert received==[('test-secret',payload)]
        data,status=await forward_room_call(cfg,'POST',payload)
        assert status==409 and data['error']=='phone busy' and len(received)==2
        data,status=await forward_room_call(cfg,'POST',payload)
        assert status==502 and 'private proxy' not in data['error'] and len(received)==3
    finally:await runner.cleanup()


@pytest.mark.asyncio
async def test_room_proxy_rejects_other_node_and_unknown_fields_without_http():
    from room_calls import forward_room_call
    cfg=SimpleNamespace(node_id='node')
    for payload in [{'target_node_id':'other'},{'target_node_id':'node','bridge_id':'other-call'}]:
        data,status=await forward_room_call(cfg,'POST',payload)
        assert status==400


def test_real_call_serializer_preserves_only_safe_native_room_binding():
    import importlib.util
    from call_manager import CallInfo,CallState
    from local_api import _call_to_dict
    metadata={'room_id':'living','room_session_id':'session','room_request_id':'press',
        'source_extension':'1040','media_mode':'sip_room','room_audio_mode':'sip',
        'target_user_id':'caregiver','secret':'never-expose','stream_url':'rtsp://private'}
    call=CallInfo(call_id='one',remote_node_id='sip:1040',call_type='sip',state=CallState.ACTIVE,
        caller_user_id='resident',metadata=metadata)
    serialized=_call_to_dict(call)
    assert serialized['metadata']=={key:metadata[key] for key in ('room_id','room_session_id','room_request_id','source_extension','media_mode','room_audio_mode')}
    source=Path(__file__).parents[2]/'integration/custom_components/simson/rooms.py'
    spec=importlib.util.spec_from_file_location('native_room_contract',source)
    rooms=importlib.util.module_from_spec(spec);spec.loader.exec_module(rooms)
    profile={'audio_mode':'sip','video_mode':'ha_camera','room_user_id':'resident','sip_extension':'1040'}
    assert rooms.owns_native_room_call(profile,{'session_id':'session','target_user_id':'caregiver'},serialized)


@pytest.mark.asyncio
async def test_native_room_invite_never_starts_gateway_fallback_or_local_asterisk():
    from main import SimsonAddon
    from call_manager import CallManager
    with patch.object(CallManager,'_load_history'):
        manager=CallManager('node')
    addon=SimsonAddon.__new__(SimsonAddon)
    addon.cfg=SimpleNamespace(node_id='node')
    addon.call_mgr=manager;addon._recent_invite_sources={}
    addon.ha=SimpleNamespace(fire_event=AsyncMock(),create_notification=AsyncMock())
    addon.api=SimpleNamespace(push_sse_event=Mock())
    addon._emit_call_event=AsyncMock();addon._start_ring_timer=Mock();addon._schedule_incoming_sip_route=Mock()
    addon.asterisk=SimpleNamespace(connected=True,originate_call=AsyncMock())
    await addon._handle_invite({'call_id':'one','from_node_id':'sip:1040','call_type':'sip',
        'metadata':{'media_mode':'sip_room','sip_bridge_id':'bridge-one','target_user_id':'caregiver','caller_user_id':'resident'}})
    addon._start_ring_timer.assert_called_once()
    addon._schedule_incoming_sip_route.assert_not_called()
    addon.asterisk.originate_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_room_cannot_be_forwarded_even_by_an_old_scheduled_timer():
    import asyncio
    from main import SimsonAddon
    from call_manager import CallInfo,CallState
    call=CallInfo(call_id='one',remote_node_id='sip:1040',call_type='sip',state=CallState.INCOMING,
        metadata={'media_mode':'sip_room','sip_bridge_id':'bridge-one','sip_extension':'1040'})
    addon=SimsonAddon.__new__(SimsonAddon)
    addon.cfg=SimpleNamespace(routing_policy={'gateway_inbound_mode':'direct_target'})
    addon._sip_route_timers={};addon.call_mgr=SimpleNamespace(get=lambda call_id:call)
    addon._incoming_sip_fallback_candidates=AsyncMock(return_value=[])
    try:
        addon._schedule_incoming_sip_route(call)
        await addon._route_incoming_sip_to_configured_target(call)
        assert not addon._sip_route_timers
        addon._incoming_sip_fallback_candidates.assert_not_awaited()
    finally:
        tasks=list(addon._sip_route_timers.values())
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
