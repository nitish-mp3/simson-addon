# Simson Call Relay - HAOS Addon
..
Connects Home Assistant to the Simson VPS for browser calls, SIP desk phones, ATA-backed landline phones, and routed call targets.

## Working Audio Baseline

Browser to SIP phone audio and SIP phone back-calling are handled by the VPS Asterisk bridge. The addon fetches WebRTC/SIP credentials from the VPS automatically, so do not manually configure local AMI, TURN, or SIP-over-WebSocket credentials in the addon.

For SIP phones and ATAs, keep the device media profile simple:

- Enable PCMU / G.711u and PCMA / G.711a.
- Disable Opus, video, SRTP, and TLS unless the VPS trunk is explicitly configured for them.
- Use RFC2833/RFC4733 for DTMF.

### Private prompt for a receiving SIP phone

The **SIP Phones** page can assign an optional spoken prompt to each endpoint. Type the sentence, for example `Call for Amit. Please wait while I connect you.` Simson generates an 8 kHz telephony WAV automatically on the VPS, caches it per customer site and phone, and removes stale versions when the text changes. Asterisk plays it only to that receiving phone after it answers; the caller is connected after playback. Leave the text blank to preserve normal call behavior.

### Caller waiting announcement before the destination rings

Each SIP phone can also have a separate caller-only waiting sentence, for example `Please wait while I call the kitchen monitor.` Asterisk sends this to the caller as early media and starts ringing the destination only after playback completes. This does not replace the private receiving-phone prompt; the two stages can be enabled independently. Leave it blank when the destination should ring immediately.

Standard SIP cannot send arbitrary audio to a receiving handset before that handset answers because no media session exists yet. Use **Receiving-phone private prompt** when the destination must hear the message: Simson plays it immediately after manual or automatic answer and before bridging the caller.

### Exact route call limits

Under a SIP phone, **Route-specific connected call limits** can end only a selected source-to-target route after a configured number of connected seconds. For example, a rule `1027 -> 1028 = 15 seconds` affects only calls from 1027 to 1028. Ringing and the before-ring announcement do not consume this time, and all routes without a rule remain unlimited. Sources must be enabled SIP phones in the same site.

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
- `GET /api/automation/device/{webhook_id}/{trigger_id}` - Run a saved preset from GET-only onsite hardware using a private capability URL
- `GET /api/automation/webhook/{webhook_id}` - Backward-compatible GET-only camera URL when exactly one enabled door preset exists

## Automation And Webhook Calls

Open the addon panel, select **Settings**, and use **Automation & Webhook Calls**:

1. Create a normal **Routing Target** first. For a desk phone, choose **SIP desk phone extension** and enter its SIP extension.
2. Add an automation trigger, give it a stable ID such as `doorbell_call`, and select the saved target.
3. For Home Assistant automations, call `simson.run_trigger` with the configured `trigger_id`.
4. For external systems that support POST headers, generate webhook credentials and use the displayed URL plus the private `X-Simson-Webhook-Secret` header.
5. For onsite camera panels that support only a GET callback URL, use the displayed private camera URL. Treat the complete URL as a password and regenerate credentials if it is exposed.

Webhooks cannot dial arbitrary numbers supplied by the caller. They can invoke only enabled presets saved by the onsite admin. Each trigger also has repeat protection to prevent accidental call storms.

Keep the addon port private. If an external service needs webhook access, expose only the webhook path through a trusted HTTPS reverse proxy or a private VPN. Do not publish the raw addon HTTP port directly to the internet.

### Door Camera Face-Mismatch Calls

For an outdoor SIP door station with a camera and face recognition:

1. Create SIP endpoints for the outdoor station and the indoor video phone. Enable **Video capable device** for both endpoints. Both devices must register to the same Simson VPS account.
2. Create **Routing Targets** for every destination that may ring. Use **SIP desk phone** for indoor video monitors and **Home / node** for HAOS cards or other homes.
3. Under **Automation & Webhook Calls**, create a door camera flow.
4. Enter the outdoor station SIP extension, select one or more destinations, generate webhook credentials, and save.
5. Configure the station's face-recognition mismatch action using one displayed recipe:
   - For a GET-only camera panel, paste the complete private camera callback URL.
   - For a controller that supports headers, `POST` the authenticated webhook URL with `X-Simson-Webhook-Secret` and `{"trigger_id":"your_trigger_id"}`.
   - If Home Assistant conditions are required, use the displayed HA webhook relay automation and include `GET` in `allowed_methods`.

Use exactly one callback path for each face-recognition action. The direct GET-only camera URL calls Simson without passing through an HA webhook automation. If you use that direct path and need companion HA actions, trigger them from the `simson_door_station_call` event instead of calling `simson.run_trigger` again.

The callback workflow calls the outdoor station first and then bridges its native SIP media to selected SIP/video phones. The outdoor station must support auto-answer for SIP callbacks. H.264 video is negotiated only between compatible SIP endpoints; existing HAOS browser audio, gateway, and landline routes remain audio-only. If you select HAOS node targets in the same flow, they receive a normal Simson call/event so local automations can react, but they do not receive the native SIP video stream.

For Home Assistant automations, Simson publishes:

- `simson_call_event` for incoming, outgoing, active, failed, ended, transferred, and forwarded call lifecycle changes.
- `sensor.simson_last_call_event` with the same event data as attributes, including `call_id`, `direction`, `call_type`, `node_id`, `target_id`, `target_type`, `sip_extension`, `source_extension`, `target_extension`, `remote_number`, and `status`.
- `simson_door_station_call` when a door camera SIP bridge is started for a SIP/video target.
- `sensor.simson_last_automation_event` with the last automation or door-flow result, including per-target status for multi-destination flows.

If the door-station firmware can place a SIP call directly when recognition fails, use that device-native mode only after adding an approved PBX direct-dial rule for the station. The supported default in Simson is the protected webhook callback flow above.
- `POST /api/answer` - Answer a call
- `POST /api/reject` - Reject a call
- `POST /api/hangup` - Hang up a call
- `POST /api/transfer` - Transfer an active SIP/PSTN/GSM bridge call to another node or specific HA user
