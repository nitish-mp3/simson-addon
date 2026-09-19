import { state, defaults } from './store.js';
import { deepMerge } from '../shared/dom.js';

let normalizedSettings;

export function getSettings() {
  if (state.settings && state.settings === normalizedSettings) return state.settings;
  state.settings = deepMerge(defaults, state.settings || {});
  state.settings.automation = deepMerge(defaults.automation, state.settings.automation || {});
  state.settings.routing = deepMerge(defaults.routing, state.settings.routing || {});
  state.settings.availability = deepMerge(defaults.availability, state.settings.availability || {});
  state.settings.call_targets = Array.isArray(state.settings.call_targets) ? state.settings.call_targets : [];
  state.settings.automation.triggers = Array.isArray(state.settings.automation.triggers) ? state.settings.automation.triggers : [];
  normalizedSettings = state.settings;
  return state.settings;
}

export function setByPath(path, value) {
  const settings = getSettings();
  const parts = path.split(".");
  let obj = settings;
  while (parts.length > 1) {
    const key = parts.shift();
    obj[key] = obj[key] || {};
    obj = obj[key];
  }
  obj[parts[0]] = value;
}
