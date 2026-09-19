import { test } from 'node:test';
import assert from 'node:assert/strict';

globalThis.window={};
const {state}=await import('../src/state/store.js');
const {getSettings,setByPath}=await import('../src/state/settings.js');
const {api}=await import('../src/services/api.js');

test('settings normalize once and retain edits until the server replaces the document',()=>{
  state.settings={routing:{ring_seconds:30}};
  const settings=getSettings();assert.equal(settings.routing.ring_seconds,30);
  assert.equal(settings.routing.max_attempts,4);assert.equal(getSettings(),settings);
  setByPath('routing.ring_seconds',42);assert.equal(getSettings().routing.ring_seconds,42);
  state.settings={routing:{ring_seconds:10}};
  assert.notEqual(getSettings(),settings);assert.equal(getSettings().routing.ring_seconds,10);
});

test('API retains ingress-relative URLs and surfaces gateway conflicts',async()=>{
  const previous=globalThis.fetch;let requested;
  globalThis.fetch=async(url,options)=>{requested={url,options};return new Response(JSON.stringify({error:'Trunk busy',errors:['Call already active']}),{status:409});};
  try {
    await assert.rejects(api('api/call',{method:'POST',body:'{}'}),error=>error.status===409 && error.message==='Call already active');
    assert.equal(requested.url,'api/call');assert.equal(requested.options.headers['Content-Type'],'application/json');
    assert.ok(requested.options.signal instanceof AbortSignal);
  }finally{globalThis.fetch=previous;}
});
