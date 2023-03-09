# -*- coding: utf-8 -*-
"""
* Updated on 2023/03/09
* python3 + gmail
"""

import smtplib
from datetime import datetime
import re
import requests

mail_server_user = os.environ['MAIL_SERVER_USER']
mail_server_password = os.environ['MAIL_SERVER_PASSWORD']
mail_to_user = os.environ['MAILTO']

def serverProviderUrl(user=mail_server_user):
	return 'https://' + user.split('@')[-1]

def mail_server(user=mail_server_user):
	"""smtp service, port 25
	"""
	return 'smtp.' + user.split('@')[-1], 25

def mailme(text, user=mail_server_user, password=mail_server_password, mailto=mail_to_user):
	sent_from = user
	sent_to = mailto
	subject = 'Python: ' + str(text)
	email_text = ( 'From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n%s' 
					% (	
							sent_from, 							#from
							", ".join(sent_to), 					#to list
							subject, 								#subject
							'Done at %s' % datetime.now().strftime('%y-%m-%d %H:%M:%S')		#body
						) 
					)
	
	try:
		requests.get(serverProviderUrl(user))
	except:
		from .util import proxy
		proxy()
	
	host, port = mail_server(user)
	try:
		server = smtplib.SMTP_SSL(host, port)
		server.ehlo()
		server.login(user, password)
		server.sendmail(sent_from, sent_to, email_text)
		server.close()

		print('Succeeded -- mailme -- sent at %s' % datetime.now().strftime('%y-%m-%d %H:%M:%S'))
	except:
		print('Failed -- mailme')