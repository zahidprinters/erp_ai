try {
(function () {
console.log("[AI Widget] Script loaded at", new Date().toISOString());
window.__erpAi = window.__erpAi || {};

function getSession() {
let s = localStorage.getItem("ai_session");
if (!s) { s = Math.random().toString(36).slice(2); localStorage.setItem("ai_session", s); }
return s;
}

function bubble(msg, who) {
const mine = who === "user";
const ts = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const row = document.createElement("div");
row.style.cssText = "display:flex;justify-content:" + (mine ? "flex-end" : "flex-start") + ";margin:7px 0;";
const b = document.createElement("div");
b.style.cssText = "max-width:80%;padding:8px 11px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-word;box-shadow:0 1px 2px rgba(0,0,0,.12);" + (mine ? "background:#2490ef;color:#fff;" : "background:var(--control-bg,#eef2f6);color:var(--text-color,#1f262e);");
b.textContent = msg;
const meta = document.createElement("div");
meta.style.cssText = "font-size:10px;opacity:.6;margin-top:3px;";
meta.textContent = (mine ? "You" : "AI") + " · " + ts;
row.appendChild(b); b.appendChild(meta);
return row;
}

function addMsg(container, msg, who) { container.appendChild(bubble(msg, who)); container.scrollTop = container.scrollHeight; }

function addTyping(container) {
const t = document.createElement("div");
t.style.cssText = "margin:7px 0;font-size:12px;opacity:.7;";
t.textContent = "AI is thinking…";
container.appendChild(t); container.scrollTop = container.scrollHeight;
return t;
}

function send(container, inp, session, doctype, name) {
let q = inp.value.trim();
if (!q) return;
inp.value = "";
addMsg(container, q, "user");
const typing = addTyping(container);
const args = doctype && name ? { doctype: doctype, name: name, prompt: q, session: session } : { prompt: q, session: session };
const method = doctype && name ? "erp_ai.api.ask_with_doc" : "erp_ai.api.ask_v2";
frappe.call({ method: method, args: args })
.then(function (r) { typing.remove(); addMsg(container, r.message.response, "ai"); })
.catch(function (e) { typing.remove(); addMsg(container, "Sorry, an error: " + (e.message || "try again"), "ai"); });
}

function buildWidget() {
if (document.getElementById("ai-chat-toggle")) return;
var toggle = document.createElement("div");
toggle.id = "ai-chat-toggle";
toggle.innerHTML = "🤖";
toggle.title = "AI Assistant";
toggle.style.cssText = "position:fixed;right:24px;bottom:24px;width:56px;height:56px;border-radius:50%;background:#2490ef;color:#fff;display:flex;align-items:center;justify-content:center;font-size:26px;cursor:pointer;z-index:9999;box-shadow:0 3px 12px rgba(0,0,0,.4);";

var panel = document.createElement("div");
panel.id = "ai-chat-panel";
panel.style.cssText = "position:fixed;right:24px;bottom:90px;width:380px;height:520px;background:var(--card-bg,#fff);border-radius:14px;box-shadow:0 8px 32px rgba(0,0,0,.32);display:none;flex-direction:column;z-index:9999;overflow:hidden;";
panel.innerHTML = '<div style="background:#2490ef;color:#fff;padding:12px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center"><span>🤖 AI Assistant <small style="font-weight:400;opacity:.85">· private</small></span><button id="ai-clear" style="background:none;border:0;color:#fff;cursor:pointer;font-size:13px" title="Clear chat">🗑</button><button id="ai-chat-close" style="background:none;border:0;color:#fff;cursor:pointer;font-size:16px">✕</button></div><div id="ai-chat-msgs" style="flex:1;overflow-y:auto;padding:12px;background:var(--control-bg,#f6f8fa)"></div><div style="display:flex;border-top:1px solid var(--border-color,#e2e2e2);background:var(--card-bg,#fff)"><input id="ai-chat-input" style="flex:1;border:0;padding:12px;outline:none;background:transparent;color:inherit" placeholder="Ask anything… (Enter to send)"/><button id="ai-mic" style="border:0;background:transparent;color:#2490ef;padding:0 10px;cursor:pointer;font-size:18px" title="Speak (mic)">🎤</button><button id="ai-chat-send" style="border:0;background:#2490ef;color:#fff;padding:0 18px;cursor:pointer;font-weight:600">Send</button></div>';

document.body.appendChild(toggle);
document.body.appendChild(panel);

var container = panel.querySelector("#ai-chat-msgs");
var inp = panel.querySelector("#ai-chat-input");
var session = getSession();
var curDoc = null;

function doSend() { send(container, inp, session, curDoc && curDoc.doctype, curDoc && curDoc.name); }
panel.querySelector("#ai-chat-send").onclick = doSend;
inp.addEventListener("keydown", function (e) { if (e.key === "Enter") doSend(); });
panel.querySelector("#ai-chat-close").onclick = function () { panel.style.display = "none"; };
panel.querySelector("#ai-clear").onclick = function () { container.innerHTML = ""; };

	var micBtn = panel.querySelector("#ai-mic");
	function resetMic() {
		micBtn.style.background = "transparent";
		micBtn.textContent = "🎤";
	}
	micBtn.onclick = function () {
		if (!window.isSecureContext) {
			addMsg(container, "Microphone needs HTTPS (or localhost). Open the site via https:// or the localhost URL.", "ai");
			return;
		}
		var rec = window.__erpAiRec;
		if (rec && rec.state === "recording") { rec.stop(); return; }
		navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
			var mr = new MediaRecorder(stream);
			var chunks = [];
			mr.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
			mr.onstop = function () {
				stream.getTracks().forEach(function (t) { t.stop(); });
				resetMic();
				var blob = new Blob(chunks, { type: mr.mimeType || "audio/webm" });
				var fr = new FileReader();
				fr.onloadend = function () {
					var b64 = fr.result.split(",")[1];
					addMsg(container, "🎤 transcribing…", "ai");
					frappe.call({ method: "erp_ai.api.voice_to_text", args: { audio: b64, fmt: "webm" } })
						.then(function (r) {
							container.lastChild.remove();
							inp.value = r.message.text;
							inp.focus();
						})
						.catch(function (e) {
							container.lastChild.remove();
							addMsg(container, "Voice error: " + (e.message || "try again"), "ai");
						});
				};
				fr.readAsDataURL(blob);
			};
			mr.start();
			window.__erpAiRec = mr;
			micBtn.style.background = "#dc3545";
			micBtn.style.borderRadius = "50%";
			micBtn.textContent = "⏹";
		}).catch(function (e) {
			addMsg(container, "Mic permission denied: " + e.name, "ai");
		});
	};
toggle.onclick = function () { panel.style.display = panel.style.display === "flex" ? "none" : "flex"; };

var hello = document.createElement("div");
hello.style.cssText = "text-align:center;font-size:12px;opacity:.7;margin:4px 0 8px;";
hello.textContent = "Ask anything — including counts (e.g. 'total stock', 'how many items', 'unpaid invoices').";
container.appendChild(hello);

window.__erpAi.askWithDoc = function (dt, nm) {
curDoc = { doctype: dt, name: nm };
panel.style.display = "flex";
};
}

function injectFormButton() {
var frm = window.cur_frm;
if (!frm || !frm.doctype || !frm.docname) return;
if (document.getElementById("ai-form-ask")) return;
var wrapper = frm.page && frm.page.wrapper;
if (!wrapper) return;
var toolbar = wrapper.find && wrapper.find(".form-inner-toolbar");
if (!toolbar || !toolbar.length) return;
var btn = document.createElement("button");
btn.id = "ai-form-ask";
btn.type = "button";
btn.className = "btn btn-default btn-sm";
btn.innerHTML = "🤖 Ask AI";
btn.title = "Ask the AI about this " + frm.doctype;
btn.onclick = function () { buildWidget(); window.__erpAi.askWithDoc(frm.doctype, frm.docname); };
toolbar.append(btn);
}

function start() {
buildWidget();
setInterval(injectFormButton, 1200);
}

function mountWorkspaceChat() {
	// Detect workspace page by URL path (most reliable)
	var loc = window.location.pathname || '';
	var isWs = loc.indexOf('ai-assistant-hub') !== -1;
	console.log('[AI Widget] Checking workspace: path=' + loc + ' isWs=' + isWs);
	if (!isWs) return;

	// Find the workspace content area — Editor.js renders into .page-main-content
	var target = document.querySelector('.page-main-content') || document.querySelector('.editor-js-container') || document.querySelector('.layout-main-section');
	console.log('[AI Widget] Target found: ' + (target ? target.className : 'NONE'));
	if (!target) return;
	// Don't double-mount
	if (target.querySelector('.ai-ws-mount')) return;

	// Create mount point for the chat panel
	var mount = document.createElement('div');
	mount.className = 'ai-ws-mount';
	mount.style.cssText = 'margin-top:16px;margin-bottom:24px;';
	mount.innerHTML = '<div class="ai-embedded-chat-wrapper" style="min-height:500px;"><p style="text-align:center;color:#888;padding-top:40px;">Loading AI chat...</p></div>';
	target.appendChild(mount);
	console.log('[AI Widget] Chat panel injected into workspace');

	var w = mount.querySelector('.ai-embedded-chat-wrapper');
	buildWorkspaceChat(w, mount);
}

// Use MutationObserver to detect when workspace content is rendered
function observeWorkspace() {
	var loc = window.location.pathname || '';
	if (loc.indexOf('ai-assistant-hub') === -1) return;

	// Try immediately
	mountWorkspaceChat();

	// Also observe for Editor.js rendering
	var observer = new MutationObserver(function (mutations) {
		mountWorkspaceChat();
	});
	var container = document.querySelector('.editor-js-container') || document.querySelector('.layout-main-section');
	if (container) {
		observer.observe(container, { childList: true, subtree: true });
	}
	// Fallback: keep trying every 2s for 30s
	var tries = 0;
	var iv = setInterval(function () {
		mountWorkspaceChat();
		tries++;
		if (tries > 15) clearInterval(iv);
	}, 2000);
}

function buildWorkspaceChat(w, mount) {
	var chatId = 'ai-ws-chat-' + Math.random().toString(36).slice(2);
	var root = document.createElement('div');
	root.id = chatId;
	root.style.cssText = 'display:flex;flex-direction:column;height:500px;';
	var msgs = document.createElement('div');
	msgs.style.cssText = 'flex:1;overflow-y:auto;padding:12px;background:var(--control-bg,#f6f8fa)';
	var ctrl = document.createElement('div');
	ctrl.style.cssText = 'display:flex;border-top:1px solid var(--border-color,#e2e2e2);padding:8px;background:var(--card-bg,#fff)';
	var input = document.createElement('input');
	input.type = 'text';
	input.className = 'form-control';
	input.placeholder = 'Ask the AI...';
	input.style.flex = '1';
	var sendBtn = document.createElement('button');
	sendBtn.type = 'button';
	sendBtn.className = 'btn btn-primary btn-sm';
	sendBtn.textContent = 'Send';
	var mic = document.createElement('button');
	mic.type = 'button';
	mic.className = 'btn btn-secondary btn-sm';
	mic.innerHTML = '🎤';
	mic.id = 'ws-mic-' + chatId;
	ctrl.appendChild(input);
	ctrl.appendChild(mic);
	ctrl.appendChild(sendBtn);
	root.appendChild(msgs);
	root.appendChild(ctrl);
	w.innerHTML = '';
	w.appendChild(root);

	var session = getSession();
	var curDoc = null;

	function add(who, msg) {
		var row = document.createElement('div');
		row.style.cssText = 'margin:7px 0';
		var b = document.createElement('div');
		var mine = who === 'user';
		b.style.cssText = 'padding:8px 11px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-word' + (mine ? ';background:#2490ef;color:#fff;margin-left:auto;display:inline-block' : ';background:var(--control-bg,#eef2f6)');
		b.textContent = msg;
		row.appendChild(b);
		msgs.appendChild(row);
		msgs.scrollTop = msgs.scrollHeight;
	}

	function doSend() {
		var q = input.value.trim();
		if (!q) return;
		input.value = '';
		add('user', q);
		var typing = document.createElement('div');
		typing.style.cssText = 'font-size:12px;opacity:.7;margin:8px 0';
		typing.textContent = 'AI is thinking…';
		msgs.appendChild(typing);
		msgs.scrollTop = msgs.scrollHeight;
		var args = curDoc ? { doctype: curDoc.doctype, name: curDoc.name, prompt: q, session: session } : { prompt: q, session: session };
		var method = curDoc ? 'erp_ai.api.ask_with_doc' : 'erp_ai.api.ask_v2';
		frappe.call({ method: method, args: args })
			.then(function (r) { typing.remove(); add('ai', r.message.response); })
			.catch(function (e) { typing.remove(); add('ai', 'Sorry, an error: ' + (e.message || 'try again')); });
	}

	sendBtn.onclick = doSend;
	input.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSend(); });

	// Voice (same logic as floating widget, scoped to this input)
	var micBtn = mic;
	function resetMic() { micBtn.style.background = 'transparent'; micBtn.textContent = '🎤'; }
	micBtn.onclick = function () {
		if (!window.isSecureContext) { add('ai', 'Microphone needs HTTPS (or localhost).'); return; }
		var rec = window.__erpAiRec;
		if (rec && rec.state === 'recording') { rec.stop(); return; }
		navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
			var mr = new MediaRecorder(stream);
			var chunks = [];
			mr.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
			mr.onstop = function () {
				stream.getTracks().forEach(function (t) { t.stop(); });
				resetMic();
				var blob = new Blob(chunks, { type: mr.mimeType || 'audio/webm' });
				var fr = new FileReader();
				fr.onloadend = function () {
					add('ai', '🎤 transcribing…');
					var b64 = fr.result.split(',')[1];
					frappe.call({ method: 'erp_ai.api.voice_to_text', args: { audio: b64, fmt: 'webm' } })
						.then(function (r) {
							var last = msgs.lastChild; if (last) last.remove();
							input.value = r.message.text; input.focus();
						})
						.catch(function (e) {
							var last = msgs.lastChild; if (last) last.remove();
							add('ai', 'Voice error: ' + (e.message || 'try again'));
						});
				};
				fr.readAsDataURL(blob);
			};
			mr.start();
			window.__erpAiRec = mr;
			micBtn.style.background = '#dc3545';
			micBtn.textContent = '⏹';
		}).catch(function (e) { add('ai', 'Mic permission denied: ' + e.name); });
	};

		add('ai', 'Hello from your AI assistant. Ask me about ERPNext, your data, or how-to steps.');

	// Quick question chips (mount is the parent div)
	if (mount) {
		var chips = document.createElement('div');
		chips.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;';
		var quickQ = ['How many items?', 'Total stock?', 'Unpaid invoices', 'Customer count?'];
		quickQ.forEach(function (q) {
			var btn = document.createElement('button');
			btn.type = 'button';
			btn.className = 'btn btn-outline-secondary btn-sm';
			btn.textContent = q;
			btn.onclick = function () { askDirect(q); };
			chips.appendChild(btn);
		});
		mount.appendChild(chips);
	}
}

if (document.readyState === "complete") start();
else window.addEventListener("load", start);

// Mount chat inside workspace using MutationObserver + fallback interval
observeWorkspace();
window.__erpAi_mountWorkspaceChat = mountWorkspaceChat;
window.__erpAi_observeWorkspace = observeWorkspace;
window.__erpAi_buildWorkspaceChat = buildWorkspaceChat;
})();
} catch (e) {
console.error('[AI Widget] ERROR:', e.message);
console.error('[AI Widget] Stack:', e.stack);
}

