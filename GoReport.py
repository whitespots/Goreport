#!/usr/bin/env python3
"""
Script for GoPhish's API. When making requests, simply append the
api_key=[API_KEY] as a GET parameter to authorize yourself to the API.

GET /api/campaigns/?api_key=
"""

import time
import requests
import sys
import json
import re
import csv
from datetime import datetime
from user_agents import parse
from collections import Counter
from geoip import open_database
db = open_database("GeoLite2-City.mmdb")  #  Replace with name/location of your database file

API_KEY = "<Your API Key>"
CAM_ID = sys.argv[1] # Campaign ID for the report
GP_URL = sys.argv[2] # IP and Port for the GoPhish server, e.g. loclahost:8080

def lookupip(ip):
	"""
	Open the GeoLite database and lookup the provided IP address
	"""
	with open_database('GeoLite2-City.mmdb') as db:
		match = db.lookup(ip)
		if match is not None:
			return match.location


def getplace(lat, lon):
	"""
	Use Google's Maps API to collect GeoIP info
	"""
	url = "http://maps.googleapis.com/maps/api/geocode/json?"
	url += "latlng={},{}&sensor=false".format(lat, lon)
	v = requests.get(url)
	j = v.json()
	components = j['results'][0]['address_components']
	country = town = None
	for c in components:
		if "country" in c['types']:
			country = c['long_name']
		if "locality" in c['types']:
			town = c['long_name']
		if "administrative_area_level_1" in c['types']:
			state = c['long_name']
	print("{}, {}, {}".format(town, state, country))
	return "{}, {}, {}".format(town, state, country)


def get_phish_details(campaign_id, api, url):
	"""
	Return structured dictionary data for given GoPhish campaign ID and API key
	"""
	url = "https://{}/api/campaigns/{}/?api_key={}".format(url, campaign_id, api)
	r = requests.get(url, verify=False)
	details = r.json()
	results = details['results']
	timeline = details['timeline']
	smtp = details['smtp']

	try:
		output = {
			"campaign_id": details ['id'],
			"campaign_name": details['name'],
			"status": details['status'],
			"created": details['created_date'],
			"completed": details['completed_date'],
			"from_address": smtp['from_address'],
			"email_template": details['template']['name'],
			"landing_page": details['page']['name'],
			"email_subject": details['template']['subject'],
			"attachment": details['template']['attachments'][0]['name'],
			"url": details['url']
		}
	except:
		output = {
			"campaign_id": details ['id'],
			"campaign_name": details['name'],
			"status": details['status'],
			"created": details['created_date'],
			"completed": details['completed_date'],
			"from_address": smtp['from_address'],
			"email_template": details['template']['name'],
			"landing_page": details['page']['name'],
			"email_subject": details['template']['subject'],
			"url": details['url']
		}

	x = 0
	data = {"results": []}
	lst = []
	for r in results:
		item = {
			"user_id": results[x]['id'],
			"user_name": results[x]['first_name'] + " " + results[x]['last_name'],
			"user_email": results[x]['email'],
			"user_status": results[x]['status'],
			"user_ip": results[x]['ip'],
			"user_latitude": results[x]['latitude'],
			"user_longitude": results[x]['longitude']
		}
		lst.append(item)
		x += 1

	data["results"] = lst

	x = 0
	events = {"timeline": []}
	lst =[]
	for e in timeline:
		event = timeline[x]['message']

		if event in ["Campaign Created", "Email Sent", "Email Opened"]:
			item = {
				"timestamp": timeline[x]['time'],
				"event": timeline[x]['message'],
				"email": timeline[x]['email']
			}
		if event in ["Clicked Link", "Submitted Data"]:
			item = {
				"timestamp": timeline[x]['time'],
				"event": timeline[x]['message'],
				"email": timeline[x]['email'],
				"payload": details['timeline'][x]['details']
			}
		lst.append(item)
		x += 1

	events["timeline"] = lst

	output.update(data)
	output.update(events)

	return output


phish = get_phish_details(CAM_ID, API_KEY, GP_URL)

"""
TARGET DATA AND RESULTS
"""

# Find out who opened/clicked/submitted
temp_opened = []
temp_clicked = []
temp_phished = []
for e in phish['timeline']:
	if e['event'] == "Email Opened":
		#print("Status: %s" % e['event'])
		#print("Target: %s" % e['email'])
		temp_opened.append(e['email'])
	if e['event'] == "Clicked Link":
		#print("Status: %s" % e['event'])
		#print("Target: %s" % e['email'])
		temp_clicked.append(e['email'])
	if e['event'] == "Submitted Data":
		#print("Status: %s" % e['event'])
		#print("Target: %s" % e['email'])
		temp_phished.append(e['email'])

opened = list(set(temp_opened))
clicked = list(set(temp_clicked))
phished = list(set(temp_phished))

# Create list of targets based on who was sent an email
targets = []
for target in phish['results']:
	targets.append(target['user_email'])
targets.sort() # Make list alphabetical

# Get the timestamp of the first Email Sent event
for e in phish['timeline']:
	if e['event'] == "Email Sent":
		temp = e['timestamp'].split('T')
		started = temp[0] + " " + temp[1].split('.')[0]
		start_date = temp[0]
		start_date = datetime.strptime(start_date, "%Y-%m-%d")
		start_date = start_date.strftime("%B %d, %Y")
		start_time = temp[1].split('.')[0]
		break

temp = phish['created'].split('T')
created = temp[0] + " " + temp[1].split('.')[0]

temp = phish['completed'].split('T')
completed = temp[0] + " " + temp[1].split('.')[0]

csv_report = "Results - GoPhish Campaign {} {}.csv".format(CAM_ID, phish['email_template']

"""
CAMPAIGN SUMMARY INFO
"""
with open(csv_report, 'w', newline='') as csvfile:
	writer = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
	writer.writerow("Campaign Results Summary")

	try:
		attachment = phish['attachment']
	except:
		attachment = "None"

	writer.writerow("Created", created)
	writer.writerow("Started", start_date, start_time)
	writer.writerow("Completed", completed)

	writer.writerow("What was the subject, From, and email content?")
	writer.writerow("From", phish['from_address'])
	writer.writerow("Subject", phish['email_subject'])
	writer.writerow("URL", phish['url'])
	writer.writerow("Attachment", attachment)

	writer.writerow("What were the results?")
	writer.writerow("Total Targets", len(targets))
	writer.writerow("Opened", len(opened))
	writer.writerow("Clicked", len(clicked))
	writer.writerow("Entered Data", len(phished))

"""
SUMMARY
"""

	writer.writerow("The table below summarizes who opened and clicked on emails sent in this campaign.")
	writer.writerow("Email", "Open", "Click", "Phish")

	# Add targets to the results table
	for target in targets:
		result = target

		if target in opened:
			result += "Y"
		else:
			result += "N"

		if target in clicked:
			result += "Y"
		else:
			result += "N"

		if target in phished:
			result += "Y"
		else:
			result += "N"

		writer.writerow(result)

"""
DETAILED RESULTS
"""

	# Lists for browser, OS, and location tables
	operating_systems = []
	browsers = []
	locations = []

	# If they are in targets[], then they get a spot here
	for target in targets:
		writer.writerow(target)

		# Get the timestamp of Email sent for target
		for e in phish['timeline']:
			if e['event'] == "Email Sent" and e['email'] == target:
				temp = e['timestamp']
				reg = re.compile(r'\d{4}-\d{2}-\d{2}')
				sent_date = re.search(reg, temp).group()
				sent_date = datetime.strptime(sent_date, "%Y-%m-%d")
				sent_date = sent_date.strftime("%B %d, %Y")
				reg = re.compile(ur'[0-9]{2}:[0-9]{2}:[0-9]{2}')
				sent_time = re.search(reg, temp).group()

				writer.writerow("Sent on {} at {}".format(sent_date, sent_time))
				"""Example: 2016-08-12T10:39:34.251188714-04:00 """

		if target in opened:
			writer.writerow("Email Previews")
			writer.writerow("Time")

			for e in phish['timeline']:
				if e['event'] == "Email Opened" and e['email'] == target:
					temp = e['timestamp'].split('T')
					writer.writerow(temp[0] + " " + temp[1].split('.')[0])

		if target in clicked:
			writer.writerow("Email Link Clicked")
			writer.writerow("Time", "IP", "City", "Browser", "Operating System")

			for e in phish['timeline']:
				if e['event'] == "Clicked Link" and e['email'] == target:
					for r in phish['results']:
						if r['user_email'] == target:
							temp = e['timestamp'].split('T')
							result = temp[0] + " " + temp[1].split('.')[0]

							result += r['user_ip']

							#coordinates = str(r['user_latitude']) + ", " + str(r['user_longitude'])
							#coordinates = getplace(str(r['user_latitude']), str(r['user_longitude']))
							coordinates = lookupip(r['user_ip'])
							coordinates = getplace(coordinates[0], coordinates[1])
							result += coordinates
							locations.append(coordinates)

							raw_payload = e['payload']
							browser_payload = re.search(r'(?<=browser":{)(.*?)(?=}})', raw_payload)
							browser_payload = browser_payload.group().split(',', 1)[1]

							user_agent = parse(browser_payload)
							browser_details = user_agent.browser.family + " " + user_agent.browser.version_string
							result += browser_details
							browsers.append(browser_details)

							os_details = user_agent.os.family + " " + user_agent.os.version_string
							result += os_details
							operating_systems.append(os_details)

		if target in phished:
			writer.writerow("Phishgate Data Captured")
			writer.writerow("Time", "IP", "City", "Browser", "Operating System", "Data Captured")

			for e in phish['timeline']:
				if e['event'] == "Submitted Data" and e['email'] == target:
					for r in phish['results']:
						if r['user_email'] == target:
							temp = e['timestamp'].split('T')
							result += temp[0] + " " + temp[1].split('.')[0]

							result += r['user_ip']

							coordinates = str(r['user_latitude']) + ", " + str(r['user_longitude'])
							result += coordinates
							locations.append(coordinates)

							raw_payload = e['payload']
							browser_payload = re.search(r'(?<=browser":{)(.*?)(?=}})', raw_payload)
							browser_payload = browser_payload.group().split(',', 1)[1]

							user_agent = parse(browser_payload)

							# Leaving the following here as examples of this library's options

							# user_agent.browser  # Returns Browser(family=u'Mobile Safari', version=(5, 1), version_string='5.1')
							# user_agent.browser.family  # Returns 'Mobile Safari'
							# user_agent.browser.version  # Returns (5, 1)
							# user_agent.browser.version_string   # Returns '5.1'

							# Accessing user agent's operating system properties
							# user_agent.os  # Returns OperatingSystem(family=u'iOS', version=(5, 1), version_string='5.1')
							# user_agent.os.family  # Returns 'iOS'
							# user_agent.os.version  # Returns (5, 1)
							# user_agent.os.version_string  # Returns '5.1'

							# Accessing user agent's device properties
							# user_agent.device  # Returns Device(family='iPhone')
							# user_agent.device.family  # Returns 'iPhone'

							browser_details = user_agent.browser.family + " " + user_agent.browser.version_string
							result += browser_details
							browsers.append(browser_details)

							os_details = user_agent.os.family + " " + user_agent.os.version_string
							result += os_details
							operating_systems.append(os_details)

							data_payload = re.search(r'(?<=payload":{)(.*?)(?=},"browser)', raw_payload)
							result += data_payload.group()

"""
TOP BROWSERS AND GEO IP
"""

	unique_browsers = Counter(browsers).keys()
	seen_browsers = Counter(browsers).values()

	unique_os = Counter(operating_systems).keys()
	seen_os = Counter(operating_systems).values()

	unique_locs = Counter(locations).keys()
	seen_locs = Counter(locations).values()

	writer.writerow("The following table shows the top browsers used to view this campaign.")
	writer.writerow("Browser", "Seen")
	for b in unique_browsers:
		writer.writerow(b)

	for b in seen_browsers:
		writer.writerow(str(b))

	writer.writerow("The following table shows the top operating systems used to view this campaign.")
	writer.writerow("Operating System", "Seen")

	for b in unique_os:
		writer.writerow(b)

	for b in seen_os:
		writer.writerow(str(b))

	writer.writerow("The following table shows the top cities.")
	writer.writerow("Location", "Visits")

	for b in unique_locs:
		writer.writerow(b)

	for b in seen_locs:
		writer.writerow(str(b))