# Simson addon frontend

`src/` is the editable source. `../app/ui/` contains generated, locally bundled
release assets served by the Python addon. Node is a build dependency only.

## Structure

- `app/`: navigation, lazy page loader, and event dispatch.
- `pages/`: overview, routing, SIP phones, automation, setup, and advanced settings.
- `features/`: routing editors/actions, SIP provisioning/actions, and media preview.
- `state/`: session state and settings normalization.
- `services/`: ingress-relative API client, status synchronization, and settings writes.
- `shared/`: formatting, feedback, endpoint normalization, and call helpers.
- `styles/`: tokens, layout, controls, and individual feature styles.

Routes load through dynamic imports. Inputs and action modules load on demand.
The overview status poll skips hidden documents and unchanged state; settings are
normalized once per server document instead of being cloned repeatedly during
rendering. Existing save and routing contracts are preserved.

```sh
cd frontend
npm ci
npm run build
npm test
```

Commit the sources, lockfile, and generated `app/ui/` assets together. The Docker
image uses those assets directly. `bundle-report.json` records output sizes.
Do not hand-edit `app/ui/app.js` or `app/ui/styles.css`.

The integration frontend browser suite also exercises these addon pages when both
repositories are checked out next to one another. Media Studio is a private device
preview; actual dashboard-call device choices live in the card's Devices tab.
LAN camera inventory contains configured SIP endpoints, not automatic ONVIF/RTSP
discovery or a network-camera-to-WebRTC bridge.
