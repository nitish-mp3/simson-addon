# Native room SIP proxy simulation

This runs the real addon HTTP proxy against a local VPS stand-in, never a phone.
The stand-in models only the contract used by `forward_room_call`; it does not
establish SIP registration, originate audio, or prove actual device readiness.

From `addon`, run:

```powershell
postman simulation run postman/simulations/room-sip.sim.yaml --port 4908 --output ndjson
```

Point a fixture config at `ws://127.0.0.1:4908/ws` using account `fixture-site`,
node `fixture-node`, and install token `fixture-only`. Use `request_id: busy`
for a conflict or `html` for a proxy HTML failure. Normal request IDs return
202, and exact repeats return the same call ID with 200; changed repeats return
409. No mock is deployed or published. For automated real-HTTP tests including
authentication forwarding and error sanitization, run
`python -m pytest tests/test_room_calls.py -q`.
