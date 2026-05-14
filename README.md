# Simson Call Relay - HAOS Addon

Connects Home Assistant to the Simson VPS for browser calls, SIP desk phones, ATA-backed landline phones, and routed call targets.

## Working Audio Baseline

Browser to SIP phone audio and SIP phone back-calling are handled by the VPS Asterisk bridge. The addon fetches WebRTC/SIP credentials from the VPS automatically, so do not manually configure local AMI, TURN, or SIP-over-WebSocket credentials in the addon.

For SIP phones and ATAs, keep the device media profile simple:

- Enable PCMU / G.711u and PCMA / G.711a.
- Disable Opus, video, SRTP, and TLS unless the VPS trunk is explicitly configured for them.
- Use RFC2833/RFC4733 for DTMF.

## Installation

1. Add this repository to Home Assistant: **Settings -> Add-ons -> Add-on Store -> ... -> Repositories -> Paste URL**.
2. Install **Simson Call Relay**.
3. Set `server_url` and optionally `admin_token` in the addon **Configuration** tab.
4. Start the addon and open the addon panel.
5. Run the setup wizard. For another HA instance, paste the same Account ID so both nodes share one account.

## Configuration

Only these addon Configuration-tab options are required for normal use:

| Option | Description |
|--------|-------------|
| `server_url` | WebSocket URL of your Simson VPS, for example `wss://simson-vps.niti.life/ws`. |
| `admin_token` | Optional VPS admin token. Helps the addon provision accounts/nodes and fetch central config. |
| `log_level` | Logging level: `debug`, `info`, `warning`, or `error`. |

Node credentials, routing targets, and SIP phone endpoints are managed from the addon panel after setup.

## Route a SIP/Landline Phone to HAOS

Use this when a desk phone, SIP phone, or analog landline phone through an ATA should call into the HAOS addon.

1. Open the addon panel and copy this HA instance's **Node ID** from **Overview**.
2. Go to **Settings -> SIP Phone Endpoints -> Add SIP Phone**.
3. Set **Extension** to the number the phone will register and dial, for example `1025`.
4. Set **Username** to the same value as the extension unless your device requires a separate auth ID.
5. Set a strong **Password**.
6. Set **Route To Node ID** to the HAOS Node ID from Overview if this phone should ring this addon directly.
7. Save the endpoint.
8. Configure the SIP phone or ATA:
   - SIP server/domain: your VPS hostname, for example `simson-vps.niti.life`.
   - Port: `5060`.
   - Transport: TCP or UDP.
   - Username/Auth username: the endpoint username.
   - Password: the endpoint password.
   - Codecs: PCMU/G.711u and PCMA/G.711a only.
   - SRTP/TLS/video/Opus: disabled.
9. Register the phone. Calls to that endpoint should ring the routed HAOS addon card.

For an analog landline handset, configure these SIP settings on the ATA device, then plug the handset into the ATA's phone port.

## Call from HAOS to a SIP Phone or Landline

To call an internal SIP phone from the HA card, dial its extension or create a **Call Target**:

- Type: `asterisk`
- Asterisk Extension / Number: the SIP extension, for example `1025`
- SIP/PSTN Trunk: leave empty for an internal SIP endpoint

To call an external PSTN/landline number through a provider trunk, create a **Call Target**:

- Type: `asterisk`
- Asterisk Extension / Number: the external number
- SIP/PSTN Trunk: the configured PJSIP trunk name on the VPS
- Fallback Target IDs: optional comma-separated targets for busy/no-answer routing

## Local API Endpoints

The addon exposes a local HTTP API for the HA integration:

- `GET /api/health` - Health check
- `GET /api/status` - Connection status and node info
- `GET /api/settings` - Routing and endpoint settings
- `POST /api/settings` - Save routing and endpoint settings
- `GET /api/webrtc-config` - Browser WebRTC/SIP bridge config
- `POST /api/call` - Make a call
- `POST /api/answer` - Answer a call
- `POST /api/reject` - Reject a call
- `POST /api/hangup` - Hang up a call
