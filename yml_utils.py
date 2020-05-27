#!/usr/bin/env python



import re
import sys
import base64
import requests

from apikey import APIKEY

class Advisory:
	def __init__(self, bugJSON, advisoryText):
		self.id = bugJSON['id']
		self.severity = getSeverity(bugJSON)
		advisory_lines = advisoryText.split("\n")
		self.cve = bugJSON['alias'] if bugJSON['alias'] else ""
		self.title = advisory_lines[0].strip()
		self.reporter = advisory_lines[1].strip() #cleanUpRealName(bugJSON['creator_details']['real_name'])
		self.description = "\n".join(advisory_lines[2:]).strip()
	def pprint(self):
		print(self.id)
		print("\t", self.severity)
		print("\t", self.title)
		print("\t", self.reporter)
		print("\t", self.description)
		print("\t")
	def getCVE(self):
		if self.cve:
			return self.cve
		return "CVE-FIXME-YYY"
	def getTitle(self):
		if ":" in self.title:
			return "'" + self.title + "'"
		return self.title

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def cleanUpRealName(name):
	name = re.sub(" \[:[^\]]+\]", "", name)
	name = re.sub(" \(:[^\)]+\)", "", name)
	name = re.sub(" \(needinfo[^\)]+\)", "", name)
 	name = re.sub(" \(ni [^\)]+\)", "", name)
	return name

def getSeverity(bugJSON):
	severity = None
	for k in bugJSON['keywords']:
		if k in ["sec-critical", "sec-high", "sec-moderate", "sec-low"]:
			thisSev = k.replace("sec-", "")
			if severity is not None:
				severity = getMaxSeverity(severity, thisSev)
			else:
				severity = thisSev
	if severity is None:
		raise Exception(str(bugJSON['id']) + " is missing a sec keyword")
	return severity

def sortAdvisories(advisories):
	for a in advisories:
		if a.severity == "critical":
			yield a
	for a in advisories:
		if a.severity == "high":
			yield a
	for a in advisories:
		if a.severity == "moderate":
			yield a
	for a in advisories:
		if a.severity == "low":
			yield a

def doBugRequest(link):
	r = requests.get(link)
	bugs = r.json()
	return bugs['bugs']

def getAdvisoryAttachment(bugid):
	link = "https://bugzilla.mozilla.org/rest/bug/" + str(bugid) + "/attachment?api_key=" + APIKEY
	r = requests.get(link)
	attachments = r.json()['bugs'][str(bugid)]
	advisory = None
	for a in attachments:
		if a['description'] == "advisory.txt" and not a['is_obsolete']:
			if advisory is not None:
				raise Exception(str(bugid) + " has two advisory.txt attachments")
			advisory = base64.b64decode(a['data'])
	if advisory is None:
		raise Exception(str(bugid) + " is missing an advisory.txt attachment")
	return advisory

def getMaxSeverity(current, this):
	if this == "critical":
		return "critical"
	elif current in ["low", "moderate"] and this == "high":
		return "high"
	elif current in ["low"] and this == "moderate":
		return "moderate"
	return current

def sanityCheckBugs(bugs, require_cves=False):
	retvalue = True
	for b in bugs:
		bugid = b['id']
		# Check for CVE
		if require_cves and not b['alias']:
			eprint(bugid, "is missing a CVE identified. Please contact Tom Ritter (cc Dan Veditz) to have one assigned.")
			retvalue = False

		# Check for severity keywords
		try:
			getSeverity(b)
		except Exception as e:
			eprint(bugid, "seems to have some problem with the severity. If you can resolve it, please do, otherwise contact Tom Ritter (and/or Dan Veditz)")
			eprint("Exception:")
			eprint(e)
			retvalue = False

		# Check if the bug is fixed or not
		if b['status'] != "RESOLVED" and b['status'] != "VERIFIED":
			eprint(bugid, "is not marked as fixed, but is marked for this version")
			retvalue = False

		# Check if the bug has an advisory
		try:
			getAdvisoryAttachment(bugid)
		except Exception as e:
			eprint(bugid, "might be missing an advisory attachment. Please create an attachment named advisory.txt as described here: https://wiki.mozilla.org/Security/Firefox/Security_Bug_Life_Cycle/Security_Advisories#Write_the_advisories")
			eprint("Exception:")
			eprint(e)
			retvalue = False

	return retvalue