const http=require('node:http');
const receipts=new Map();
http.createServer(async(request,response)=>{
  const json=(status,value)=>{response.writeHead(status,{'content-type':'application/json'});response.end(JSON.stringify(value));};
  if(!['/room-calls','/node/room-calls'].includes(request.url))return json(501,{error:'Endpoint not modeled'});
  if(request.headers['x-simson-install-token']!=='fixture-only')return json(401,{error:'unauthorized'});
  if(request.method==='GET')return json(200,{native_sip_rooms:true});
  let raw='';for await(const chunk of request)raw+=chunk;
  let payload;try{payload=JSON.parse(raw);}catch{return json(400,{error:'invalid room request'});}
  if(payload.request_id==='busy')return json(409,{error:'the selected SIP phone is already in a call'});
  if(payload.request_id==='html'){response.writeHead(502,{'content-type':'text/html'});return response.end('<html>private upstream details</html>');}
  if(payload.target_node_id!=='fixture-node'||payload.source_extension!=='1040')return json(400,{error:'invalid room binding'});
  const key=payload.room_id+':'+payload.request_id;
  const previous=receipts.get(key);
  if(previous&&previous.binding!==raw)return json(409,{error:'request_id was already used with different room bindings'});
  const result=previous?.result||{call_id:'fixture-call',sip_bridge_id:'fixture-bridge',session_id:payload.session_id,status:'ringing',native_sip_rooms:true};
  receipts.set(key,{binding:raw,result});json(previous?200:202,result);
}).listen(process.env.PORT);
