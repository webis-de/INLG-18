# -*- coding: utf-8 -*-
# read corpus and transform to txt and pickle format
import sys
import unicodedata
import xml.dom.minidom
import os
import codecs, locale
import pickle
from bs4 import BeautifulSoup
# print sys.getdefaultencoding()
# print sys.stdout.encoding
# sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

def getValue(value):
    if value == '':
        return -1
    else:
        return int(value)

if __name__ == '__main__':

    inputDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/corpus-yahoo-news-quality/cleaned/cleaned/v08/'
    pickleDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/corpus-yahoo-news-quality/pickle/'
    artLevelFile = inputDir + 'news.csv'
    senLevelFile = inputDir + 'sentences.csv'

    maxScore = 5
    
# part 1 read data

    with codecs.open(senLevelFile, 'r',encoding='mac_roman') as f:
        lines = [line.rstrip('\r') for line in f]
     
    sens = []
    for i in range(maxScore+1):
        sens.append({})
     
    for line in lines:
        parts = line.split('\t')
        print parts
        if parts[0] != 'id': # not first line
            nid         = int(parts[0])
            news_name   = parts[1]
            sen         = parts[2]
            subScore    = parts[3]
            posScore    = parts[4]
            negScore    = parts[5]
            ign         = parts[6]
            confidence  = parts[7]
            if (ign == '' or 'i' not in ign.lower().split()) and subScore != '':
                with codecs.open(inputDir + subScore + '.txt', 'a', encoding = 'utf8') as fscore:
                    fscore.write(news_name + '\t' + sen + '\n')
                sens[int(subScore)][sen] = [nid,news_name,getValue(posScore),getValue(negScore),getValue(confidence)]
     
    with open(pickleDir + 'sens.pickle','w') as fpickle:
        pickle.dump(sens, fpickle)

    with open(pickleDir + 'sens.pickle','r') as fpickle:
        sens = pickle.load(fpickle)        
    
    for subsens in sens:
        print len(subsens)
                