// Frontend integration seam. This build is explicitly MOCK-only.
// A future live adapter must obtain signed prepay parameters from the backend,
// invoke the official payment API, then QUERY the server for confirmed status.
const A = require('./api');
async function pay(orderId, success = true) {
  return A.call('/payments/' + encodeURIComponent(orderId) + '/simulate', 'POST', { success });
}
module.exports = { pay, mode: 'mock' };
