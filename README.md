# Simson Call Relay - HAOS Addon
..
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
| `server_url` | WebSocket URL of your Simson VPS, for example `wss://simson-vps.vipsy.in/ws`. |
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
   - SIP server/domain: your VPS hostname, for example `simson-vps.vipsy.in`.
   - Port: `5060`.
   - Transport: TCP or UDP.
   - Username/Auth username: the endpoint username.
   - Password: the endpoint password.
   - Codecs: PCMU/G.711u and PCMA/G.711a only.
   - SRTP/TLS/video/Opus: disabled.
9. Register the phone. Calls to that endpoint should ring the routed HAOS addon card.

For an analog landline handset, configure these SIP settings on the ATA device, then plug the handset into the ATA's phone port.

## Route PSTN/GSM Gateways to HAOS

Use one dedicated SIP endpoint per gateway. Do not reuse a desk-phone endpoint for a gateway.

Recommended endpoint layout:

- `7001` - HT841 / landline FXO gateway, `Route To Node ID = office2`
- `7002` - SMG4008 / GSM gateway, `Route To Node ID = office2`
- `7009` - SMG4008 active GSM port, `Route To Node ID = office2`

Gateway SIP registration:

- SIP server/domain: `simson-vps.vipsy.in`
- Port: `5060`
- Transport: TCP or UDP
- SIP/Auth user: the gateway endpoint username, for example `7001`
- Password: the gateway endpoint password
- Codecs: PCMU/G.711u and PCMA/G.711a only
- DTMF: RFC2833/RFC4733

Inbound outside-call routing:

- Configure the gateway's inbound PSTN/GSM route to send calls to the registered gateway endpoint number, for example `7009`.
- Simson accepts that gateway number in a locked inbound context and uses the endpoint's `Route To Node ID` to ring the right HAOS addon.

Outbound HAOS-to-PSTN/GSM routing:

- Use the card's **Phone via Gateway** dial row and enter a number such as `+9192387324`; the leading `+` is accepted and sent as digits.
- Use trunk `7009` for the current GSM gateway, or create a Call Target with type `asterisk` for saved speed-dials.
- Put the gateway endpoint extension in **SIP/PSTN Trunk**, for example `7001` for landline, `7002`, or `7009` for GSM.
- The VPS dials `PJSIP/<outside-number>@<gateway-endpoint>` and bridges the answered call back to the HAOS browser card.

Transfer while a gateway call is active:

- Use **Transfer Call** on the card, enter another HAOS node ID, and optionally choose a named user after pressing **Users**.
- The VPS invites the new node into the same SIP bridge and only dismisses the original browser leg after the target answers.
- If the transfer target is busy or offline, the existing call remains active on the original card.

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

## Site Routing and Availability

Each HAOS addon instance keeps its own site settings in `/data/settings.json`, so homes/sites do not share targets, gateways, busy state, or routing policy.

In the addon panel, open **Settings -> Site Routing & Availability**:

- **Ring Before Next Target** controls how long a routed call rings before trying the next fallback.
- **Max Attempts** includes the primary target. For example, `4` means primary plus up to three fallback targets.
- **Final Fallback Target** is an optional last target such as a desk phone, security desk, or gateway-backed outside number.
- **Skip targets marked busy/offline** prevents routing to targets manually marked unavailable.
- Use the live routing board to mark each target **Available**, **Busy**, or **Offline**.

To route calls to other SIP phones, create a Call Target with **Type = SIP phone**, set **SIP Extension** to the phone extension, and leave the gateway trunk empty. To route to an outside phone through a gateway, create **Type = Gateway / outside line**, set the outside number as the extension, and set **SIP/PSTN Trunk** to the gateway endpoint such as `7009`.

## FXO Channel Event Troubleshooting

Raw Home Assistant notifications such as `New channel: PJSIP/fxo1-...` and `Channel hung up: PJSIP/fxo1-...` are not created by the Simson addon. They come from a separate onsite Asterisk AMI automation or integration that is publishing every channel lifecycle event.

If these notifications repeat:

- Check the FXO gateway call log first. A matching incoming PSTN caller ID means the physical landline is receiving real calls.
- If no PSTN call exists, inspect the FXO gateway's inbound route and retry settings. A local FXO retry loop should be fixed on the gateway instead of filtered inside Simson.
- In Home Assistant automations, search for `persistent_notification.create`, `Call Event`, `Call Ended`, or `New channel`. Disable or rate-limit that raw AMI monitor if user-facing notifications are not needed.
- Keep the Simson addon notification path enabled. Simson creates only the higher-level `Incoming Call` and `Call Failed` notifications used by the card.

## Local API Endpoints

The addon exposes a local HTTP API for the HA integration:

- `GET /api/health` - Health check
- `GET /api/status` - Connection status and node info
- `GET /api/routing` - Live routing board, availability, active calls, and target status
- `GET /api/settings` - Routing and endpoint settings
- `POST /api/settings` - Save routing and endpoint settings
- `POST /api/availability` - Mark this onsite addon available, busy, or offline
- `POST /api/target-availability` - Mark a configured target available, busy, or offline
- `GET /api/webrtc-config` - Browser WebRTC/SIP bridge config
- `POST /api/call` - Make a call
- `GET /api/automation` - Read the configured onsite automation presets
- `POST /api/automation/trigger/{trigger_id}` - Run a configured preset from the local HA integration
- `POST /api/automation/webhook/{webhook_id}` - Run a configured preset from an external webhook with `X-Simson-Webhook-Secret`

## Automation And Webhook Calls

Open the addon panel, select **Settings**, and use **Automation & Webhook Calls**:

1. Create a normal **Routing Target** first. For a desk phone, choose **SIP desk phone extension** and enter its SIP extension.
2. Add an automation trigger, give it a stable ID such as `doorbell_call`, and select the saved target.
3. For Home Assistant automations, call `simson.run_trigger` with the configured `trigger_id`.
4. For external systems, generate webhook credentials and use the displayed URL plus the private `X-Simson-Webhook-Secret` header.

Webhooks cannot dial arbitrary numbers supplied by the caller. They can invoke only enabled presets saved by the onsite admin. Each trigger also has repeat protection to prevent accidental call storms.

Keep the addon port private. If an external service needs webhook access, expose only the webhook path through a trusted HTTPS reverse proxy or a private VPN. Do not publish the raw addon HTTP port directly to the internet.
- `POST /api/answer` - Answer a call
- `POST /api/reject` - Reject a call
- `POST /api/hangup` - Hang up a call
- `POST /api/transfer` - Transfer an active SIP/PSTN/GSM bridge call to another node or specific HA user
