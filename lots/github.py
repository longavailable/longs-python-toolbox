# -*- coding: utf-8 -*-
"""
* Updated on 2020/08/01
* python3 + Github
**
* Get a personal access token and set it as environment variable 'export GITHUB_API_TOKEN=""' firstly
"""

import os
from github import Github

token = os.environ['GITHUB_API_TOKEN'] #Personal access tokens
g = Github(token).get_user()

'''
request the download url of file from github repository
Note:For private repositories, these links are temporary and expire after five minutes
'''
def getGithubFileUrl(repoName,filePath):
	return g.get_repo(repoName).get_contents(filePath).download_url

def grepoExist(repoName):
	#gRepos = g.get_user().get_repos()
	gRepos = g.get_repos()
	repos = [gRepo.name for gRepo in gRepos]
	if repoName in repos:
		return True
	else:
		return False

#check if a file exits in github repository
#replaced by gfileInfo function
def gfileExist(repoName,filename,filePath='./'):
	if not grepoExist(repoName):
		return False
	else:
		gFiles = g.get_repo(repoName).get_contents(filePath)
		files = [gFile.name for gFile in gFiles]
		if filename in files:
			return True
		else:
			return False

#return a gFile's information, or False
def gfileInfo(repoName,filename,filePath='./'):
	if not grepoExist(repoName):
		return False
	else:
		gFiles = g.get_repo(repoName).get_contents(filePath)
		for gFile in gFiles:
			if gFile.name == filename:
				return gFile
		return False