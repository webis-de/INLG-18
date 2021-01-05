# -*- coding: utf-8 -*-
# read corpus and transform to txt and pickle format
import sys
import unicodedata
import xml.dom.minidom
import os
from os import listdir
import codecs, locale, pickle,nltk
from bs4 import BeautifulSoup
# print sys.getdefaultencoding()
# print sys.stdout.encoding
# sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

_sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')

def getValue(value):
    if value == '':
        return -1
    else:
        return int(value)

def getOriSen(endpoints,sens,rsens,txt):
    p1 = int(endpoints.split(',')[0])
    p2 = int(endpoints.split(',')[1])
    for sen in sens:
        pp1 = int(sen[1].split(',')[0])
        pp2 = int(sen[1].split(',')[1])
        if p1 >= pp1 and p1 <= pp2 and p2 >= pp1 and p2 <= pp2:
            if sen in rsens:
                rsens.remove(sen)
            return txt[pp1:pp2].replace('\n','')

if __name__ == '__main__':

# mpqa 1.2
#     inputTxtDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.1.2/docs/'
#     inputAnnDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.1.2/man_anns/'
#     pickleDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.1.2/pickle/'

# mpqa 2.0    
    inputTxtDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.2.0/docs/'
    inputAnnDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.2.0/man_anns/'
    pickleDir = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.2.0/pickle/'
    mpqalistFile = '/home/penguin/workspace/research-in-progress/text-neutralization/corpus/database.mpqa.2.0/doclist.mpqaOriginalByTopic'
    
    subtypes = ['GATE_direct-subjective','GATE_expressive-subjectivity']
    with codecs.open(mpqalistFile,'r',encoding='utf8') as flist:
        lines = [line.rstrip() for line in flist]
    
    files = []
    for line in lines:
        topic = line.split(' ')[0].split('=')[1]
        filename = line.split(' ')[1].split('=')[1]
        files.append(filename)
        
    subTxtDirs = listdir(inputTxtDir)
    
    annoDic = {}
    with codecs.open(inputTxtDir+'sub.txt','w') as fsub, codecs.open(inputTxtDir+'obj.txt','w') as fobj:
        for txtFile in files:
            with codecs.open(inputTxtDir+txtFile,'rb',encoding='utf8') as ftxt, codecs.open(inputAnnDir+txtFile+'/gateman.mpqa.lre.2.0','r',encoding='utf8') as fann, codecs.open(inputAnnDir+txtFile+'/gatesentences.mpqa.2.0','r',encoding='utf8') as fsen:
                annos = [line.rstrip() for line in fann]
                annoList = []
                for ann in annos:
                    if len(ann.split('\t')) == 5:
                        parts = ann.split('\t')
                        aid = int(parts[0])
                        endpoints = parts[1]
                        atype = parts[2]
                        asub = parts[3]
                        aatt = parts[4]
                        annoList.append((aid,endpoints,atype,asub,aatt))
                
                txt = ftxt.read()
                
                sens = [line.rstrip() for line in fsen]
                senList = []
                for sen in sens:
                    if len(sen.split('\t')) == 4:
                        parts = sen.split('\t')
                        sid = int(parts[0])
                        endpoints = parts[1]
                        stype = parts[2]
                        ssub = parts[3]
                        senList.append((sid,endpoints,stype,ssub))
                resList = senList[:] # copy this list
                for (aid,endpoints,atype,asub,aatt) in annoList:
                    target = txt[int(endpoints.split(',')[0]):int(endpoints.split(',')[1])].replace('\n','')
                    if len(target) < 1:
                        continue
                    if asub in subtypes: # a sub candidate sentence
                        atts = aatt.split(' ')
                        oriSen = getOriSen(endpoints,senList,resList,txt)
#                         print aid,endpoints,atype,asub,aatt
#                         print target
#                         print txtFile
#                         print oriSen
#                         raw_input("Press Enter to continue...")                        
                        if asub == 'GATE_direct-subjective':
                            issub = True
                            for att in atts:
                                atttype = att.split('=')[0]
                                if atttype == 'intensity':
                                    attvalue = att.split('=')[1]
                                    if attvalue not in ['low','neutral']:
                                        issub = True        
                                    else:
                                        issub = False
                                if atttype == 'insubstantial':
                                    issub = False
                            if issub:
                                fsub.write(target + '\t' + oriSen + '\t' + txtFile + '\t' + aatt + '\n')
                            else:
                                fobj.write(target + '\t' + oriSen + '\t' + txtFile + '\t' + aatt + '\n')
                        else:
                            for att in atts:
                                atttype = att.split('=')[0]
                                if atttype == 'intensity':
                                    attvalue = att.split('=')[1]
                                    if attvalue != 'low':
                                        try:
                                            fsub.write(target + '\t' + oriSen + '\t' + txtFile + '\t' + aatt + '\n')
                                        except:
                                            print txt[722:745]
                                            print aid,endpoints,atype,asub,aatt
                                            print target
                                            print txtFile
                                            print oriSen
                                    else:
                                        fobj.write(target + '\t' + oriSen + '\t' + txtFile + '\t' + aatt + '\n')
                for (sid,endpoints,stype,ssub) in resList:
                    resStart = int(endpoints.split(',')[0])
                    resEnd = int(endpoints.split(',')[1])
                    fobj.write('' + '\t' + txt[resStart:resEnd].replace('\n','') + '\t' + txtFile + '\t' + '' + '\n')
#                 print aid,endpoints,atype,asub,amisc
#                 print target
#                 print txtFile
#                 raw_input("Press Enter to continue...")
                                    
#     artLevelFile = inputDir + 'news.csv'
#     senLevelFile = inputDir + 'sentences.csv'
# 
#     maxScore = 5
    
# part 1 read data

#     with codecs.open(senLevelFile, 'r',encoding='mac_roman') as f:
#         lines = [line.rstrip('\r') for line in f]
#     
#     sens = []
#     for i in range(maxScore+1):
#         sens.append({})
#     
#     for line in lines:
#         parts = line.split('\t')
#         print parts
#         if parts[0] != 'id': # not first line
#             nid         = int(parts[0])
#             news_name   = parts[1]
#             sen         = parts[2]
#             subScore    = parts[3]
#             posScore    = parts[4]
#             negScore    = parts[5]
#             ign         = parts[6]
#             confidence  = parts[7]
#             if (ign == '' or 'i' not in ign.lower().split()) and subScore != '':
#                 with codecs.open(inputDir + subScore + '.txt', 'a', encoding = 'utf8') as fscore:
#                     fscore.write(news_name + '\t' + sen + '\n')
#                 sens[int(subScore)][sen] = [nid,news_name,getValue(posScore),getValue(negScore),getValue(confidence)]
#     
#     with open(pickleDir + 'sens.pickle','w') as fpickle:
#         pickle.dump(sens, fpickle)

#     with open(pickleDir + 'sens.pickle','r') as fpickle:
#         sens = pickle.load(fpickle)        
#     
#     for subsens in sens:
#         print len(subsens)
                