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
import html2text 
from decimal import getcontext
import random
import datetime
import json
import dateparser
from selenium import webdriver
from selenium.webdriver.common.by import By
from newspaper import Article

parser = html2text.HTML2Text()
parser.body_width = 0
parser.ignore_links = True
parser.single_line_break = True
parser.ignore_emphasis = True
parser.ignore_images = True
# todo:
# check unicode: this option is useless?
# parser.unicode_snob = True
# title: all uppercase?
# author: only first later uppercase?
# note
# 1. some articles still have multiple line breaks: because they are some special headings

base_url = 'https://www.allsides.com'
input_dir = '../misc/'
output_dir = '../results/'
logs_dir = output_dir + 'logs/'
output_pickle_dir = output_dir + "pickle/"

output_df_path = output_dir + "allsides-df.csv"

storyItems = []
newskeys = {}
fetched_from_cache = 0
fetched_from_error_cache = 0
new_fetched = 0
story_counter = 1
errors_subs = 0
errors_new = 0
wayback_success = 0
wayback_fail = 0

# Get all user agents
user_agents = []
with open(input_dir + "user-agents.txt") as file:
    for line in file: 
        line = line.strip()
        user_agents.append(line)
file.close()

def convert_to_df(data):
    documents = ""
    stories = data[0]

    all_stories = []
    all_stories_counter = 0
    
    cols = [
        "title",
        "time",
        "bias",
        "grouped_with",
        "content"
    ]

    for story_grouped in stories:
        grouped_with = []
        grouped_counter = all_stories_counter
        for x in story_grouped:
            grouped_with.append(grouped_counter)
            grouped_counter += 1

        for story in story_grouped:
            story_misc = story[6] # author, time

            story_time = ""
            if "time" in story_misc:
                if story_misc["time"] != None and story_misc["time"] != "None":
                    story_time = story_misc["time"]

            story_bias = story[0].replace("From the", "")
            story_content = story[5]
            story_title = story[4]
            temp_grouped_with = deepcopy(grouped_with)
            temp_grouped_with.remove(all_stories_counter)

            # add to our list of dictionaries
            all_stories.append(
                {
                    "title": story_title,
                    "time": story_time,
                    "bias": story_bias,
                    "content": story_content,
                    "grouped_with": temp_grouped_with
                }
            )

            all_stories_counter += 1

    documents = pd.DataFrame(all_stories, columns=cols)
    
    return documents


def removeHeading(text):
    r = text.replace('### ','') # h3 heading
    r = r.replace('## ','') # h2 heading
    r = r.replace('# ','') # h1 heading
    return r

def removeListing(text):
    r = ''
    
    if len(text.split('\n')) > 0:
        r = '\n'.join([t.replace('* ','').strip() for t in text.split('\n')])
        if len(r)<1:
            r = text
        else:
            if r[-1] == '*':
                r = r[:-1]
    else:
        r = text
        
    return r

def removeEmail(text):
    r = text.replace('[email protected]','<EMAIL>')
    return r

def nytseparate(text):
    r = text.replace('____\n','')
    return r

def get_response_content(response):
    return str(response.text)

def get_html(url):
    global user_agents
    response = ""
    
    try:
        response = requests.get(
            url,
            allow_redirects = True,
            headers = {
                'User-Agent': random.choice(user_agents),
                "Connection" : "close"
            }
        )
    except requests.exceptions.Timeout:
        return False
    except requests.exceptions.TooManyRedirects:
        return False
    except requests.exceptions.RequestException as e:
        return False

    return str(response.text)

def do_request(url):
    global user_agents
    response = ""
    
    try:
        response = requests.get(
            url,
            allow_redirects = True,
            headers = {
                'User-Agent': random.choice(user_agents),
                "Connection" : "close"
            }
        )
    except requests.exceptions.Timeout:
        return False
    except requests.exceptions.TooManyRedirects:
        return False
    except requests.exceptions.RequestException as e:
        return False

    return response

def bypass_cookies_consent(url, element_css):
    url_status = False
    soup = ''
    redirected_url_source = ''
    
    # simulate button click
    print("---- Bypassing cookies consent page")

    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    driver = webdriver.Chrome(chrome_options=chrome_options)

    driver.get(url)
    destination_page_link = driver.find_element_by_css_selector(element_css)
    if destination_page_link:
        destination_page_link.click()

        # wait for the new page
        time.sleep(3)

        # the redirected link
        redirected_url_source = driver.page_source
    
    if redirected_url_source:
        try:
            print("---- Success")
            soup = BeautifulSoup(redirected_url_source.encode('utf-8'), 'html.parser')
            url_status = True
        except:
            print("---- Fail")
            url_status = False
    
    return url_status, soup

def soup_is_string(soup_object):
    is_string = False
    if isinstance(soup_object, str):
        is_string = True
        print ('Wayback machine - no snapshot of url found')
    return is_string
    
def try_wayback_machine(url):
    
    soup = ''
    
    global user_agents
    
    base_url = "http://archive.org/wayback/available?url="
    
    print ("Checking Wayback Machine ...")
    resp = requests.get(
        base_url + url,
        headers = {
            'User-Agent': random.choice(user_agents),
            "Connection" : "close"
        }
    )
    
    data = json.loads(resp.text)

    if len(data['archived_snapshots']) > 0:
        snapshots = data['archived_snapshots']
        if len(snapshots['closest']) > 0 :
            closest = snapshots['closest']
            if closest['available'] == True and len(closest['url']) > 0:
                snapshot = closest['url']

                # request
                response = do_request(snapshot)
                if response:
                    soup = BeautifulSoup(get_response_content(response), 'html.parser')
                
    return soup

def waybackCheck(url, title, body):
    global wayback_success
    global wayback_fail
    
    success = True if body.strip() != '' else False;
        
    if success == True:
        with open(logs_dir + 'wayback-machine-success.txt', 'a+') as f:
            wayback_success = wayback_success + 1
            f.write(str(url) + '\n')
        f.close()
        
    else:
        with open(logs_dir + 'wayback-machine-fail.txt', 'a+') as ff:
            wayback_fail = wayback_fail + 1
            ff.write(str(url) + '\n')
        ff.close()

def read_config(key):
    settings = {}
    path = "../config/" + str(key) + ".txt"

    if os.path.exists(path):
        f = open(path, "r")
        for line in f.readlines():
            line_p = line.strip().split("\t")
            if len(line_p) == 2:
                if line_p[1].strip() != '':
                    # values can be multiple separated by ;
                    settings_value = line_p[1].strip().split(";")
                    settings[line_p[0].strip()] = settings_value
        f.close()

    return settings

def process_url(config_key, url):
    title = ''
    body = ''
    misc = {
        'time': '',
        'author': []
    }
    # request
    soup = ''
    tried_wayback = False
    url_status = True
    url_status_code = ""

    
    # Parse using the newspaper library
    article = Article(url)
    article.download()
    article.parse()

    if article.text and article.title:
        if article.publish_date:
            misc["time"] = article.publish_date.strftime("%Y-%d-%m %H:%M:%S")

        if len(article.authors) > 0:
            misc["author"] = article.authors

        return article.title.strip(), article.text.strip(), misc, url_status, url_status_code

    # Parse using local config files

    # load config
    config = read_config(config_key)

    # remove parts of the url if needed
    if "remove_from_url" in config and len(config["remove_from_url"]) > 0:
        for val in config["remove_from_url"]:
            url = url.replace(val, "")

    if not config:
        url_status = "error_config"

    else:

        # Send the request
        response = do_request(url)

        redirect_html_404 = False
        redirect_robot = False

        # 404
        try:
            # 404 redirect
            if "redirect_404" in config and len(config["redirect_404"]) > 0:
                for a in config["redirect_404"]:
                    if response.url.strip("/").endswith(a):
                        url_status = False
                        redirect_html_404 = True

            # 404 caught from the response url
            if "redirect_404_url" in config and len(config["redirect_404_url"]) > 0:
                for a in config["redirect_404_url"]:
                    if a in response.url:
                        url_status = False
                        redirect_html_404 = True

            if url_status != False:
                soup = BeautifulSoup(get_response_content(response), 'html.parser')
                if soup == '':
                    url_status = False
                    url_status_code = "unknown"

                # Cookies Consent
                elif "accept_cookies_button" in config and len(config["accept_cookies_button"]) > 0:
                    for el in config["accept_cookies_button"]:
                        if len(soup.select(el)) > 0:
                            url_status, soup = bypass_cookies_consent(url, el)

                if soup == '':
                    url_status = False
                    url_status_code = "unknown"
                else:
                    # 404 from the html content (not from the response url)
                    if "html_404" in config and len(config["html_404"]) > 0:

                        for a in config["html_404"]:
                            if len(soup.select(a)) > 0:
                                url_status = False
                                redirect_html_404 = True
                    # Robot blocker
                    if "redirect_robot" in config and len(config["redirect_robot"]) > 0:
                        for a in config["redirect_robot"]:
                            if len(soup.select(a)) > 0:
                                url_status = False
                                redirect_robot = True

        except:
            url_status = False

        # if the url is a 404 redirect
        # Call the wayback machine
        if redirect_html_404 or response.status_code == 404 or redirect_robot == True:
            soup = try_wayback_machine(url)

            # we found the article
            if soup_is_string(soup) == False:
                url_status = True
            else:
                if redirect_robot == True:
                    url_status_code = "robot_blocked"

                else:
                    url_status_code = "404"

        if url_status == True:
            while body == '':
                
                # Title
                if "title" in config and len(config["title"]) > 0:
                    config_val = config["title"]

                    for val in config_val:
                        if not title:
                            if len(soup.select(val)) != 0:
                                for v in soup.select(val):
                                    if v.get_text().strip() != '':
                                        title = v.get_text().strip()

                # Author
                if "author" in config and len(config["author"]) > 0:
                    config_val = config["author"]
                    split = config["author_split"] if "author_split" in config and len(config["author_split"]) > 0 else ""

                    for val in config_val:
                        if len(misc['author']) == 0:
                            if len(soup.select(val)) != 0:
                                for v in soup.select(val):
                                    if v.get_text().strip() != '':

                                        # remove 'By'
                                        # split by 'and' if present
                                        v_final = v.get_text().replace("By ", "")

                                        if split:
                                            split_by = split[0]
                                            split_take = 0 if len(split) < 2 else int(split[1])
                                            v_final = v_final.split(split_by)
                                            if split_take not in v_final:
                                                split_take = 0

                                            v_final = v_final[split_take]
                                            misc['author'].append(v_final.strip()) 

                                        else:
                                            v_final = v_final.split("and")
                                            for vv in v_final:
                                                misc['author'].append(vv.strip())

                # Time
                if "time" in config and len(config["time"]) > 0:
                    # get time (datetime property or just the text inside the html element)
                    mode = config["time_mode"][0] if "time_mode" in config and len(config["time_mode"]) > 0 else ""
                    split = config["time_split"] if "time_split" in config and len(config["time_split"]) > 0 else ""

                    config_val = config["time"]

                    for val in config_val:
                        if not misc['time']:
                            if len(soup.select(val)) != 0:
                                for v in soup.select(val):
                                    if mode != "" and mode in v:
                                        vv = v[mode].strip()
                                    else:
                                        vv = v.get_text().strip()

                                    vv = vv.replace("Published:", "")
                                    if split:
                                        split_by = split[0]
                                        split_take = 0 if len(split) < 2 else int(split[1])
                                        vv = vv.split(split_by)

                                        if len(vv) <= split_take:
                                            split_take = 0
                                        
                                        vv = vv[split_take].strip()

                                    if vv:
                                        misc['time'] = vv
                
                # Body
                if "body" in config and len(config["body"]) > 0:
                    config_val = config["body"]

                    if not body:
                        for val in config_val:
                            if len(soup.select(val)) != 0:
                                body = parser.handle(' '.join([str(element) for element in soup.select(val)]))

                if body == '' and redirect_html_404 == True:
                    url_status_code = "404"
                    waybackCheck(url, title, body)
                    title = url
                    break

                # if we tried once with the waybackmachine and still not succeeding, break the while loop
                if tried_wayback == True:
                    waybackCheck(url, title, body)
                    title = url
                    break
                    
                # if the body cant be found, try the waybackmachine url
                # print(body)
                if body == '' and tried_wayback == False:
                    soup = try_wayback_machine(url)
                    if soup_is_string(soup) == True : break
                    tried_wayback = True

    if url_status_code != '':
        url_status = False
    
    return title.strip(), body.strip(), misc, url_status, url_status_code

def getNews_The_Atlantic(news_link):
    title = ''
    body = ''
    misc = {}
    
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) != 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            
            if len(soup.select('span[itemprop=author]')) != 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('span[itemprop=author]') if a.get_text().strip() != '']
            elif len(soup.select('.c-article-author__link')) != 0:
                title = soup.select('.c-article-author__link')[0].get_text().strip()
            
            if len(soup.select('time[itemprop="datePublished"]')) != 0:
                misc['time'] = soup.select('time[itemprop="datePublished"]')[0]['datetime'].strip()
            
            if len(soup.select('div[itemprop="articleBody"] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop="articleBody"] p')]))
            elif len(soup.select('section[itemprop="articleBody"] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('section[itemprop="articleBody"] p')]))
                
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_National_Review(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('span[itemprop=headline]')) > 0:
                title = soup.select('span[itemprop=headline]')[0].get_text().strip()
            elif len(soup.select('.article-header__title')) > 0:
                title = soup.select('.article-header__title')[0].get_text().strip()
                
            if len(soup.select('a.article-header__meta-author')) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('a.article-header__meta-author') if a.get_text().strip() != '']
                
            if len(soup.select('time[itemprop="datePublished"]')) > 0:
                misc['time'] = soup.select('time[itemprop="datePublished"]')[0]['datetime']
            elif len(soup.select('time')) > 0:
                misc['time'] = soup.select('time')[0]['datetime']
                
            if len(soup.select('div[itemprop="articleBody"] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop="articleBody"] p')]))
            elif len(soup.select('.article-content p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-content p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
        
    return title.strip(), body.strip(), misc, url_status

def getNews_Vox(news_link):
    title = ''
    body = ''
    summary = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.c-page-title')) > 0:
                title = soup.select('h1.c-page-title')[0].get_text().strip()
            if len(soup.select('.c-byline > .c-byline__item a')) > 0:
                misc['author'] = soup.select('.c-byline > .c-byline__item a')[0].get_text().strip()
            if len(soup.select('time.c-byline__item')) > 0:
                misc['time'] = soup.select('time.c-byline__item')[0].get_text().strip()
            
            if len(soup.select('h2.c-entry-summary p-dek')) != 0:
                misc['subtitle'] = soup.select('h2.c-entry-summary p-dek')[0].get_text().strip()
                
            if len(soup.select('.c-entry-content')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.c-entry-content')[0].find_all(['p','h3'])]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_The_Federalist(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
       
            if len(soup.select('header .entry-title a')) != 0:
                title = soup.select('header .entry-title a')[0].get_text().strip()

            if len(soup.select('article a[rel="author"]')) != 0:
                misc['author'] = soup.select('article a[rel="author"]')[0].get_text().strip()
            
            if len(soup.select('.alpha-byline')) != 0:
                misc['time'] = soup.select('.alpha-byline')[0].get_text().strip()

            if len(soup.select('article .entry-content p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article .entry-content p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_USA_TODAY(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
       
            if len(soup.select('h1[itemprop=headline]')) != 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            elif len(soup.select('.article-wrapper h1.title')) != 0:
                title = soup.select('.article-wrapper h1.title')[0].get_text().strip()

            if len(soup.select('.asset-metabar-author a[rel=author]')) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('.asset-metabar-author a[rel=author]') if a.contents[0].strip() != '']
            elif len(soup.select('.article-wrapper .author')) != 0:
                misc['author'] = [a.strip() for a in soup.select('.article-wrapper .author')[0].get_text().split("and")]
            
            if len(soup.select('.asset-metabar-time')) != 0:
                misc['time'] = soup.select('.asset-metabar-time')[0].get_text().replace('Published ','').split('|',1)[0].strip()
            elif len(soup.select('.article-wrapper .publish-date')):
                misc['time'] = soup.select('.article-wrapper .publish-date')[0].get_text().strip()

            if len(soup.select('div[itemprop=articleBody] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] p')]))
            elif len(soup.select('.article-wrapper p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-wrapper p')]))
                    
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_Washington_Post_news(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('html.blog')) != 0:
                title = soup.select('#article-topper h1[itemprop=headline]')[0].get_text().strip()
            if len(soup.select('span.author')) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.find_all('span',itemprop="author")[0].find_all('span', itemprop = 'name')]
            if len(soup.select('span[itemprop="datePublished"]')) > 0:
                misc['time'] = soup.select('span[itemprop="datePublished"]')[0].get_text().strip()

            if len(soup.select('article[itemprop="articleBody"] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article[itemprop="articleBody"] p')]))
            elif len(soup.find_all('article p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
                
    return title.strip(), body.strip(), misc, url_status

def getNews_Washington_Post_graphics(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.pg-h1 balanced-headline')) > 0:
                title = removeHeading(parser.handle(str(soup.find_all('h1', class_ ="pg-h1 balanced-headline")[0]))).strip()

            if len(soup.select('h1.pg-h1 balanced-headline')) > 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('.pg-byline--author-wrap a') if a.get_text().strip() != '']

            if len(soup.select('span[itemprop="datePublished"]')) > 0:
                misc['time'] = soup.select('span[itemprop="datePublished"]')[0].get_text().strip()

            if len(soup.select('article .pg-bodyCopy')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article .pg-bodyCopy')]))
           
           # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True

    return title.strip(), body.strip(), misc, url_status

def getNews_Reuters(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.ArticleHeader_headline_2zdFM')) > 0:
                title = soup.select('h1.ArticleHeader_headline_2zdFM')[0].get_text().strip()
            
            if len(soup.select('h1.headline_2zdFM')) > 0:
                title = soup.select('h1.headline_2zdFM')[0].get_text().strip()

            if len(soup.select('.ArticleHeader_headline')) > 0:
                title = soup.select('.ArticleHeader_headline')[0].get_text().strip()
                
            if len(soup.select('.lower-container')[0].find_all('a',href=True)) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('.lower-container')[0].find_all('a',href=True) if a.contents[0].strip() != '']
            elif len(soup.select('.BylineBar_byline span a')) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('.BylineBar_byline span a') if a.contents[0].strip() != '']
                
            if len(soup.select('.ArticleHeader_date_V9eGk')) > 0:
                misc['time'] = soup.select('.ArticleHeader_date_V9eGk')[0].get_text().split('/')[0].strip()
            elif len(soup.select('.date_V9eGk')) > 0:
                misc['time'] = soup.select('.date_V9eGk')[0].get_text().split('/')[0].strip()
            elif len(soup.select('.ArticleHeader_date')) > 0:
                misc['time'] = soup.select('.ArticleHeader_date')[0].get_text().split('/')[0].strip()
                
            if len(soup.select('.StandardArticleBody_body p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.StandardArticleBody_body p')]))
            elif len(soup.select('.StandardArticleBody_body_1gnLA p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.StandardArticleBody_body_1gnLA p')]))
            elif len(soup.select('.body_1gnLA p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.body_1gnLA p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_Reuters_Mobile(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.ArticleHeader_headline_2zdFM')) > 0:
                title = soup.select('h1.ArticleHeader_headline_2zdFM')[0].get_text().strip()
            
            if len(soup.select('h1.headline_2zdFM')) > 0:
                title = soup.select('h1.headline_2zdFM')[0].get_text().strip()
                
            if len(soup.select('.lower-container')[0].find_all('a',href=True)) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('.lower-container')[0].find_all('a',href=True) if a.contents[0].strip() != '']
                
            if len(soup.select('.ArticleHeader_date_V9eGk')) > 0:
                misc['time'] = soup.select('.ArticleHeader_date_V9eGk')[0].get_text().split('/')[0].strip()
            if len(soup.select('.date_V9eGk')) > 0:
                misc['time'] = soup.select('.date_V9eGk')[0].get_text().split('/')[0].strip()
                
            if len(soup.select('.StandardArticleBody_body_1gnLA p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.StandardArticleBody_body_1gnLA p')]))
            if len(soup.select('.body_1gnLA p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.body_1gnLA p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_CBN(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.page-title')) != 0:
                title = soup.select('h1.page-title')[0].contents[0].strip()
            
            if len(soup.select('div[property=schema:author]')) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('div[property=schema:author]')[0].find_all('a',href=True) if a.contents[0].strip() != '']
            
            if len(soup.select('span[property=schema:datePublished]')) != 0:
                misc['time'] = soup.select('span[property=schema:datePublished]')[0].contents[0].split('/')[0].strip()
               
            if len(soup.find_all('div', property= "content:encoded")) != 0:     
                body = parser.handle(' '.join([str(p) for p in soup.find_all('div', property= "content:encoded")[0].find_all('p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
        
    return title.strip(), body.strip(), misc, url_status

def getNews_TechCrunch(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.wsj-article-headline')) > 0:
                title = soup.select('h1.wsj-article-headline')[0].get_text().strip()
            if len(soup.select('.byline a')) > 0:
                misc['author'] = soup.select('.byline a')[0].get_text().strip()
            if len(soup.select('.byline time[datetime]')) > 0:
                misc['time'] = soup.select('.byline time[datetime]')[0]['datetime']

            if len(soup.select('.article-entry > p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-entry > p')]))
        
                # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status
    
def getNews_MSNBC(news_link):
    title = ''
    body = ''
    misc = {}
    
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) > 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            if len(soup.select('[itemprop=author] a')) > 0:
                misc['author'] = soup.select('[itemprop=author] a')[0].get_text().strip()
            if len(soup.select('time[datetime]')) > 0:
                misc['time'] = soup.select('time[datetime]')[0]['datetime']
      
            if len(soup.select('[itemprop=articleBody] > p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('[itemprop=articleBody] > p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True    
    
    return title.strip(), body.strip(), misc, url_status
    
def getNews_National_Interest(news_link):
    title = ''
    body = ''
    misc = {}
    
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('#page-title')) > 0:
                title = soup.select('#page-title')[0].get_text().strip()
            if len(soup.select('span[property=schema:author] a')) > 0:
                misc['author'] = soup.select('span[property=schema:author] a')[0].get_text().strip()
            if len(soup.select('time[datetime]')) > 0:
                misc['time'] = soup.select('time[datetime]')[0]['datetime']

            if len(soup.select('.node-content p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.node-content p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status
    
def getNews_The_Independent(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) > 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            if len(soup.select('li[itemprop=author] a')) > 0:
                misc['author'] = soup.select('li[itemprop=author] a')[0].get_text().strip()
            if len(soup.select('li time[datetime]')) > 0:
                misc['time'] = soup.select('li time[datetime]')[0]['datetime'].split(' -', 1)[0]

            if len(soup.select('div[itemprop=articleBody] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True    
    
    return title.strip(), body.strip(), misc, url_status

def getNews_Independent_Journal_Review(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop="headline"]')) > 0:
                title = soup.select('h1[itemprop="headline"]')[0].get_text().strip()
            if len(soup.select('a[rel="author"]')) > 0:
                misc['author'] = soup.select('a[rel="author"]')[0].get_text().strip()
            if len(soup.select('time[itemprop="datePublished"]')) > 0:
                misc['time'] = soup.select('time[itemprop="datePublished"]')[0]['datetime'].strip()

            if len(soup.select('div[itemprop="articleBody"] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop="articleBody"] p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True    
    
    return title.strip(), body.strip(), misc, url_status

def getNews_The_Week(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.article-headline p')) > 0 and title != '':
                title = soup.select('.article-headline p')[0].contents[0].strip()
            elif len(soup.select('.article-headline-detail p')) > 0 and title != '':
                title = soup.select('.article-headline-detail p')[0].contents[0].strip()
            elif len(soup.select('.section-1 .sr-headline')) > 0 and title != '':
                title = soup.select('.section-1 .sr-headline')[0].contents[0].strip()
            
            if len(soup.select('.author .name')) > 0:
                misc['author'] = soup.select('.author .name')[0].contents[0].strip()
            
            if len(soup.select('.article-date')) > 0:
                misc['time'] = soup.select('.article-date')[0].contents[0].strip()
            elif len(soup.select('.section-1 .sr-date')) > 0 and title != '':
                title = soup.select('.section-1 .sr-date')[0].contents[0].strip()
                
            if len(soup.select('.article-body p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-body p')]))
            elif len(soup.select('.section-1 article p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.section-1 article p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
        
    return title.strip(), body.strip(), misc, url_status 

def getNews_The_Nation(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.title')) > 0:
                title = soup.select('h1.title')[0].get_text().strip()
            if len(soup.select('.author_name .author')) > 0:
                misc['author'] = soup.select('.author_name .author')[0].get_text().replace('By ', '').strip()
            if len(soup.select('.article_pub_time')) > 0:
                misc['time'] = soup.select('.article_pub_time')[0].get_text().strip()

            if len(soup.select('section.article-body p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('section.article-body p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status
    
def getNews_The_Intercept(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':

            if len(soup.select('h1.Post-title')) > 0:
                title = soup.select('h1.Post-title')[0].get_text().strip()
            if len(soup.select('a[rel="author"] span')) > 0:
                misc['author'] = soup.select('a[rel="author"] span')[0].get_text().strip()
            if len(soup.select('.PostByline-date span')) > 0:
                misc['time'] = soup.select('.PostByline-date span')[0].get_text().strip()
                
            if len(soup.select('.PostContent p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.PostContent p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status
    

def getNews_Pando(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':

            if len(soup.select('#intro h1')) > 0:
                title = soup.select('#intro h1')[0].get_text().strip()
                
            if len(soup.select('#byline a')) > 0:
                misc['author'] = soup.select('#byline a')[0].get_text().replace('By ', '').strip()
            if len(soup.select('#byline > span')) > 0:
                misc['time'] = soup.select('#byline > span')[0].get_text().split('written on', 1)[1].strip()
                
            if len(soup.select('.contains-copy p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.contains-copy p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status
    
def getNews_Cato_Institute_Blog(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':

            if len(soup.select('h1.page-h1')) > 0:
                title = soup.select('h1.page-h1')[0].get_text().strip()
            if len(soup.select('.byline a[typeof=foaf:Person]')) > 0:
                misc['author'] = soup.select('.byline a[typeof=foaf:Person]')[0].get_text().strip()
            if len(soup.select('time.date-property-single')) > 0:
                misc['time'] = soup.select('time.date-property-single')[0]['content'].strip()

            if len(soup.select('.body-text p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.body-text p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_The_Boston_Globe(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1[itemprop=headline]')) > 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            if len(soup.select('.article-header__byline-author')) > 0:
                misc['author'] = soup.select('.article-header__byline-author')[0].get_text().split('By ', 1)[1].strip()
            if len(soup.select('time[itemprop=datePublished]')) > 0:
                misc['time'] = soup.select('time[itemprop=datePublished]')[0]['datetime'].strip()

            if len(soup.select('div[itemprop=articleBody] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_Pew_Research(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
           
            misc['author'] = 'Pew Research Center'
            if len(soup.select('#content h1')) > 0:
                title = soup.select('#content h1')[0].get_text().strip()
            if len(soup.select('#content .date')) > 0:
                misc['time'] = soup.select('#content .date')[0]['data-datetime'].strip()

            if len(soup.select('p.selectionShareable')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('#content')[0].select('p.selectionShareable')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_Gallup(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.header-article h1')) > 0:
                title = soup.select('.header-article h1')[0].get_text().strip()
            if len(soup.select('.authorDisplayLine1 a')) > 0:
                misc['author'] = soup.select('.authorDisplayLine1 a')[0].get_text().strip()
            if len(soup.select('time[itemprop="datePublished"]')) > 0:
                misc['time'] = soup.select('time[itemprop="datePublished"]')[0]["datetime"].strip()

            if len(soup.select('div[itemprop="articleBody"] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop="articleBody"] p')[0]]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status


def getNews_CNSNews(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.page-header')) > 0:
                title = soup.select('h1.page-header')[0].get_text().strip()
            if len(soup.select('.authors')) > 0:
                misc['author'] = soup.select('.authors')[0].get_text().split('|')[0].replace('By ', '').strip()

            if len(soup.select('#block-system-main .content p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('#block-system-main .content p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_New_York_Post(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.CheatHeader__title')) > 0:
                title = soup.select('h1.CheatHeader__title')[0].get_text().strip()
            
            elif len(soup.select('.article-header h1')) > 0:
                title = soup.select('.article-header h1')[0].get_text().strip()
                
            if len(soup.select('#author-byline .byline a')) > 0:
                misc['author'] = soup.select('#author-byline .byline a')[0].get_text().strip()
            
            if len(soup.select('.byline-date')) > 0:
                misc['time'] = soup.select('.byline-date')[0].get_text().split('|',1)[0].strip()
            
            if len(soup.select('time.PublicationTime')) > 0:
                misc['time'] = soup.select('time.PublicationTime')[0]['datetime'].strip()

            if len(soup.select('.entry-content')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.entry-content p')]))
            elif len(soup.select('.CheatBody')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.CheatBody p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_Daily_Beast(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.ArticleBody h1.Title')) > 0:
                title = soup.select('.ArticleBody h1.Title')[0].get_text().strip()
            elif len(soup.select('h1.CheatHeader__title')) > 0:
                title = soup.select('h1.CheatHeader__title')[0].get_text().strip()  
            
            if len(soup.select('.ArticleAuthor__name')) > 0:
                misc['author'] = soup.select('.ArticleAuthor__name')[0].get_text().strip()
               
            if len(soup.select('.ArticleBody__date-time')) > 0: 
                misc['time'] = soup.select('.ArticleBody__date-time')[0].get_text().strip()
            
            elif len(soup.select('header .PublicationTime__date')) > 0: 
                misc['time'] = soup.select('header .PublicationTime__date')[0].get_text().strip()
                 
            if len(soup.select('article.Body p')) > 0: 
                body = parser.handle(' '.join([str(p) for p in soup.select('article.Body p')]))
            elif len(soup.select('.CheatBody p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.CheatBody p')]))
                
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status
    
def getNews_Daily_Beast_Cheats(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            misc['author']  = ''
            if len(soup.select('h1.CheatHeader__title')) > 0:
                title = soup.select('h1.CheatHeader__title')[0].get_text().strip()
                
            if len(soup.select('h1.CheatHeader__title')) > 0:
                misc['time'] = soup.select('time.PublicationTime')[0]['datetime'].strip()

            if len(soup.select('.CheatBody p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.CheatBody p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_HotAir(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.article')) > 0:
                title = soup.select('h1.article')[0].get_text().strip()
                
            if len(soup.select('span.author')) > 0:
                misc['author'] = soup.select('span.author')[0].get_text()
            if len(soup.select('.byline')) > 0:
                misc['time'] = soup.select('.byline')[0].get_text().split("on ", 1)[1]
                
            if len(soup.select('.salem-content-injection-wrap p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.salem-content-injection-wrap p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status
    
def getNews_KSL(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1[data-role=storyTitle]')) > 0:
                title = soup.select('h1[data-role=storyTitle]')[0].get_text().strip()
            if len(soup.select('span.author')) > 0:
                misc['author'] = soup.select('span.author')[0].get_text().split("and")
            if len(soup.select('.story h4')) > 0:
                misc['time'] = re.sub(r'@.*', '', soup.select('.story h4')[0].get_text().split("Posted",1)[1][1:] )
                
            if len(soup.select('#kslMainArticle p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('#kslMainArticle p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_NBC_News(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('.article-hed h1')) > 0:
                title = soup.select('.article-hed h1')[0].get_text().strip()
            elif len(soup.select('h1.nhqI9FeZjriaympPDu4K4')) > 0:
                title = soup.select('h1.nhqI9FeZjriaympPDu4K4')[0].get_text().strip()
            elif len(soup.select('header h1')) > 0:
                title = soup.select('header h1')[0].get_text().strip()
            
            if len(soup.select('.byline .byline_author')) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('.byline .byline_author') if a.get_text().strip() != '']
            elif len(soup.select('._2FfYYqD6LKQXumcozpQUlc')) > 0:
                misc['author'] = soup.select('._2FfYYqD6LKQXumcozpQUlc')[0].get_text().strip().replace('by','')
            if len(soup.select('time.timestamp_article')) > 0:
                misc['time'] = soup.select('time.timestamp_article')[0]['datetime']
            elif len(soup.select('time._3OViwiRtR_PFko9i8o9Mov')) > 0:
                misc['time'] = soup.select('time._3OViwiRtR_PFko9i8o9Mov')[0]['datetime']
            elif len(soup.select('article time')) > 0:
                misc['time'] = soup.select('article time')[0]['datetime']

            if len(soup.select('.article-body p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-body p')]))
            elif len(soup.select('.vDyiyCGfLduDDsffkLdUM p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.vDyiyCGfLduDDsffkLdUM p')]))
            elif len(soup.select('article p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status 

def getNews_Newsweek(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) > 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            
            if len(soup.select('span[itemprop="author"]')) > 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('span[itemprop="author"]') if a.get_text().strip() != '']
            if len(soup.select('time')) > 0:
                misc['time'] = soup.select('time[itemprop="datePublished"]')[0]['datetime']
            if len(soup.select('.articleBody p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.articleBody p')]))
            elif len(soup.select('div[itemprop="articleBody"] p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop="articleBody"] p')]))
                misc['time'] = soup.select('time[itemprop="datePublished"]')[0]['datetime']
            elif len(soup.select('.article-body p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-body p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status

def getNews_Mashable(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':

            if len(soup.select('header.article-header h1.title')) != 0:
                title = soup.select('header.article-header h1.title')[0].get_text().strip()
            
            if len(soup.select('.byline .author_name a')) != 0:
                misc['author'] = soup.select('.byline .author_name a')[0].get_text().strip()
            
            if len(soup.select('.byline time')) != 0:
                misc['time'] = soup.select('.byline time')[0]['datetime']

            if len(soup.select('.article-content p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-content p')]))
                    
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
                
    return title.strip(), body.strip(), misc, url_status

def getNews_Mother_Jones(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.entry-title')) != 0:
                title = soup.select('h1.entry-title')[0].get_text().strip()
            if len(soup.select('.byline a')) != 0:
                misc['author'] = soup.select('.byline a')[0].get_text().strip()
            if len(soup.select('.byline-dateline .dateline')) != 0:
                misc['time'] = soup.select('.byline-dateline .dateline')[0].get_text().strip()
            if len(soup.select('article.entry-content p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article.entry-content p')]))
       
               # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True

    return title.strip(), body.strip(), misc, url_status

def getNews_Media_Matters(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.bd-headline h1')) != 0:
                title = soup.select('.bd-headline h1')[0].contents[0].strip()
                
            if len(soup.select('a.author-link')) != 0:
                misc['author'] = soup.select('a.author-link')[0].contents[0].strip()
            if len(soup.select('.bd-headline time')) != 0:
                misc['time'] = soup.select('.bd-headline time')[0].contents[0].strip()
              
            if len(soup.select('.item-body p')) != 0:  
                body = parser.handle(' '.join([str(p) for p in soup.select('.item-body p')]))

               # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
        
    return title.strip(), body.strip(), misc, url_status

def getNews_Jeff_Jacoby(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.article-header__headline')) != 0:
                title = soup.select('h1.article-header__headline')[0].get_text().strip()

            if len(soup.select('p.article-header__overline')) != 0:
                misc['author'] = soup.select('p.article-header__overline')[0].get_text().strip()
            if len(soup.select('time.article-header__pubdate')) != 0:
                misc['time'] = soup.select('time.article-header__pubdate')[0].get_text().strip()

            if len(soup.select('.article-content p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-content p')]))

               # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
        
    return title.strip(), body.strip(), misc, url_status
    
def getNews_New_York_Magazine(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.headline-primary')) != 0:
                title = soup.select('h1.headline-primary')[0].get_text().strip()
                
            if len(soup.select('a.article-author')) != 0:
                misc['author'] = soup.select('a.article-author')[0].get_text().strip()
                
            if len(soup.select('span.large-width-date')) != 0:
                misc['time'] = soup.select('span.large-width-date')[0].get_text().strip()

            if len(soup.select('section.body p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('section.body p')]))
            
           # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
        
    return title.strip(), body.strip(), misc, url_status

def getNews_LastVegasSun(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.articlehed1')) != 0:
                title = soup.select('h1.articlehed1')[0].contents[0].strip()

            if len(soup.select('p.byline')) != 0:
                misc['author'] = soup.select('p.byline')[0].contents[0].replace('By ','').strip()

            if len(soup.select('p.bypubdate')) != 0:
                misc['time'] = soup.select('p.bypubdate')[0].contents[0].strip()
            
            if len(soup.find_all('div', class_ = "article")[0].find_all('p', attrs={'class': None})) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.find_all('div', class_ = "article")[0].find_all('p', attrs={'class': None})]))
        
           # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
    
    return title.strip(), body.strip(), misc, url_status

def getNews_Fox_News_Latino(news_link):    
    title = ''
    body = ''
    misc = {}
    
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('#content article h1')) != 0:
                title = soup.select('#content article h1')[0].get_text().strip()
            
            if len(soup.select('.article-info p')) != 0:
                misc['author'] = re.sub(' +',' ',soup.select('.article-info p')[0].get_text().replace('By','')).split(',')
            
            if len(soup.select('#content time')) != 0:
                misc['time'] = soup.select('#content time')[0]['datetime'].split('T')[0].strip()

            if len(soup.select('.article-text')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-text')[0].find_all('p')]))
        
           # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
    
    return title.strip(), body.strip(), misc, url_status

def getNews_Fox_News_insider(news_link):
    title = ''
    body = ''
    misc = {}
    
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1#page-title')) > 0:
                title = soup.select('h1#page-title')[0].get_text().strip()
            elif len(soup.select('h1[itemprop=headline]')) > 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            
            if len(soup.select('.author span[itemprop=name]')) > 0:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('span', itemprop = 'author')[0].find_all('span', itemprop='name') if a.contents[0].strip() != '']
            
            if len(soup.select('time')) > 0:
                misc['time'] = soup.find_all('time')[0]['datetime']
                
            if len(soup.select('.articleBody')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.find_all('div', class_ = "articleBody")[0].find_all('p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
            
    return title.strip(), body.strip(), misc, url_status

def getNews_The_Daily_Caller(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select("#main-article h1")) != 0:
                title = soup.select("#main-article h1")[0].contents[0].strip()

            if len(soup.select(".name")) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('.name') if a.contents[0].strip()!='']
            if len(soup.select(".dateline")) != 0:
                misc['time'] = soup.find_all('div', class_ = 'dateline')[0].contents[0].strip()
                
            if len(soup.select(".thepost post article-content p")) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.thepost post article-content p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True  
        
    return title.strip(), body.strip(), misc, url_status

def getNews_RealClearPolitics(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select(".article-title h1")) != 0:
                title = soup.select(".article-title h1")[0].contents[0].strip()
            elif len(soup.select("h3.entry_header")) != 0:
                title = soup.select("h3.entry_header")[0].contents[0].strip()
            if len(soup.select(".auth-byline a")) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('div', class_ = 'auth-byline')[0].find_all('a', href=True) if a.contents[0].strip() != '']

            if len(soup.select(".auth-byline")) != 0:
                misc['time'] = soup.find_all('div', class_ = 'auth-byline')[0].contents[-1].strip()

            if len(soup.select(".article-body-text p")) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.find_all('div', class_ = "article-body-text")[0].find_all('p')[:-1]]))
            #    -1th is always an author statement?
            #    ex: James Arkin is a congressional reporter for RealClearPolitics. He can be reached at ....
            elif len(soup.select("#story p")) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('#story p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
    
    return title.strip(), body.strip(), misc, url_status

def getNews_The_Hill(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('#page-title')) != 0:
                title = soup.select('#page-title')[0].get_text()
           
            if len(soup.select('.submitted-by')) > 0:
                author_split = soup.select('.submitted-by')[0].get_text().split('-')[0]
                misc['author'] = author_split.replace('By','').strip()
            if len(soup.select('.submitted-date')) != 0:
                misc['time'] = soup.select('.submitted-date')[0].get_text().strip()

            if len(soup.select('div[property="content:encoded"] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[property="content:encoded"] p') ]))
            if body == '' and len(soup.select('div[property="content:encoded"] div')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[property="content:encoded"] div') ]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
    
    return title.strip(), body.strip(), misc, url_status

def getNews_ThinkProgress(news_link):
    title = ''
    body = ''
    subtitle = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.post__title')) != 0:
                title = soup.select('h1.post__title')[0].get_text().strip()
            
            if len(soup.select('.post__byline__author a')) != 0:
                misc['author'] = [a.get_text().strip() for a in soup.find_all('span', class_ = 'post__byline__author')[0].find_all('a',href=True,target=False) if a.get_text().strip()!='']
            
            if len(soup.select('time.post__date')) != 0:
                misc['time'] = soup.select('time.post__date')[0].get_text().strip()
            
            if len(soup.select('h2.post__dek')) != 0:
                misc['subtitle'] = soup.select('h2.post__dek')[0].get_text().strip()

            if len(soup.select('.post__content p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.find_all('div', class_ = "post__content")[0].find_all('p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
    
    return title.strip(), body.strip(), misc, url_status

def getNews_FactCheck(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.entry-title')) != 0:
                title = soup.select('h1.entry-title')[0].get_text().strip()
            if len(soup.select('.byline .author')) != 0:
                misc['author']  = soup.select('.byline .author')[0].get_text().strip()
            if len(soup.select('time[datetime]')) != 0:
                misc['time']  = soup.select('time[datetime]')[0]['datetime'].strip()

            if len(soup.select('.entry-content > p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.entry-content > p')]))
        
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
    
    return title.strip(), body.strip(), misc, url_status

def getNews_CNN_Web_News(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.cnnBlogContentTitle')) != 0:
                title = soup.select('.cnnBlogContentTitle')[0].get_text().strip()

            elif len(soup.select('h1.pg-headline')) != 0:
                title = soup.select('h1.pg-headline')[0].get_text().strip()
                
            elif len(soup.select('#cnnContentContainer h1')) != 0:
                title = soup.select('#cnnContentContainer h1')[0].get_text().strip()
                
            elif len(soup.select('h1.article-title')) != 0:
                title = soup.select('h1.article-title')[0].get_text().strip()

            if len(soup.select('.cnn_author')) != 0:
                misc['author'] = soup.select('.cnn_author')[0].get_text().strip()
                
            elif len(soup.select('.metadata__byline__author')) != 0:
                misc['author'] = soup.select('.metadata__byline__author')[0].get_text().replace('By ', '').strip()
                
            elif len(soup.select('#cnnContentContainer .cnnByline')) != 0:
                misc['author'] = soup.select('#cnnContentContainer .cnnByline')[0].get_text().replace('By ', '').strip()
             
            elif len(soup.select('.byline-timestamp .byline a')) > 1:
                misc['author'] = soup.select('.byline-timestamp .byline a')[1].get_text().strip()

            if len(soup.select('.cnnBlogContentDateHead')) != 0:
                misc['time'] = soup.select('.cnnBlogContentDateHead')[0].get_text().strip()
                
            elif len(soup.select('.update-time')) != 0:
                if len(soup.select('.update-time')[0].get_text().split(')',1)) > 0:
                    misc['time'] = soup.select('.update-time')[0].get_text().split(')',1)[1].strip()
                
            elif len(soup.select('#cnnContentContainer .cnn_strytmstmp')) != 0:
                try:
                    misc['time'] = re.findall(r'(,.*)', soup.select('#cnnContentContainer .cnn_strytmstmp')[0].get_text())[0][2:].strip()
                except:
                    pass
                
            elif len(soup.select('.byline-timestamp .cnnDateStamp')) != 0: 
                time = soup.select('.byline-timestamp .cnnDateStamp')[0].get_text()
                
            if len(soup.select('.zcnnBlogContentPost p')) != 0: 
                body = parser.handle(' '.join([str(p) for p in soup.select('.zcnnBlogContentPost p')]))
                
            elif len(soup.select('.zn-body__paragraph')) != 0: 
                body = parser.handle(' '.join([str(p) for p in soup.select('.zn-body__paragraph')]))

            elif len(soup.select('div[itemprop=articleBody] .zn-body__paragraph')) != 0: 
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] .zn-body__paragraph')]))
        
            elif len(soup.select('.cnn_storypgraphtxt')) != 0: 
                body = parser.handle(' '.join([str(p) for p in soup.select('.cnn_storypgraphtxt')]))
            
            elif len(soup.select('#storytext p')) != 0: 
                body = parser.handle(' '.join([str(p) for p in soup.select('#storytext p')]))
             
            elif len(soup.select('.cnnBlogContentPost p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.cnnBlogContentPost p')]))
                 
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
            
    return title.strip(), body.strip(), misc, url_status

def getNews_Washington_Examiner(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) != 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()
            
            if len(soup.select('a[itemprop=author]')) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('a[itemprop=author]')[0].select('span[itemprop=name') if a.get_text().strip()!='']
            
            if len(soup.select('time[itemprop=datePublished]')) != 0:
                misc['time'] = soup.select('time[itemprop=datePublished')[0].get_text().strip()
                
            if len(soup.select('div[itemprop=articleBody] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] p')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
            
    return title.strip(), body.strip(), misc, url_status

def getNews_PBS_NewsHour(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.headline')) != 0:
                title = soup.find_all('h1', itemprop ="headline")[0].contents[0].strip()

            if len(soup.select('a[itemprop="author"]')) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('a',itemprop="author")[0].find_all('span', itemprop = 'name') if a.contents[0].strip()!='']
            if len(soup.select('time[itemprop="datePublished"]')) != 0:
                misc['time'] = soup.find_all('time', itemprop = 'datePublished')[0].contents[0].strip()

            if len(soup.select('article[itemprop="articleBody"] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('article[itemprop="articleBody"] p')[0].find_all('p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
        
    return title.strip(), body.strip(), misc, url_status

def getNews_The_Guardian(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) != 0:
                title = soup.select('h1[itemprop=headline]')[0].contents[0].strip()
            if len(soup.select('h1[articleprop=headline]')) != 0:
                title = soup.select('h1[articleprop=headline]')[0].contents[0].strip()
            
            if len(soup.find_all('a',rel="author")) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('a',rel="author")[0].find_all('span', itemprop = 'name') if a.contents[0].strip()!='']
            else:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('p',class_='byline') if a.contents[0].strip()!='']
                
            if len(soup.select('time[itemProp="datePublished"]')) != 0:
                misc['time'] = soup.find_all('time', itemprop = 'datePublished')[0].contents[0].strip()
            if len(soup.select('.content__standfirst')) != 0:
                misc['summary'] = soup.select('.content__standfirst')[0].get_text().strip()

            if len(soup.select('div[itemprop=articleBody] p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
        
    return title.strip(), body.strip(), misc, url_status

def getNews_Breitbart_News(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('header.articleheader h1')) != 0:
                title = soup.select('header.articleheader h1')[0].contents[0].strip()
            if len(soup.select('a.byauthor')) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('a',class_="byauthor") if a.contents[0].strip()!='']
            if len(soup.select('span.bydate')) != 0:
                misc['time'] = soup.find_all('span', class_ = 'bydate')[0].contents[0].strip()

            if len(soup.select('.entry-content p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.entry-content p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
        
    return title.strip(), body.strip(), misc, url_status

def getNews_Slate(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.article__hed') )!= 0:
                title = soup.select('h1.article__hed')[0].contents[0].strip()
            elif len(soup.select('#article_header h1') )!= 0:
                title = soup.select('#article_header h1')[0].contents[0].strip()
            
            if len(soup.select('#main_byline a') )!= 0:
                misc['author'] = soup.select('#main_byline a')[0].contents[0].strip()
            else:
                if len(soup.select('.article__authors span[itemprop=name]') )!= 0:
                    misc['author'] = [a.contents[0].strip() for a in soup.select('.article__authors span[itemprop=name]') if a.contents[0].strip()!='']

            if len(soup.select('#article_header .pub-date') )!= 0:
                misc['time'] = soup.select('#article_header .pub-date')[0].contents[0].strip()
            else:
                if len(soup.select('.article__date') )!= 0:
                    misc['time'] = soup.select('.article__date')[0].contents[0].strip()

            if len(soup.select('.newbody p') )!= 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.newbody p')]))
            else:
                if len(soup.select('div[itemprop=articleBody] p') )!= 0:
                    body = parser.handle(' '.join([str(p) for p in soup.select('div[itemprop=articleBody] p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
                
    return title.strip(), body.strip(), misc, url_status

def getNews_NPR_News(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
        
    # Cookies Consent
    if url_status == True and len(soup.select("#accept")) > 0 and len(soup.select("#revoke")) > 0:
        url_status, soup = bypass_cookies_consent(news_link, '//*[@id="accept"]')
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.storytitle h1')) != 0:
                title = soup.select('.storytitle h1')[0].contents[0].strip()

            if len(soup.select('a[rel="author"]')) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('a[rel="author"]') if a.contents[0].strip() != '']
            if len(soup.select('span.date')) != 0:
                misc['time'] = soup.select('span.date')[0].contents[0].strip()

            if len(soup.select('#storytext p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.find_all('div', id = "storytext")[0].find_all('p')[2:]]))
            #    1st and 2nd are always a picture?
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
        
    return title.strip(), body.strip(), misc, url_status

    
def getNews_Salon(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.title-container h1')) != 0:
                title = soup.select('.title-container h1')[0].get_text().strip()
                
            if len(soup.select('.writer-container a')) != 0:
                misc['author'] = [a.get_text().strip() for a in soup.select('.writer-container a') if a.get_text().strip() != '']
            if len(soup.select('.writer-container h6')) != 0:
                misc['time'] = soup.select('.writer-container h6')[0].get_text().replace('(UTC)', '').strip()
              
            if len(soup.select('article p')) != 0:  
                body = parser.handle(' '.join([str(p) for p in soup.select('article p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
    
    return title.strip(), body.strip(), misc, url_status
    

def getNews_CNBC(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('.story-header-left h1.title')) != 0:
                title = soup.select('.story-header-left h1.title')[0].get_text().strip()

            if len(soup.select('div[itemprop=author] a')) != 0:
                misc['author'] = soup.select('div[itemprop=author] a')[0].get_text().strip()

            if len(soup.select('time[itemprop=datePublished]')) != 0:
                misc['time'] = soup.select('time[itemprop=datePublished]')[0]['datetime'].strip()

            if len(soup.select('#article_body p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('#article_body p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 

    return title.strip(), body.strip(), misc, url_status

def getNews_IB_Times(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1[itemprop=headline]')) != 0:
                title = soup.select('h1[itemprop=headline]')[0].get_text().strip()

            if len(soup.select('.author-name span')) != 0:
                misc['author'] = soup.select('.author-name span')[0].get_text().strip()

            if len(soup.select('time[itemprop=datePublished]')) != 0:
                misc['time'] = soup.select('time[itemprop=datePublished]')[0]['datetime'].strip()

            if len(soup.select('.article-body p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.article-body p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 

    return title.strip(), body.strip(), misc, url_status
    
def getNews_WND_com(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('h1.posttitle')) != 0:
                title = soup.select('h1.posttitle')[0].get_text().strip()

            if len(soup.find_all('div',class_="byline author vcard")) != 0:
                misc['author'] = [a.contents[0].strip() for a in soup.find_all('div',class_="byline author vcard")[0].find_all('span', class_='fn')[0].find_all('a') if a.contents[0].strip() != '']

            if len(soup.select('time')) != 0:
                misc['time'] = soup.select('time')[0]['datetime'].strip()

            if len(soup.select('h2.deck')) != 0:
                misc['subtitle'] = soup.select('h2.deck')[0].get_text().strip()

            if len(soup.select('.entry-content wnd p')) != 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.entry-content wnd p')][:-1]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 

    return title.strip(), body.strip(), misc, url_status

def getNews_Buzzfeed(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
        
            if len(soup.select('header h1.buzz-title')) >0:
                title = soup.select('header h1.buzz-title')[0].get_text().strip()
                    
            if len(soup.select('.byline a.bold')) >0:
                misc['author'] = [a.get_text().strip() for a in soup.select('.byline a.bold') if a.get_text().strip()!='']
            if len(soup.select('time.buzz-timestamp__time')) >0:
                misc['time'] = soup.select('time.buzz-timestamp__time')[0].get_text().strip()

            if len(soup.select('article .subbuzz-text')) >0:
                body = parser.handle(' '.join([str(p) for p in soup.find_all('article')[0].find_all('div',class_='subbuzz-text')]))
            
            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True 
        
    return title.strip(), body.strip(), misc, url_status

def getNews_Wall_Street_Journal_News(news_link):
    title = ''
    body = ''
    misc = {}
    tried_wayback = False
    url_status = True
    try: soup = BeautifulSoup(get_html(news_link), 'html.parser')
    except: url_status = False
    
    if url_status == True:
        while body == '':
            
            if len(soup.select('h1.wsj-article-headline')) > 0:
                title = soup.select('h1.wsj-article-headline')[0].get_text().strip()
                
            if len(soup.select('.author span')) > 0:
                misc['author'] = [a.contents[0].strip() for a in soup.select('.author span') if a.contents[0].strip()!='']
                
            if len(soup.select('time.timestamp')) > 0:
                misc['time'] = soup.select('time.timestamp')[0].get_text().strip()
            
            if len(soup.select('h2[itemprop=description]')) > 0:
                subtitle = soup.select('h2[itemprop=description]')[0].get_text().strip()

            if len(soup.select('.lb-widget-text p')) > 0:
                body = parser.handle(' '.join([str(p) for p in soup.select('.lb-widget-text p')]))

            # if we tried once with the waybackmachine and still not succeeding, break the while loop
            if tried_wayback == True:
                waybackCheck(news_link, title, body)
                title = news_link
                break
                
            # if the title cant be found, try the waybackmachine url
            if body == '' and tried_wayback == False:
                soup = try_wayback_machine(news_link)
                if soup_is_string(soup) == True : break
                tried_wayback = True
    
    return title.strip(), body.strip(), misc, url_status


###################################################
############## START HERE

# logging
all_errors_new = {}
file_errors_new = open(logs_dir + 'errors-new.txt','w+', encoding='utf8')
all_errors_parsing = {}
file_errors_parsing = open(logs_dir + 'errors-parsing.txt','w+', encoding='utf8')
all_errors_404 = {}
file_errors_404 = open(logs_dir + 'errors-404.txt','w+', encoding='utf8')
all_errors_robot = {}
file_errors_robot = open(logs_dir + 'errors-robot.txt','w+', encoding='utf8')
all_errors_non_articles = {}
file_errors_non_articles = open(logs_dir + 'errors-non-articles.txt','w+', encoding='utf8')
all_errors_subs = {}
file_errors_subs = open(logs_dir + 'errors-subscription.txt','w+', encoding='utf8')
file_time_none = open(logs_dir + 'time-none.txt','w+', encoding='utf8')
file_summary = open(logs_dir + 'summary.txt','w+', encoding='utf8')
date = datetime.datetime.now().strftime("%Y-%m-%d")

open(logs_dir + 'wayback-machine-success.txt','w+', encoding='utf8').close()
open(logs_dir + 'wayback-machine-fail.txt','w+', encoding='utf8').close()

# pickle file (old and new)
current_pickle_file = 'current.pickle' # will be checked as a cache to not fetch articles that we already have
new_pickle_file = 'newest.pickle' # will contain all the cache + new fetched articles

error_pickle_file = 'error.pickle'

#######################
#######################
##### IMPORTANT
##### At every run of the program, manuallydelete current.pickle, and rename newest.pickle to current.pickle
#######################
#######################
if os.path.isfile(output_pickle_dir + current_pickle_file):    
    with open(output_pickle_dir + current_pickle_file, 'rb') as f:
        [storyItemsOld, oldNewsKeys] = pickle.load(f)
else:
    oldNewsKeys = {}
    storyItemsOld = []

# error pickle
if os.path.isfile(output_pickle_dir + error_pickle_file):    
    with open(output_pickle_dir + error_pickle_file, 'rb') as f:
        pickleErrors = pickle.load(f)
else:
    pickleErrors = []

# Fetch all stories' urls
# assuming max 3 stories per url (some have less)
actual_stories_total = 0

stories_csv_file = output_dir + "stories.csv"

num_lines = sum(1 for line in open(stories_csv_file, encoding='utf8', newline='')) - 2 # 2 > the csv header and the last empty line
stories_total = num_lines * 3   

with open(stories_csv_file, encoding='utf8', newline='') as f:
    reader = csv.DictReader(f, delimiter=',', quoting=csv.QUOTE_ALL)

    # skip header
    skip_header_line = next(reader)
    c = 0
    for story_data in reader:
        # if c == 2:
            # break
        c += 1
        story_url = story_data['url']
        story_title = story_data['title']
        story_topics = story_data['topics']

        print (str(story_counter) + str(': ~') + str(stories_total))
        
        story_soup = BeautifulSoup(get_html(story_url), 'html.parser')
        
        print ("----- " + str(story_url))
        
        if isinstance(story_soup, bool):
            print("Error in fetching main story")
            continue
        
        if len(story_soup.select('h1.taxonomy-heading')) < 1:
            continue

        story_des = ''
        if len(story_soup.find_all('div', class_ = 'story-id-page-description')) > 0:
            if len(story_soup.find_all('div', class_ = 'story-id-page-description')[0].find_all('p')) > 0:
                story_des = story_soup.find_all('div', class_ = 'story-id-page-description')[0].find_all('p')[0].contents[0]
        
        # Parse the news page on allsides.com
        # example url page: https://www.allsides.com/story/government-shutdown-looms-0
        
        news_bias_list = ''
        news_title_links = ''
        news_body = ''
        news_sources = ''
        
        if len(story_soup.find_all('div', class_ = 'global-bias')) > 0:
            news_bias_list = story_soup.find_all('div', class_ = 'global-bias')
        
        if len(story_soup.find_all('div', class_ = 'news-title')) > 0:
            news_title_links = story_soup.find_all('div', class_ = 'news-title')
        
        if len(story_soup.find_all('div', class_ = 'news-body')) > 0:
            news_body = story_soup.find_all('div', class_ = 'news-body')
        
        if len(story_soup.find_all('div', class_ = 'news-source')) > 0:
            news_sources = story_soup.find_all('div', class_ = 'news-source')

        newsItem = []
        news_sources_size = len(news_sources)

        for i in range(news_sources_size):
        
            is_page_not_article = False
            url_status = True
            news_link = ''
            news_bias = ''
            news_title = ''
            news_body = ''
            news_source = ''
            
            # keep these try / except standalone (don't group them into one try/except)
            try:
                news_bias = news_bias_list[i].contents[0].strip()
            except:
                pass
            
            try:
                if len(news_title_links[i].find_all("a", href=True)) != 0:
                    news_title = news_title_links[i].find_all("a", href=True)[0].contents[0].strip()
                    news_link = news_title_links[i].find_all("a", href=True)[0]['href'].strip()
            except:
                pass
            
            print(news_link)
            
            try:
                if len(news_body[i].select('p')) > 0:
                      news_body = news_body[i].select('p')[0].contents[0].strip()
            except:
                pass
            
            try:
                if len(news_sources[i].find_all("a", href=True)) != 0:
                    news_source = news_sources[i].find_all("a", href=True)[0].contents[0].strip()
            except:
                pass
            
            if news_source == 'New York Times' and news_title == 'Republican Tax Bill Passes Senate in 51-48 Vote':
                news_link = 'https://www.nytimes.com/2017/12/19/us/politics/tax-bill-vote-congress.html'
            
            # domain
            domain = news_link.replace('https://','').replace('http://','').split('/')[0].replace('www.','')
            # backup domain
            domain_original = domain
            
            subdomain = ''
            if domain.count('.') == 2:
                subdomain = domain.split('.', 1)[0]
                domain = domain.split('.', 1)[1] # example: blogs.wsj.com (domain is wsj.com)
            elif domain.count('.') == 3:
                domain = domain.split('.', 2)[2] # example: uk.blogs.wsj.com (domain is wsj.com)

            # Entry is in error cache
            if news_link in pickleErrors:
                print ('-- skipped - error cache')
                pickleErrors.append(news_link)
                fetched_from_error_cache = fetched_from_error_cache + 1

            # skip some domains (subscription)
            elif domain == 'npr.org' or domain == 'mismatch.org' or domain == 'dailycaller.com' or domain == 'slate.com' or domain == 'washingtonpost.com' or domain == 'yahoo.com' or domain == 'allsides.com' or domain == 'wsj.com' or news_source == 'Wikipedia' or domain == 'nationaljournal.com' or domain == 'forbes.com':
                
                if news_source not in all_errors_subs:
                    all_errors_subs[news_source] = []
                all_errors_subs[news_source].append(news_link)
                
                pickleErrors.append(news_link)
                fetched_from_error_cache = fetched_from_error_cache + 1
            
            elif news_link != '':
            
                # Already in cache
                if news_link in oldNewsKeys:
                    print ('-- fetched from cache')
                    already_fetched = True
                    news_loc = oldNewsKeys[news_link]
                    oriTitle = storyItemsOld[news_loc[0]][news_loc[1]][4]
                    oriBody = storyItemsOld[news_loc[0]][news_loc[1]][5]
                    oriMisc = storyItemsOld[news_loc[0]][news_loc[1]][6]
                
                else:
                    already_fetched = False
                    actual_stories_total = actual_stories_total + 1

                    oriTitle = ''
                    oriBody = ''
                    oriMisc = ''

                    url_status_code = ""
                    
                    try:
                        url_params = news_link.replace('https://','').replace('http://','').split('/')
                        url_param_1 = url_params[1]
                        url_param_2 = url_params[2].strip() if len(url_params) > 2 else ""
                        
                        if domain == 'youtube.com':
                            is_page_not_article = True

                        #####################
                        # Domains with the configuration-file-based parsing
                        # Config files (.txt) can be found under the config directory in the project root
                        #####################
                        if domain == 'americanthinker.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("americanthinker", news_link)
                        elif domain == 'axios.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("axios", news_link)
                        elif domain == 'lifehacker.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("lifehacker", news_link)
                        elif domain == 'vanityfair.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("vanityfair", news_link)
                        elif domain == 'bloomberg.com' or domain == 'businessweek.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("bloomberg", news_link)
                        elif domain == 'usnews.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("usnews", news_link)
                        elif domain == 'apnews.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("apnews", news_link)
                        elif domain == 'aim.org':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("aim", news_link)
                        elif domain == 'vice.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("vice", news_link)
                        elif domain == 'sfgate.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("sfgate", news_link)
                        elif domain == 'democracynow.org':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("democracynow", news_link)
                        elif domain == 'bbc.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("bbc", news_link)
                        elif domain == 'spectator.org':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("spectator", news_link)
                        elif domain == 'chicagotribune.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("chicagotribune", news_link)
                        elif domain == 'mediaite.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("mediaite", news_link)
                        elif domain == 'dailykos.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("dailykos", news_link)
                        elif domain_original == 'dailymail.co.uk':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("dailymailuk", news_link)
                        elif domain == 'sunlightfoundation.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("sunlightfoundation", news_link)
                        elif domain == 'csmonitor.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("csmonitor", news_link)
                        elif domain == 'reason.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("reason", news_link)
                        elif domain == 'politifact.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("politifact", news_link)
                        elif domain == 'foxnews.com':
                            if subdomain == 'video':
                                is_page_not_article = True
                            if url_param_1 == 'insider':
                                oriTitle, oriBody, oriMisc, url_status = getNews_Fox_News_insider(news_link)
                            else:
                                oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("foxnews", news_link)
                        elif news_source == 'CBN' or domain == 'cbn.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("cbn", news_link)
                        elif domain == 'politico.eu':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("politico-eu", news_link)
                        elif domain == 'politico.com':
                            if url_param_1 == 'magazine':
                                is_page_not_article = True
                            else:
                                oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("politico", news_link)
                        elif domain == 'theblaze.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("blaze", news_link)
                        elif domain == 'time.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("time", news_link)
                        elif domain == 'mrc.org':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("mrc", news_link)
                        elif domain == 'businessinsider.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("business-insider", news_link)
                        elif domain == 'newsmax.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("newsmax", news_link)
                        elif domain == 'cbsnews.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("cbsnews", news_link)
                        elif domain == 'buzzfeed.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("buzzfeed", news_link)
                        elif domain == 'buzzfeednews.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("buzzfeednews", news_link)
                        elif domain == 'huffingtonpost.com' or domain == 'huffpost.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("huffingtonpost", news_link)
                        elif news_source == 'Ben Shapiro':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("ben-shapiro", news_link)
                        elif domain == 'freebeacon.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("washingtonfreebeacon", news_link)
                        elif domain == 'aljazeera.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("aljazeera", news_link)
                        elif domain == 'nydailynews.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("nydailynews", news_link)
                        elif domain_original == 'abcnews.go.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("abcnews", news_link)
                        elif domain == 'bustle.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("bustle", news_link)
                        elif domain == 'nytimes.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("nytimes", news_link)
                        elif domain == 'foxbusiness.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("foxbusiness", news_link)
                        elif domain == 'newyorker.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("newyorker", news_link)
                        elif domain == 'latimes.com':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("latimes", news_link)
                        elif domain == 'washingtontimes.com':
                            if url_param_1 == 'multimedia':
                                is_page_not_article = True
                            elif url_param_1 == 'elections' and url_param_2 == '':
                                is_page_not_article = True
                            else:
                                oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("washingtontimes", news_link)
                        elif domain == 'watchdog.org':
                            oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("watchdog", news_link)
                        elif domain == 'opensecrets.org':
                            if url_param_1 == 'orgs':
                                is_page_not_article = True
                            else:
                                oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("opensecrets". news_link)
                        elif news_source == 'Townhall' or news_source == 'Thomas Sowell' or domain == 'townhall.com':
                            if url_param_1 == 'video' or subdomain == 'media':
                                is_page_not_article = True
                            else:
                                oriTitle, oriBody, oriMisc, url_status, url_status_code = process_url("townhall", news_link)

                        elif news_source == 'TechCrunch':
                            oriTitle, oriBody, oriMisc, url_status = getNews_TechCrunch(news_link)
                        elif news_source == 'MSNBC':
                            oriTitle, oriBody, oriMisc, url_status = getNews_MSNBC(news_link)
                        elif news_source == 'The Independent':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Independent(news_link)
                        elif news_source == 'Cato Institute (blog)':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Cato_Institute_Blog(news_link)
                        elif news_source == 'The Boston Globe':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Boston_Globe(news_link)
                        elif news_source == 'The Nation':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Nation(news_link)
                        elif domain == 'pando.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Pando(news_link) 
                        elif domain == 'theintercept.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Intercept(news_link) 
                        elif domain == 'nationalinterest.org':
                            oriTitle, oriBody, oriMisc, url_status = getNews_National_Interest(news_link)
                        elif domain == 'thedailybeast.com':
                            if url_param_1 == 'cheats':
                                oriTitle, oriBody, oriMisc, url_status = getNews_Daily_Beast_Cheats(news_link)
                            else:
                                oriTitle, oriBody, oriMisc, url_status = getNews_Daily_Beast(news_link)
                        elif news_source == 'HotAir':
                            oriTitle, oriBody, oriMisc, url_status = getNews_HotAir(news_link)
                        elif news_source == 'KSL':
                            oriTitle, oriBody, oriMisc, url_status = getNews_KSL(news_link)
                        elif domain == 'mashable.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Mashable(news_link)
                        elif news_source == 'Independent Journal Review' or domain == 'ijr.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Independent_Journal_Review(news_link)
                        elif news_source == 'The Week' or domain == 'theweek.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Week(news_link)
                        elif domain == 'nbcnews.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_NBC_News(news_link)
                        elif news_source == 'Newsweek':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Newsweek(news_link)
                        elif domain == 'factcheck.org':
                            oriTitle, oriBody, oriMisc, url_status = getNews_FactCheck(news_link)
                        elif domain == 'cnbc.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_CNBC(news_link)
                        elif domain == 'theatlantic.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Atlantic(news_link)
                        elif domain == 'motherjones.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Mother_Jones(news_link)
                        elif news_source == 'Media Matters':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Media_Matters(news_link)
                        elif news_source == 'Jeff Jacoby':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Jeff_Jacoby(news_link)
                        elif domain == 'nymag.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_New_York_Magazine(news_link)
                        elif news_source == 'Las Vegas Sun':
                            oriTitle, oriBody, oriMisc, url_status = getNews_LastVegasSun(news_link)
                        elif news_source == 'National Review' or domain == 'nationalreview.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_National_Review(news_link)
                        elif news_source == 'Vox':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Vox(news_link)
                        elif domain == 'usatoday.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_USA_TODAY(news_link)
                        elif domain == 'thefederalist.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Federalist(news_link)
                        elif domain == 'washingtonpost.com':
                            if url_param_1 == 'graphics':
                                oriTitle, oriBody, oriMisc, url_status = getNews_Washington_Post_graphics(news_link)
                            else:
                                oriTitle, oriBody, oriMisc, url_status = getNews_Washington_Post_news(news_link)
                        elif domain == 'reuters.com':
                            if news_link == 'uk.mobile.reuters.com':
                                oriTitle, oriBody, oriMisc, url_status = getNews_Reuters_Mobile(news_link)
                            else:
                                oriTitle, oriBody, oriMisc, url_status = getNews_Reuters(news_link)
                        elif domain == 'latino.foxnews.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Fox_News_Latino(news_link)
                        elif news_source == 'The Daily Caller':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Daily_Caller(news_link)
                        elif domain == 'people-press.org':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Pew_Research(news_link)
                        elif domain == 'cnsnews.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_CNSNews(news_link)
                        elif domain == 'nypost.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_New_York_Post(news_link)
                        elif domain == 'realclearpolitics.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_RealClearPolitics(news_link)
                        elif domain == 'thehill.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Hill(news_link)    
                        elif domain == 'thinkprogress.org':
                            oriTitle, oriBody, oriMisc, url_status = getNews_ThinkProgress(news_link)
                        elif domain == 'cnn.com':
                            if url_param_1 == 'videos' or url_param_1 == 'video' or url_param_2 == 'live-news':
                                is_page_not_article = True
                            else:
                                oriTitle, oriBody, oriMisc, url_status = getNews_CNN_Web_News(news_link)
                        elif domain == 'washingtonexaminer.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Washington_Examiner(news_link)
                        elif news_source == 'PBS NewsHour':
                            oriTitle, oriBody, oriMisc, url_status = getNews_PBS_NewsHour(news_link)
                        elif news_source == 'The Guardian':
                            oriTitle, oriBody, oriMisc, url_status = getNews_The_Guardian(news_link)
                        elif news_source == 'Breitbart News':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Breitbart_News(news_link)
                        elif news_source == 'Slate':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Slate(news_link)
                        elif news_source == 'NPR News' or domain == 'npr.org':
                            oriTitle, oriBody, oriMisc, url_status = getNews_NPR_News(news_link)
                        elif news_source == 'Salon':
                            oriTitle, oriBody, oriMisc, url_status = getNews_Salon(news_link)
                        elif domain == 'ibtimes.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_IB_Times(news_link)
                        elif news_source == 'WND.com':
                            oriTitle, oriBody, oriMisc, url_status = getNews_WND_com(news_link)
                        else:
                            print ('-- unknown website')
                            errors_new = errors_new + 1
                            file_errors_new.write(news_source + ',' + news_link + '\n')
                                
                    except:
                        print ('Failed')
                
                if is_page_not_article == True:
                    if news_source not in all_errors_non_articles:
                        all_errors_non_articles[news_source] = []
                    all_errors_non_articles[news_source].append(news_link)
                    pickleErrors.append(news_link)

                elif url_status == False:
                    if url_status_code == "404":
                        if news_source not in all_errors_404:
                            all_errors_404[news_source] = []
                        all_errors_404[news_source].append(news_link)
                        pickleErrors.append(news_link)
                    elif url_status_code == "robot_blocked":
                        if news_source not in all_errors_robot:
                            all_errors_robot[news_source] = []
                        all_errors_robot[news_source].append(news_link)
                        pickleErrors.append(news_link)
                    else:
                        if news_source not in all_errors_parsing:
                            all_errors_parsing[news_source] = []
                        all_errors_parsing[news_source].append(news_link)
                
                # URL parsing fails
                elif oriBody == '':
                    if news_source not in all_errors_parsing:
                        all_errors_parsing[news_source] = []
                    all_errors_parsing[news_source].append(news_link)
            
                # Success, save article
                else:
                    oriBody = removeHeading(oriBody)
                    oriBody = removeEmail(oriBody)
                    oriBody = removeListing(oriBody)
                    
                    if len(oriBody.split('\n')) > 0:
                        oriBody = '\n'.join([l for l in oriBody.split('\n') if l != ''])
                            
                    # ocd check on body
                    if oriBody == '':
                        if news_source not in all_errors_parsing:
                            all_errors_parsing[news_source] = []
                        all_errors_parsing[news_source].append(news_link)
                    
                    else:
                 
                        if 'summary' in oriMisc:
                            oriMisc['summary'] = removeListing(oriMisc['summary'])
                        if 'subtitle' in oriMisc:
                            oriMisc['subtitle'] = removeListing(oriMisc['subtitle'])
                        if 'author' in oriMisc:
                            # try:
                            oriMisc['author'] = [str(a) for a in oriMisc['author']]
                            # except UnicodeError:
                            #     oriMisc['author'] = [str(a) for a in oriMisc['author']]
                                
                        # debug authors
                        if 'author' in oriMisc and len(oriMisc['author']) > 0:
                            if len(oriMisc['author'][0]) == 1:
                                oriMisc['author'] = ''.join(oriMisc['author']).replace('by','').split(',')[0].split(' and ')
                        
                        #debug time
                        if 'time' in oriMisc:
                        
                            # cleanup
                            if not isinstance(oriMisc['time'], datetime.datetime):
                                # time = unicode(oriMisc['time'].encode("utf-8"), 'utf8')
                                # time = time.encode('utf8', 'replace')
                                time = str(oriMisc["time"])
                                time = time.replace('Z','')
                                time = time.replace(': ', ' ')
                            else:
                                time = oriMisc['time'].replace(tzinfo=None)
                                time = time.strftime('%Y-%m-%d %H:%M:%S')
                                
                            time_parsed = ''
                            
                            # fix 1
                            fix_1 = re.findall(r'([\(\[]).*?([\)\]])', time)
                            if len(fix_1) > 0:
                                time = re.sub("([\(\[]).*?([\)\]])", "", time).strip().replace('  ',' ')
                                time = time[:2] + ':' + time[2:]
                                time_parsed = dateparser.parse(time, date_formats=['%H:%M %Z %B %d, %Y'])
                            else:
                                time_parsed = dateparser.parse(time)
                            
                            # log failed time (empty or None)
                            if time_parsed == '' or time_parsed == None:
                                file_time_none.write( str(news_link) + "," + str(time) + '\n')
                            
                            # write back to string variable to the array
                            oriMisc['time'] = str(time_parsed)

                        # Topics
                        oriMisc['topics'] = story_topics

                        newskeys[news_link] = (len(storyItems),len(newsItem))
                        newsItem.append((news_bias, news_title, news_body, news_source, oriTitle, oriBody, oriMisc))

                        if already_fetched == False:
                            new_fetched = new_fetched + 1
                            print('-- Saved\n')
                        else:
                            fetched_from_cache = fetched_from_cache + 1
                            print ('-- Saved from cache\n')
            
        print ('---------------------')
            
        story_counter = story_counter + 1
        storyItems.append(newsItem)
f.close()

# Save stories
stories_output = [storyItems, newskeys]
with open(output_pickle_dir + new_pickle_file, 'wb') as f:  
    pickle.dump(stories_output, f, pickle.HIGHEST_PROTOCOL)
f.close()

# save stories as dataframe csv
stories_docs = convert_to_df(stories_output)
stories_docs.to_csv(output_df_path, index=False) 

# Save error stories
with open(output_pickle_dir + error_pickle_file, 'wb') as f:  
    pickle.dump(pickleErrors, f, pickle.HIGHEST_PROTOCOL)
f.close()

# write errors to files

for key in sorted(all_errors_non_articles.keys()):
    urls = all_errors_non_articles[key]
    for url in urls:
        file_errors_non_articles.write(key + ',' + url + '\n')
file_errors_non_articles.close()

for key in sorted(all_errors_new.keys()):
    urls = all_errors_new[key]
    for url in urls:
        file_errors_new.write(key + ',' + url + '\n')
file_errors_new.close()

for key in sorted(all_errors_parsing.keys()):
    urls = all_errors_parsing[key]
    for url in urls:
        file_errors_parsing.write(key + ',' + url + '\n')
file_errors_parsing.close()

for key in sorted(all_errors_404.keys()):
    urls = all_errors_404[key]
    for url in urls:
        file_errors_404.write(key + ',' + url + '\n')
file_errors_404.close()

for key in sorted(all_errors_robot.keys()):
    urls = all_errors_robot[key]
    for url in urls:
        file_errors_robot.write(key + ',' + url + '\n')
file_errors_robot.close()

for key in sorted(all_errors_subs.keys()):
    urls = all_errors_subs[key]
    for url in urls:
        file_errors_subs.write(key + ',' + url + '\n')
file_errors_subs.close()

# Logs
total_robot = sum(len(v) for v in all_errors_robot.values())
total_404 = sum(len(v) for v in all_errors_404.values())
total_subs = sum(len(v) for v in all_errors_subs.values())
total_parsing = sum(len(v) for v in all_errors_parsing.values())
total_new = sum(len(v) for v in all_errors_new.values())
total_non_articles = sum(len(v) for v in all_errors_non_articles.values())

all_errors = total_robot + total_404 + total_subs + total_parsing + total_new + total_non_articles

print_a = []
print_a.append("Total Stories: " + str(stories_total) + "\n")
print_a.append("Skipped from error cache: " + str(fetched_from_error_cache) + "\n")
print_a.append("Stories that can be fetched: " + str(actual_stories_total) + "\n")
print_a.append("Saved from cache: " + str(fetched_from_cache) + "\n")
print_a.append("Saved new: " + str(new_fetched) + "\n")
print_a.append("Total Saved: " + str(new_fetched + fetched_from_cache) + "\n")
print_a.append("Total Errors: " + str(all_errors) + "\n")
print_a.append("---- Robot blocked: " + str(total_robot) + "\n")
print_a.append("---- 404: " + str(total_404) + "\n")
print_a.append("---- Subscription: " + str(total_subs) + "\n")
print_a.append("---- Parsing: " + str(total_parsing) + "\n")
print_a.append("---- New: " + str(total_new) + "\n")
print_a.append("Wayback - Success: " + str(wayback_success) + "\n")
print_a.append("Wayback - Fail: " + str(wayback_fail) + "\n")

for s in print_a:
    print (s)
    file_summary.write(s)
# end logs

# close files
file_time_none.close()
file_summary.close()