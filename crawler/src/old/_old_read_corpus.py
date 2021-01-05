# -*- coding: utf-8 -*-
import sys
import unicodedata
import xml.dom.minidom
import os
import codecs
import locale
from bs4 import BeautifulSoup
# print sys.getdefaultencoding()
# print sys.stdout.encoding
# sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
if __name__ == '__main__':

    inputDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/corpus-yahoo-news-quality/cleaned/cleaned/v08/'
    filename = inputDir + '10-surprising-things-put-r-sum-154737905.xmi'
    filename = inputDir + 'sentences.csv'
        
#     with codecs.open(filename, 'r',encoding='mac_roman') as f:
    with codecs.open(filename, 'r',encoding='mac_roman') as f:
        lines = [line for line in f]
    
    print lines[51]
    print lines[52]
    print lines[53]
    print lines[54]