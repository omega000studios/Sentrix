'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { orders: [], selected: null, filter: 'ALL', authorization: null, busy: false };
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const title = (value) => ({ BLOCKED: 'Blocked', REVIEW: 'Review', PROTECTED: 'Protected' }[value] || 'Awaiting label');
const statusClass = (value) => ({ BLOCKED: 'blocked', REVIEW: 'review', PROTECTED: 'protected' }[value] || 'pending');
const status = (value) => `<span class="status ${statusClass(value)}">${title(value)}</span>`;
function notice(message, error = false) { $('#notice').textContent = message; $('#notice').classList.toggle('error', error); }
function busy(value) {
  state.busy = value;
  $('#refresh').disabled = value || !state.authorization;
  $('#connect').disabled = value;
  $('#signout').disabled = value;
  const check = $('#run-check');
  if (check) check.disabled = value;
}
async function api(path, body) {
  const response = await fetch(path, { method: body ? 'POST' : 'GET', credentials: 'omit', headers: { Authorization: state.authorization, ...(body ? { 'Content-Type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}), cache: 'no-store' });
  if (response.status === 401) { disconnect(); throw new Error('Credentials were not accepted. Enter your merchant username and password.'); }
  if (!response.ok) throw new Error(`Request failed (${response.status}). Check that the backend is running, then try again.`);
  return response.json();
}
function disconnect() {
  state.authorization = null; state.orders = []; state.selected = null;
  $('#workspace').hidden = true; $('#login').hidden = false; $('#signout').hidden = true;
  $('#connection').textContent = 'Not connected'; $('#orders').replaceChildren(); $('#detail').replaceChildren();
  $('#password').value = ''; $('#refresh').disabled = true;
}
async function loadOrders() {
  busy(true);
  notice('Loading saved orders…');
  try {
    state.orders = await api('/orders');
    if (!state.orders.some((order) => order.order_id === state.selected)) state.selected = state.orders.find((order) => order.source === 'sandbox')?.order_id || state.orders[0]?.order_id || null;
    $('#login').hidden = true; $('#workspace').hidden = false; $('#signout').hidden = false;
    $('#connection').textContent = 'Backend connected'; $('#password').value = '';
    render();
    notice(`${state.orders.length} saved orders loaded.`);
  } catch (error) { notice(error.message, true); }
  finally { busy(false); }
}
function render() {
  $('#total').textContent = `(${state.orders.length})`;
  const search = $('#search').value.trim().toLowerCase();
  const orders = state.orders.filter((order) => (state.filter === 'ALL' || order.verdict === state.filter) && order.order_id.toLowerCase().includes(search));
  if (!orders.some((order) => order.order_id === state.selected)) state.selected = orders[0]?.order_id || null;
  $('#orders').innerHTML = orders.map((order) => `<tr class="${order.order_id === state.selected ? 'selected' : ''}"><td><button class="order-button" data-order="${escapeHTML(order.order_id)}" aria-pressed="${order.order_id === state.selected}">${escapeHTML(order.order_id)}</button><span class="source">${order.source === 'sandbox' ? 'PayPal sandbox' : 'Synthetic fixture'}</span></td><td>${escapeHTML(new Intl.NumberFormat('en-US', { style: 'currency', currency: order.amount.currency }).format(Number(order.amount.value)))}</td><td>${status(order.verdict)}</td></tr>`).join('');
  $('#empty').hidden = orders.length > 0;
  renderDetail();
}
function addressLines(address, reference) {
  if (!address) return '<p class="address-lines">No label checked yet.</p>';
  const fields = ['line1', 'line2', 'city', 'state', 'postal_code', 'country'];
  return `<div class="address-lines">${fields.filter((key) => address[key] || reference?.[key]).map((key) => `<div><span class="${reference && address[key] !== reference[key] ? 'changed' : ''}">${escapeHTML(address[key] || 'Not provided')}</span></div>`).join('')}</div>`;
}
function renderDetail() {
  const order = state.orders.find((item) => item.order_id === state.selected);
  if (!order) { $('#detail').innerHTML = '<p class="detail-placeholder">Select an order to inspect its shipment.</p>'; return; }
  const heading = { BLOCKED: 'Hold dispatch', REVIEW: 'Human review needed', PROTECTED: 'Address check passed' }[order.verdict] || 'Ready for an address check';
  const explanation = { BLOCKED: 'The shipping destination differs from the payment record.', REVIEW: 'Resolve uncertainty before proceeding with fulfillment.', PROTECTED: 'The supported address checks pass for this shipment.' }[order.verdict] || 'Check a shipping label against the original payment address.';
  const reasons = order.comparison?.reasons || [];
  $('#detail').innerHTML = `<div class="detail-head">${status(order.verdict)}<h2>${escapeHTML(order.order_id)}</h2><p class="detail-meta">${order.source === 'sandbox' ? 'PayPal sandbox capture' : 'Synthetic demo order'} · ${escapeHTML(order.amount.currency)} ${escapeHTML(order.amount.value)} · Eligibility: ${escapeHTML(order.seller_protection)}</p><div class="decision"><h3>${heading}</h3><p>${explanation}</p>${reasons.length ? `<ul>${reasons.map((reason) => `<li>${escapeHTML(reason)}</li>`).join('')}</ul>` : ''}</div></div><div class="address-section"><div class="section-heading"><h3>Destination comparison</h3><span class="match-label">${escapeHTML(order.comparison?.match?.replaceAll('_', ' ') || 'Not evaluated')}</span></div><div class="addresses"><div><p class="address-title">PayPal payment address</p>${addressLines(order.paypal_address)}</div><div><p class="address-title">Latest shipping label</p>${addressLines(order.label?.address, order.paypal_address)}</div></div></div>${order.message ? `<div class="message-section"><h3>Customer message</h3><blockquote>“${escapeHTML(order.message.text)}”</blockquote><small>${order.source === 'fixture' ? 'Simulated message' : 'Stored message'}${order.ai_analysis ? ` · ${escapeHTML(order.ai_analysis.intent.replaceAll('_', ' ').toLowerCase())}` : ' · Analysis pending'}</small></div>` : ''}<form id="label-form" class="simulation"><h3>Try a label check</h3><p>Simulated label data. Running a check saves a new verdict and audit record for this order.</p><label for="scenario">Label scenario<select id="scenario"><option value="match">Same address as the PayPal payment</option><option value="mismatch">Different house number</option><option value="uncertain">Same address, low extraction confidence</option></select></label><button id="run-check" class="primary" ${state.busy ? 'disabled' : ''}>Run simulated check</button></form>`;
}
$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const bytes = new TextEncoder().encode(`${$('#username').value}:${$('#password').value}`);
  state.authorization = `Basic ${btoa(String.fromCharCode(...bytes))}`;
  await loadOrders();
});
$('#signout').addEventListener('click', () => { disconnect(); notice('Signed out.'); $('#username').focus(); });
$('#refresh').addEventListener('click', loadOrders);
$('#search').addEventListener('input', render);
$('.filters').addEventListener('click', (event) => {
  const button = event.target.closest('[data-filter]');
  if (!button) return;
  state.filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
  render();
});
$('#orders').addEventListener('click', (event) => {
  const button = event.target.closest('[data-order]');
  if (!button || state.busy) return;
  state.selected = button.dataset.order;
  render();
  const selected = [...document.querySelectorAll('[data-order]')].find((item) => item.dataset.order === state.selected);
  selected?.focus();
});
$('#detail').addEventListener('submit', async (event) => {
  if (event.target.id !== 'label-form') return;
  event.preventDefault();
  const order = state.orders.find((item) => item.order_id === state.selected);
  const scenario = $('#scenario').value;
  const address = { ...order.paypal_address };
  if (scenario === 'mismatch') address.line1 = /^\d+/.test(address.line1) ? address.line1.replace(/^\d+/, (number) => number === '987' ? '123' : '987') : '987 Main Street';
  busy(true); notice('Checking the simulated label…');
  try {
    const result = await api('/labels', { order_id: order.order_id, address, confidence: scenario === 'uncertain' ? 0.65 : 0.98, carrier: 'SIMULATED', tracking_number: 'SIMULATED-UI-LABEL' });
    state.orders = state.orders.map((item) => item.order_id === result.order_id ? result : item);
    render();
    notice(`Saved simulated check for ${result.order_id}: ${title(result.verdict)}.`);
    $('#detail').setAttribute('tabindex', '-1'); $('#detail').focus();
  } catch (error) { notice(error.message, true); }
  finally { busy(false); }
});
