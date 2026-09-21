frappe.pages["ai-assistant"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({ parent: wrapper, title: "AI Assistant", single_column: true });

	var session = localStorage.getItem("ai_session");
	if (!session) {
		session = Math.random().toString(36).slice(2);
		localStorage.setItem("ai_session", session);
	}

	var qs = [
		"How do I create a Sales Invoice?",
		"What apps are installed here?",
		"How do I make a Purchase Receipt?",
		"What is a Stock Entry?",
	];

	$(wrapper)
		.find(".layout-main")
		.html(
			'<div style="max-width:820px;margin:0 auto;display:flex;flex-direction:column;height:calc(100vh - 160px)">' +
				'<div style="padding:6px 0;display:flex;flex-wrap:wrap;gap:6px">' +
				qs
					.map(function (q) {
						return '<button class="btn btn-xs btn-default ai-q">' + q + "</button>";
					})
					.join("") +
				"</div>" +
				'<div id="ai-page-msgs" style="flex:1;overflow-y:auto;padding:14px"></div>' +
				'<div style="display:flex;gap:8px;padding:12px;border-top:1px solid var(--border-color,#e2e2e2)">' +
				'<input id="ai-page-input" class="form-control" placeholder="Ask anything…">' +
				'<button id="ai-page-send" class="btn btn-primary">Send</button></div></div>'
		);

	function msgEl(who, text, ts) {
		var mine = who === "user";
		var d = document.createElement("div");
		d.style.cssText =
			"display:flex;justify-content:" +
			(mine ? "flex-end" : "flex-start") +
			";margin:8px 0;";
		var b = document.createElement("div");
		b.style.cssText =
			"max-width:78%;padding:9px 12px;border-radius:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;box-shadow:0 1px 2px rgba(0,0,0,.12);" +
			(mine
				? "background:#2490ef;color:#fff;"
				: "background:var(--control-bg,#eef2f6);color:var(--text-color,#1f262e);");
		b.textContent = text;
		var m = document.createElement("div");
		m.style.cssText = "font-size:10px;opacity:.6;margin-top:3px;";
		m.textContent =
			(mine ? "You" : "AI") +
			" · " +
			(ts || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
		b.appendChild(m);
		d.appendChild(b);
		return d;
	}

	var msgs = $(wrapper).find("#ai-page-msgs");

	function add(who, text) {
		msgs.append(msgEl(who, text));
		msgs.scrollTop(msgs[0].scrollHeight);
	}

	function send() {
		var inp = $(wrapper).find("#ai-page-input");
		var q = inp.val().trim();
		if (!q) return;
		inp.val("");
		add("user", q);
		var t = document.createElement("div");
		t.id = "ai-page-typing";
		t.style.cssText = "font-size:12px;opacity:.7;margin:8px 0;";
		t.textContent = "AI is thinking…";
		msgs.append(t);
		msgs.scrollTop(msgs[0].scrollHeight);
		frappe
			.call({ method: "erp_ai.api.ask", args: { prompt: q, session: session } })
			.then(function (r) {
				t.remove();
				add("ai", r.message.response);
			})
			.catch(function (e) {
				t.remove();
				add("ai", "Sorry, an error: " + (e.message || "try again"));
			});
	}

	$(wrapper).find("#ai-page-send").on("click", send);
	$(wrapper)
		.find("#ai-page-input")
		.on("keydown", function (e) {
			if (e.key === "Enter") send();
		});
	$(wrapper)
		.find(".ai-q")
		.on("click", function () {
			$(wrapper).find("#ai-page-input").val($(this).text());
			send();
		});

	add(
		"ai",
		"Welcome! 👋 I know your ERPNext, Frappe framework and your custom apps. Ask me anything, or use the quick questions above."
	);
};

frappe.pages["ai-assistant"].on_page_show = function () {
	$("#ai-page-input").focus();
};
