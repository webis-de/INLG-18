# -*- coding: utf-8 -*-

from newspaper import Article
import bs4
import requests
from bs4 import SoupStrainer, BeautifulSoup
import urllib3
import csv
import numpy as np
import pandas as pd
import certifi
import pickle, sys, os, time
import re
# from matplotlib.font_manager import pickle_dump
import html2text 
from decimal import getcontext
import random
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

parser = html2text.HTML2Text()
parser.body_width = 0
parser.ignore_links = True
parser.single_line_break = True
parser.ignore_emphasis = True
parser.ignore_images = True

user_agents = []
with open("../misc/user-agents.txt") as file:
    for line in file: 
        line = line.strip()
        user_agents.append(line)

file.close()

def nytseparate(text):
    r = text.replace('____\n','')
    return r

def get_response_content(response):
    return response.text.encode('utf-8')

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
#     pm = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
#     response = pm.urlopen(url=url, method="GET").data

    return response

def waybackCheck(url, title, body):
    v = 1
    
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
    
def try_wayback_machine(url):
    
    soup = ''
    
    global user_agents
    
    base_url = "http://archive.org/wayback/available?url="
    
    print("Checking Wayback Machine ...")
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

    
    # Try newspaper library
    article = Article(url)
    article.download()
    article.parse()

    if article.text and article.title:
        if article.publish_date:
            misc["time"] = article.publish_date.strftime("%Y-%d-%m %H:%M:%S")

        if len(article.authors) > 0:
            misc["author"] = article.authors

        return article.title.strip(), article.text.strip(), misc, url_status, url_status_code

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
            # 404 from the response url
            if "redirect_404" in config and len(config["redirect_404"]) > 0:
                for a in config["redirect_404"]:
                    if response.url.strip("/").endswith(a):
                        url_status = False
                        redirect_html_404 = True

            # 404 from the response url
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
                            print(soup)

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

def soup_is_string(soup_object):
    is_string = False
    if isinstance(soup_object, str):
        is_string = True
        print('Wayback machine - no snapshot of url found')
    return is_string

def test(url):
    return process_url("fox13now", url)

oriBody = ''
oriTitle = ''
oriMisc = ''

newsLink = "https://www.washingtontimes.com/news/2019/may/13/john-durham-appointed-william-barr-investigate-rus/"

domain = newsLink.replace('https://','').replace('http://','').split('/')[0].replace('www.','')
domain_original = domain
print("Domain original: " + str(domain_original))

subdomain = ''
if domain.count('.') == 2:
    subdomain = domain.split('.', 1)[0]
    domain = domain.split('.', 1)[1] # example: blogs.wsj.com (domain is wsj.com)
elif domain.count('.') == 3:
    domain = domain.split('.', 2)[2] # example: uk.blogs.wsj.com (domain is wsj.com)
url_params = newsLink.replace('https://','').replace('http://','').split('/')
url_param_1 = url_params[1]
url_param_2 = url_params[2].strip() if len(url_params) > 2 else ""
print("url_param_1: " + str(url_param_1))
print("url_param_2: " + str(url_param_2))

oriTitle, oriBody, oriMisc, url_status, url_status_code = test(newsLink)

print("Status: " + str(url_status_code))
print(oriTitle + "\n")
print(oriBody)
print(oriMisc)