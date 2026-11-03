// 前端只呼叫本服務自己的 API（同源），不直接連第三方，
// 所以快取、重試、錯誤處理都由後端統一負責。

const CURRENCIES = {
  TWD: "新台幣", USD: "美元", JPY: "日圓", EUR: "歐元", CNY: "人民幣",
  HKD: "港幣", GBP: "英鎊", AUD: "澳幣", KRW: "韓元", SGD: "新加坡幣",
  CAD: "加拿大幣", THB: "泰銖",
};
const BOARD = ["USD", "JPY", "EUR", "CNY", "HKD", "GBP", "AUD", "KRW", "SGD"];

const $ = (id) => document.getElementById(id);
const amountEl = $("amount");
const fromEl = $("from");
const toEl = $("to");
const resultEl = $("result");
const rateLineEl = $("rate-line");
const messageEl = $("message");
const updatedEl = $("updated");
const boardBody = $("board-body");

const fmt = (value, max = 4) =>
  Number(value).toLocaleString("zh-TW", { maximumFractionDigits: max });

const fmtTime = (iso) =>
  new Date(iso).toLocaleString("zh-TW", {
    timeZone: "Asia/Taipei", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit",
  });

function fillSelect(select, selected) {
  for (const [code, name] of Object.entries(CURRENCIES)) {
    const opt = new Option(`${code} ${name}`, code, false, code === selected);
    select.add(opt);
  }
}

function showMessage(text) {
  messageEl.textContent = text;
  messageEl.hidden = !text;
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = body.error || {};
    const field = err.details?.[0]?.field;
    // 後端驗證訊息是給工程師看的英文；使用者看到的改成中文提示
    const msg = field === "amount"
      ? "請輸入大於 0 的數字，最多 6 位小數"
      : err.message || "請求失敗，請稍後再試";
    throw new Error(err.request_id ? `${msg}（追蹤編號 ${err.request_id}）` : msg);
  }
  return body;
}

function updatedText(data) {
  const base = `匯率更新於 ${fmtTime(data.last_updated_utc)}（台灣時間）`;
  return data.stale ? `${base}，資料源暫時無法連線，顯示的是最後一次取得的資料` : base;
}

// ---------- 換算 ----------
let timer;
let requestSeq = 0;

function scheduleConvert() {
  clearTimeout(timer);
  timer = setTimeout(convert, 300); // 停止輸入 0.3 秒後才送出，避免每打一個字就呼叫 API
}

async function convert() {
  const amount = amountEl.value.replace(/,/g, "").trim();
  const from = fromEl.value;
  const to = toEl.value;
  markBoard();

  if (!amount) {
    resultEl.textContent = "—";
    rateLineEl.textContent = "";
    showMessage("");
    return;
  }

  const seq = ++requestSeq; // 只採用最新一次請求的結果，避免慢回應覆蓋新結果
  try {
    const data = await api("/api/v1/convert", {
      method: "POST",
      body: JSON.stringify({ from_currency: from, to_currency: to, amount }),
    });
    if (seq !== requestSeq) return;
    resultEl.textContent = fmt(data.result, 2); // 顯示到小數 2 位，精確值仍可從下方匯率計算
    rateLineEl.textContent =
      `1 ${from} = ${fmt(data.rate, 6)} ${to}，1 ${to} = ${fmt(data.inverse_rate, 6)} ${from}`;
    updatedEl.textContent = updatedText(data);
    showMessage("");
  } catch (err) {
    if (seq !== requestSeq) return;
    resultEl.textContent = "—";
    rateLineEl.textContent = "";
    showMessage(err.message);
  }
}

// ---------- 牌告看板 ----------
async function loadBoard() {
  try {
    const data = await api(`/api/v1/rates/latest?base=TWD&symbols=${BOARD.join(",")}`);
    boardBody.replaceChildren(
      ...BOARD.map((code) => {
        const perTwd = Number(data.rates[code]);
        const tr = document.createElement("tr");
        tr.tabIndex = 0;
        tr.dataset.code = code;
        tr.innerHTML = `
          <td><span class="code">${code}</span><span class="name">${CURRENCIES[code]}</span></td>
          <td class="num">${fmt(1 / perTwd, 4)}</td>`;
        const pick = () => {
          fromEl.value = code;
          toEl.value = "TWD";
          convert();
        };
        tr.addEventListener("click", pick);
        tr.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); }
        });
        return tr;
      }),
    );
    updatedEl.textContent = updatedText(data);
    markBoard();
  } catch (err) {
    boardBody.innerHTML = `<tr><td colspan="2" class="empty"></td></tr>`;
    boardBody.querySelector("td").textContent = `無法載入匯率：${err.message}`;
    updatedEl.textContent = "目前無法取得匯率";
  }
}

function markBoard() {
  for (const tr of boardBody.querySelectorAll("tr[data-code]")) {
    const active = tr.dataset.code === fromEl.value && toEl.value === "TWD";
    tr.setAttribute("aria-current", active ? "true" : "false");
  }
}

// ---------- 初始化 ----------
fillSelect(fromEl, "USD");
fillSelect(toEl, "TWD");

amountEl.addEventListener("input", scheduleConvert);
fromEl.addEventListener("change", convert);
toEl.addEventListener("change", convert);
$("swap").addEventListener("click", () => {
  [fromEl.value, toEl.value] = [toEl.value, fromEl.value];
  convert();
});

loadBoard();
convert();
