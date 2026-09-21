#!/usr/bin/env python3
"""Commit-message check: conventional subject line.

Used as a pre-commit ``commit-msg`` hook so the history stays machine-readable
(the CHANGELOG and release notes are built from it).

Usage (pre-commit calls this with the commit message file path)::

    python.github / scripts / check_commit_msg.py.git / COMMIT_EDITMSG

Accepted subject::

    <type>[(scope)]: <subject>

``type`` is one of feat, fix, ci, docs, chore, test, refactor, perf, build,
style, revert. Merge commits and fixup!/squash! commits are exempt, and a body
is free-form.
"""

import re
import sys

ALLOWED_TYPES = (
	"feat",
	"fix",
	"ci",
	"docs",
	"chore",
	"test",
	"refactor",
	"perf",
	"build",
	"style",
	"revert",
)
SUBJECT_RE = re.compile(r"^(%s)(\([^)]+\))?!?: .{3,}" % "|".join(ALLOWED_TYPES))
MAX_SUBJECT = 100
EXEMPT_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ")


def check(message: str) -> list:
	"""Return a list of problem strings (empty when the message is fine)."""
	lines = [line for line in message.splitlines() if not line.startswith("#")]
	while lines and not lines[0].strip():
		lines.pop(0)
	if not lines:
		return ["empty commit message"]

	subject = lines[0].rstrip()
	if subject.startswith(EXEMPT_PREFIXES):
		return []

	problems = []
	if not SUBJECT_RE.match(subject):
		problems.append(
			"subject must look like '<type>[(scope)]: <subject>' with type in %s\n"
			"  got: %s" % ("/".join(ALLOWED_TYPES), subject)
		)
	if len(subject) > MAX_SUBJECT:
		problems.append("subject is %d chars (max %d)" % (len(subject), MAX_SUBJECT))
	return problems


def main(argv):
	if len(argv) < 2:
		print("usage: check_commit_msg.py <commit-message-file>")
		return 2
	with open(argv[1], encoding="utf-8", errors="replace") as handle:
		message = handle.read()
	problems = check(message)
	if problems:
		print("Commit message rejected:")
		for problem in problems:
			print("  - %s" % problem)
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))
