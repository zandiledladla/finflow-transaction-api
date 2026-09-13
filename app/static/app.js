const state = { sender: null, recipient: null, senderAccount: null, recipientAccount: null };
const byId = (id) => document.getElementById(id);
const transferButton = document.querySelector("#transfer-form button");

function setStatus(message, type = "") {
  const status = byId("status");
  status.textContent = message;
  status.className = `status ${type}`;
}

function logRequest(method, path, status) {
  const activity = byId("activity");
  activity.querySelector(".empty")?.remove();
  const item = document.createElement("li");
  item.innerHTML = `<span class="method">${method}</span><span>${path}</span><span class="code">${status}</span>`;
  activity.prepend(item);
}

async function request(path, options = {}) {
  const method = options.method || "GET";
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  logRequest(method, path, response.status);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(value);
}

async function refreshBalances() {
  state.senderAccount = await request(`/api/v1/accounts/${state.senderAccount.id}`);
  state.recipientAccount = await request(`/api/v1/accounts/${state.recipientAccount.id}`);
  byId("sender-balance").textContent = formatMoney(state.senderAccount.balance);
  byId("recipient-balance").textContent = formatMoney(state.recipientAccount.balance);
}

async function createDemo() {
  setStatus("Creating scenario…", "busy");
  byId("create-demo").disabled = true;
  const token = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  try {
    state.sender = await request("/api/v1/customers", { method: "POST", body: JSON.stringify({ full_name: "Lerato Mokoena", email: `lerato-${token}@demo.finflow` }) });
    state.recipient = await request("/api/v1/customers", { method: "POST", body: JSON.stringify({ full_name: "Anele Jacobs", email: `anele-${token}@demo.finflow` }) });
    state.senderAccount = await request("/api/v1/accounts", { method: "POST", body: JSON.stringify({ customer_id: state.sender.id, currency: "ZAR" }) });
    state.recipientAccount = await request("/api/v1/accounts", { method: "POST", body: JSON.stringify({ customer_id: state.recipient.id, currency: "ZAR" }) });
    await request(`/api/v1/transactions/accounts/${state.senderAccount.id}/deposit`, { method: "POST", headers: { "Idempotency-Key": `demo-funding-${token}` }, body: JSON.stringify({ amount: "1000.00", reference: "Demo opening balance" }) });
    byId("sender-name").textContent = state.sender.full_name;
    byId("recipient-name").textContent = state.recipient.full_name;
    await refreshBalances();
    transferButton.disabled = false;
    setStatus("Scenario ready", "success");
  } catch (error) {
    setStatus(error.message, "error");
    byId("create-demo").disabled = false;
  }
}

async function submitTransfer(event) {
  event.preventDefault();
  setStatus("Transferring…", "busy");
  transferButton.disabled = true;
  const amount = Number(byId("amount").value).toFixed(2);
  try {
    await request("/api/v1/transactions/transfer", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ source_account_id: state.senderAccount.id, destination_account_id: state.recipientAccount.id, amount, reference: "Interactive demo transfer" }) });
    await refreshBalances();
    setStatus(`${formatMoney(amount)} transferred`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    transferButton.disabled = false;
  }
}

byId("create-demo").addEventListener("click", createDemo);
byId("transfer-form").addEventListener("submit", submitTransfer);
byId("clear-log").addEventListener("click", () => { byId("activity").innerHTML = '<li class="empty">Requests will appear here.</li>'; });
