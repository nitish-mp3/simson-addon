import { state } from '../../state/store.js';
import { $, esc, option } from '../../shared/dom.js';

export function phoneProvisioningProfiles() {
  const profiles = state.health?.capabilities?.phone_provisioning?.profiles;
  return Array.isArray(profiles) && profiles.length ? profiles : [{
    id: "grandstream_gsc36xx",
    name: "Grandstream GSC36xx door/camera station",
    mode: "direct_management",
    automatic_write: true,
    help: "Direct account setup for GSC3610, GSC3615, and GSC3620.",
  }];
}

export function selectedPhoneProvisioningProfile() {
  const selected = $("sip-phone-profile")?.value || phoneProvisioningProfiles()[0]?.id || "";
  return phoneProvisioningProfiles().find((profile) => profile.id === selected) || phoneProvisioningProfiles()[0];
}

export function updatePhoneProfileHelp() {
  const profile = selectedPhoneProvisioningProfile();
  const hint = $("sip-phone-profile-help");
  const button = document.querySelector('[data-action="discover-phone"]');
  if (hint) hint.textContent = profile?.help || "Select the exact device family.";
  if (button) {
    button.disabled = profile?.automatic_write === false;
    button.textContent = profile?.automatic_write === false
      ? "Provisioning-server setup required"
      : "Test connection & find accounts";
  }
}

export function phoneProvisioningResultHtml() {
  const provision = state.phoneProvisioning;
  if (!provision.sessionId) {
    return `<div class="provision-status idle"><b>Not tested</b><span>Enter all management fields, then test before creating.</span></div>`;
  }
  const available = (provision.slots || []).filter((slot) => slot.available);
  const occupied = (provision.slots || []).filter((slot) => !slot.available);
  return `
    <div class="provision-status ok">
      <b>Connection verified</b>
      <span>${esc(provision.deviceName)} at ${esc(provision.phoneIp)} · expires in 5 minutes</span>
    </div>
    <div class="field full">
      <label>Install into available phone account</label>
      <select id="sip-phone-slot">
        <option value="">Select an account slot</option>
        ${available.map((slot) => option(slot.slot, `Account ${slot.slot} · empty`, provision.selectedSlot)).join("")}
      </select>
      ${occupied.length ? `<div class="hint">Protected existing accounts: ${occupied.map((slot) => `Account ${esc(slot.slot)}${slot.sip_user ? ` (${esc(slot.sip_user)})` : ""}`).join(", ")}. Simson will not overwrite them.</div>` : ""}
    </div>`;
}

export function renderPhoneProvisioningResult() {
  const result = $("sip-phone-test-result");
  if (result) result.innerHTML = phoneProvisioningResultHtml();
}

export function invalidatePhoneProvisioningTest() {
  state.phoneProvisioning.sessionId = "";
  state.phoneProvisioning.slots = [];
  state.phoneProvisioning.selectedSlot = "";
  state.phoneProvisioning.deviceName = "";
  state.phoneProvisioning.phoneIp = "";
  renderPhoneProvisioningResult();
}

