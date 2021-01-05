# -*- coding: utf-8 -*-

import bs4
import requests
from bs4 import SoupStrainer, BeautifulSoup
import urllib3
import csv
import numpy as np
import pandas as pd
import certifi
import re, pickle, sys, os, time
from matplotlib.font_manager import pickle_dump
import html2text 
from decimal import getcontext

parser = html2text.HTML2Text()
parser.body_width = 0
parser.ignore_links = True
parser.single_line_break = True
parser.ignore_emphasis = True
parser.ignore_images = True

input = ''

#soup = BeautifulSoup(input.decode('utf-8').encode('utf-8'), 'html.parser')
#result = parser.handle(' '.join([str(p).decode('utf8') for p in soup.select('.article-text')[0].find_all('p')])).encode('utf-8')
# print result

url = 'Jeremy Herb a Manu Raju, CNN'
# domain = url.replace('https://','').replace('http://','').split('/')[0].replace('www.','')
# if domain.count('.') == 2:
    # domain = domain.split('.', 1)[1]

test = url.split(',')[0].split(' and ')
print test