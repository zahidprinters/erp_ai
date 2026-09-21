#!/usr/bin/env python3
"""Sync the AI Assistant Hub workspace JSON to the database.

Usage:
    bench --site spi.local execute erp_ai.scripts.sync_workspace
"""

import json
import pathlib

import frappe


def execute():
	spec_path = (
		pathlib.Path(__file__).resolve().parent.parent
		/ "erp_ai"
		/ "erp_ai"
		/ "workspace"
		/ "ai_assistant_hub"
		/ "ai_assistant_hub.json"
	)
	spec = json.loads(spec_path.read_text(encoding="utf-8"))
	spec["content"] = json.loads(spec["content"])

	if frappe.db.exists("Workspace", "AI Assistant Hub"):
		ws = frappe.get_doc("Workspace", "AI Assistant Hub")
		for k in ("label", "title", "module", "public", "indicator_color", "sequence_id"):
			if k in spec:
				setattr(ws, k, spec[k])
		ws.content = json.dumps(spec["content"])
		ws.shortcuts = [frappe.new_doc("Workspace Shortcut", d) for d in spec.get("shortcuts", [])]
		ws.save()
		frappe.db.commit()
		print(f"SYNCED: {ws.name} | blocks={len(spec['content'])} shortcuts={len(ws.shortcuts)}")
	else:
		print("NOT FOUND: Workspace 'AI Assistant Hub' not in DB")


if __name__ == "__main__":
	import os

	os.environ["SITE"] = "spi.local"
	os.environ["SITES_DIR"] = "/home/erpnext/frappe-bench/sites"
	os.environ["HOME"] = "/home/erpnext"
	import sys

	sys.path.insert(0, "/home/erpnext/frappe-bench/apps/frappe")
	sys.path.insert(0, "/home/erpnext/frappe-bench/apps/erpnext")
	sys.path.insert(0, "/home/erpnext/frappe-bench/apps/erp_ai")
	frappe.init(site="spi.local", sites_path="/home/erpnext/frappe-bench/sites")
	frappe.connect()
	execute()
	frappe.destroy()

frappe.destroy()
