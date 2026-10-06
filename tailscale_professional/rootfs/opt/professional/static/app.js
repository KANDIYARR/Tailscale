'use strict';
const $ = (id) => document.getElementById(id);
let session = null;
let step = 0;
let restarting = false;
let saving = false;
let currentAddress = '';
const stateLabels = {Running: 'Connected', NeedsLogin: 'Sign-in needed', NeedsMachineAuth: 'Approval needed', Starting: 'Connecting', Stopped: 'Stopped', NoState: 'Not connected', Unavailable: 'Starting'};
const stateDetails = {Running: 'Your private connection is ready.', NeedsLogin: 'Open Tailscale controls to sign in, or add an authentication key.', NeedsMachineAuth: 'Approve this device in your Tailscale admin console.', Starting: 'Establishing your secure connection…', Stopped: 'Tailscale is stopped. Restart the add-on to reconnect.', NoState: 'Use guided setup to connect this device.', Unavailable: 'Waiting for the Tailscale service.'};

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`api/${path}`, {method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: body ? {'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf || ''} : {}, body: body ? JSON.stringify(body) : undefined});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The request could not be completed.');
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Check your connection and try again.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').classList.toggle('error', error);
  $('notice').hidden = !message;
}
function render(status) {
  const connected = status.state === 'Running' && status.online;
  $('connection-pill').textContent = connected ? 'Connected' : status.state === 'Running' ? 'Reconnecting' : stateLabels[status.state] || 'Checking';
  $('connection-pill').className = `pill ${connected ? 'online' : 'attention'}`;
  $('device-name').textContent = status.hostname || 'Your Home Assistant';
  $('connection-detail').textContent = status.state === 'Running' && !status.online ? 'Your device is offline. Checking the connection…' : stateDetails[status.state] || 'Checking the connection.';
  currentAddress = status.addresses?.[0] || '';
  $('ip-address').textContent = currentAddress || 'No address yet';
  $('copy-ip').disabled = !currentAddress;
  $('dns-name').textContent = status.dns_name || '';
  $('peer-count').replaceChildren(document.createTextNode(`${status.peers_online || 0} `));
  const total = document.createElement('small'); total.textContent = `of ${status.peers_total || 0} visible peers`;
  $('peer-count').append(total);
  const expiry = status.key_expiry ? new Date(status.key_expiry) : null;
  $('key-expiry').textContent = expiry && !Number.isNaN(expiry.valueOf()) ? `Expires ${expiry.toLocaleDateString()}` : status.state === 'Running' ? 'No expiry reported' : 'Available after sign-in';
  $('network-mode').textContent = session?.settings.userspace_networking ? 'Userspace networking' : 'Host networking';
  const checks = [...(status.health || [])];
  if (!checks.length) checks.push(connected ? 'No connection issues reported by Tailscale.' : stateDetails[status.state] || 'Waiting for status.');
  if (session?.has_auth_key && connected) checks.push('An enrollment key is still saved. Remove it through guided setup when it is no longer needed.');
  if (expiry && expiry.valueOf() > 0 && expiry.valueOf() - Date.now() < 7 * 86400000) checks.push('Your device key expires soon or has expired. Review it in the Tailscale admin console.');
  $('health-list').replaceChildren(...checks.map((message) => {const li = document.createElement('li'); li.textContent = message; return li;}));
  $('last-updated').textContent = `Checked ${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`;
}
async function initialize() {
  try {
    session = await api('session');
    $('version').textContent = `v${session.version} · Vinoth Sakthivel`;
    $('setup-open').disabled = false;
    render(session.status);
    notice('');
  } catch (_) { notice('Cannot reach the add-on yet. This page will retry automatically.', true); }
}
function showStep(value) {
  step = value;
  document.querySelectorAll('[data-step]').forEach((element) => {element.hidden = Number(element.dataset.step) !== step;});
  document.querySelectorAll('[data-step-indicator]').forEach((element) => {
    const active = Number(element.dataset.stepIndicator) === step;
    element.classList.toggle('active', active);
    if (active) element.setAttribute('aria-current', 'step'); else element.removeAttribute('aria-current');
  });
  $('step-back').hidden = step === 0;
  $('step-next').hidden = step === 2;
  $('setup-save').hidden = step !== 2;
  $('setup-error').hidden = true;
  if (step === 2) renderReview();
  if ($('setup-dialog').open) document.querySelector(`[data-step="${step}"] input`)?.focus();
}
function openSetup() {
  if (!session || saving) return;
  const values = session.settings;
  $('hostname').value = values.hostname || '';
  $('auth-key').value = '';
  $('clear-key').checked = false;
  $('clear-key-row').hidden = !session.has_auth_key;
  $('login-server').value = values.login_server || 'https://controlplane.tailscale.com';
  $('accept-dns').checked = !!values.accept_dns;
  $('accept-routes').checked = !!values.accept_routes;
  $('userspace').checked = !!values.userspace_networking;
  $('advertise-exit').checked = !!values.advertise_exit_node;
  $('routes').value = (values.advertise_routes || []).join('\n');
  showStep(0);
  $('setup-dialog').showModal();
}
function settings() {
  return {hostname: $('hostname').value.trim(), auth_key: $('auth-key').value.trim(), clear_auth_key: $('clear-key').checked,
    login_server: $('login-server').value.trim(), accept_dns: $('accept-dns').checked, accept_routes: $('accept-routes').checked,
    userspace_networking: $('userspace').checked, advertise_exit_node: $('advertise-exit').checked,
    advertise_routes: $('routes').value.split('\n').map((value) => value.trim()).filter(Boolean)};
}
function renderReview() {
  const values = settings();
  const rows = [['Device name', values.hostname || 'Use Home Assistant hostname'], ['Sign-in', values.auth_key ? 'Use the new authentication key' : values.clear_auth_key ? 'Remove saved key; keep current identity' : session.has_auth_key ? 'Keep saved key' : 'Browser sign-in / saved identity'], ['Networking', values.userspace_networking ? 'Userspace' : 'Host networking'], ['Network DNS', values.accept_dns ? 'Enabled' : 'Disabled'], ['Accept routes', values.accept_routes ? 'Enabled' : 'Disabled'], ['Provide exit node', values.advertise_exit_node ? 'Enabled' : 'Disabled'], ['Subnet routes', values.advertise_routes.join(', ') || 'None']];
  $('review-list').replaceChildren(...rows.flatMap(([label, value]) => {const dt = document.createElement('dt'); dt.textContent = label; const dd = document.createElement('dd'); dd.textContent = value; return [dt, dd];}));
}
function setupError(message) { $('setup-error').textContent = message; $('setup-error').hidden = false; }
$('setup-open').addEventListener('click', openSetup);
$('setup-close').addEventListener('click', () => {if (!saving) $('setup-dialog').close();});
$('setup-dialog').addEventListener('cancel', (event) => {if (saving) event.preventDefault();});
$('setup-dialog').addEventListener('close', () => {$('auth-key').value = '';});
$('step-back').addEventListener('click', () => showStep(Math.max(0, step - 1)));
$('step-next').addEventListener('click', () => {
  if (step === 0) {
    if (!$('login-server').reportValidity()) return;
    const name = $('hostname').value.trim();
    if (name && !/^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$/.test(name)) return setupError('Use letters, numbers and hyphens for the device name.');
    if ($('login-server').value.trim() !== session.settings.login_server && session.status.state === 'Running') return setupError('To switch control servers, first sign out through Tailscale controls, then return here.');
  }
  if (step === 1 && $('advertise-exit').checked && session.settings.exit_node) return setupError('An exit node is already selected. Remove it in the add-on Configuration tab before offering this device as an exit node.');
  showStep(Math.min(2, step + 1));
});
$('setup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (step !== 2 || saving) return;
  saving = true;
  $('setup-save').disabled = true;
  $('setup-save').textContent = 'Saving…';
  try {
    const result = await api('setup', {revision: session.revision, settings: settings()});
    session.revision = result.revision;
    $('auth-key').value = '';
    await api('restart', {confirm: true});
    $('setup-dialog').close();
    restarting = true;
    $('setup-open').disabled = true;
    notice('Settings saved. Reconnecting after the add-on restarts…');
    const previousCsrf = session.csrf;
    let reconnected = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 4000));
      try {
        const next = await api('session');
        if (next.csrf === previousCsrf) continue;
        session = next; render(next.status); reconnected = true; break;
      } catch (_) { /* Expected while the add-on restarts. */ }
    }
    notice(reconnected ? 'Setup saved. If sign-in is needed, open Tailscale controls below.' : 'Settings are saved. Reopen this page after restart, or restart the add-on from Home Assistant.', !reconnected);
  } catch (error) { setupError(error.message); }
  finally {saving = false; restarting = false; $('setup-open').disabled = false; $('setup-save').disabled = false; $('setup-save').textContent = 'Save and restart';}
});
$('copy-ip').addEventListener('click', async () => {
  try {await navigator.clipboard.writeText(currentAddress); $('copy-ip').textContent = 'Copied'; setTimeout(() => {$('copy-ip').textContent = 'Copy address';}, 2000);}
  catch (_) {notice('Clipboard access is unavailable. Select and copy the displayed address.');}
});
initialize();
setInterval(async () => {
  if (restarting || saving) return;
  if (!session) return initialize();
  try {render(await api('status'));}
  catch (_) {notice('The connection to this dashboard was interrupted. Retrying…', true);}
}, 15000);
