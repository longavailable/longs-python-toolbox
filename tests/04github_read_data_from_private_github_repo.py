"""
*2020/08/01
*test for invoking github function
"""
import pandas as pd
from lots.github import *

repositoryName = 'datarepo01'
filePath = 'test/mk_test.txt'

fileUrl = getGithubFileUrl(repositoryName,filePath)
df = pd.read_csv(fileUrl)
print(df)
print('Done.')
