import bs4
from bs4 import SoupStrainer, BeautifulSoup
import urllib3
import csv
import numpy as np
import pandas as pd
import certifi
import re

asurl = "http://www.allsides.com/bias/bias-ratings?field_news_source_type_tid=2&field_news_bias_nid=1&field_featured_bias_rating_value=1&title="

def get_soup(url):
    '''
    Returns BeautifulSoup object of a given url.
    Input: url (str).
    Output: BeautifulSoup object.
    '''
    pm = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    html = pm.urlopen(url=url, method="GET").data
    return BeautifulSoup(html, "lxml")

def get_source_url(url):
    '''
    Returns the source name tag of a news source on the AllSides bias ratings page.
    Input: url (str).
    Output: urlkey (str) = source name tag retrieved with regex.
    '''
#     print 'url',url
    urlsoup = get_soup(url)
    urltag = urlsoup.find("div", class_="source-image")
#     print 'url',urltag 
    url = urltag.find("a")["href"].strip()
#     print 'url',url
    urlkey = re.search(r"(?<=://)(www[.])?(.+)([a-z/]*\.[a-z/]*)", url)
#     print urlkey
    urlkey = urlkey.group(2).lower()
    return urlkey

def source_info(soup):
    '''
    Creates a dictionary of news sources, with values on bias rating, url, and
    the community agree/disagree ratio on the respective bias ratings.
    Input: soup (BeautifulSoup object) = soup of the AllSides bias ratings page.
    Output: info (dict of tuples) = dictionary of news source information.
    note: the url is no longer available in allsides.com
    '''
    odd = soup.find_all("tr", class_="odd")
    odd = [(o, o.find_next("div", class_="rate-details")) for o in odd]
    even = soup.find_all("tr", class_="even")
    even = [(e, e.find_next("div", class_="rate-details")) for e in even]
    tags = [None]*(len(odd) + len(even))
    tags[::2] = odd
    tags[1::2] = even

    info = {}

    for t in tags:
        bias = ""
        agree = int(t[1].find("span", class_="agree").text)
        disagree = int(t[1].find("span", class_="disagree").text)
        alist = t[0].find_all("a", href=True)
        source_name = alist[0].contents[0]
        bias = alist[1]["href"].split('/')[-1]
        
        if source_name not in info:
            info[source_name] = (bias, agree, disagree, agree/float(disagree))
    print info
    return info

def go(dataDir):
    '''
    Prints the source info as a pandas dataframe and writes to a csv.
    '''
    soup = get_soup(asurl)
    info = source_info(soup)
    labels = ["Source Name", "Bias", "Agree", "Disagree", "Ratio"]
    df = pd.DataFrame(info, index=labels[1:]).T
    df.columns.name = "News Source"
    print(df)

    with open(dataDir + "allsides_bias.csv", "w") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(labels)
        for key in sorted(info.keys()):
            row = [key]
            row += [val for val in info[key]]
            writer.writerow(row)


if __name__ == "__main__":
    dataDir = '../data/'
    go(dataDir)
    print("\ncreated as.csv")
    