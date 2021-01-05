import bs4
from bs4 import SoupStrainer, BeautifulSoup
import requests
import urllib
import pickle
import csv
import re, sys, os, time
import random
import datetime

input_dir = "../misc/"
output_dir = "../results/"
pickle_dir = input_dir + "temp/"

user_agents = []
# Get all user agents
with open(input_dir + "user-agents.txt") as file:
    for line in file: 
        line = line.strip()
        user_agents.append(line)
file.close()

def getHtml(url):
    global user_agents
    
    html = requests.get(
        url,
        allow_redirects = True,
        headers = {
            'User-Agent': random.choice(user_agents),
            "Connection" : "close"
        },
        verify = False
    )
    
    return str(html.text)

def save_obj(obj, name):
    with open(pickle_dir + name + '.pkl', 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def check_obj(name):
    return True if os.path.isfile(pickle_dir + name + ".pkl") else False

def load_obj(name):
    with open(pickle_dir + name + '.pkl', 'rb') as f:
        return pickle.load(f)

def run():
    # Fetch stories list
    story_urls_output_file = output_dir + 'stories.csv'

    # Urls
    base_url = 'https://www.allsides.com'
    url = base_url + '/story/admin?page='

    # Fetch and save storylist html
    all_pages_count = 5
    c_page_count = 0

    stories_data = {}
    if check_obj("stories_data") and len(sys.argv) > 1 and sys.argv[1] == "cache":
        print("found stories data in cache..." + str(pickle_dir + "stories_data.pkl"))
        stories_data = load_obj("stories_data")

    else:
        while int(c_page_count) < int(all_pages_count):

            # all pages besides the first one have pagination urls
            current_url = url + str(c_page_count-1)

            print(str(c_page_count+1) + "/" + str(all_pages_count))

            time.sleep(1)
            html = getHtml(current_url)
            soup = BeautifulSoup(html, 'html.parser')

            # get total number of pages (only once)
            if (c_page_count == 0):
                all_pages_count = int(soup.select('.pager-last a')[0]['href'].split("=")[1])

            # get stories
            all_stories = soup.select('#content .views-table tr')

            for story in all_stories:

                if len(story.select("a[href^='/story/']")) > 0:

                    # Story URL
                    story_url = base_url + story.select("a[href^='/story/']")[0]['href']

                    if story_url:
                        if story_url not in stories_data:
                            stories_data[story_url] = {}

                        # Date
                        if len(story.select(".date-display-single")) > 0:
                            stories_data[story_url]['date'] = story.select('.date-display-single')[0].get_text().strip()

                        # URL
                        stories_data[story_url]['url'] = story_url

                        # Title
                        stories_data[story_url]['title'] = story.select("a[href^='/story/']")[0].get_text().strip()

                        # Append Topics
                        if "topics" not in stories_data[story_url]:
                            stories_data[story_url]["topics"] = []

                        if len(story.select(".views-field-field-story-topic a")) > 0:

                            topics = story.select(".views-field-field-story-topic a")
                            for topic in topics:
                                t = topic.get_text().replace(',', '').strip()
                                stories_data[story_url]["topics"].append(t)

            # increment next page
            c_page_count = c_page_count + 1

        save_obj(stories_data, "stories_data")

    ###
    # WRITE TO CSV

    # empty file
    open(story_urls_output_file, 'w').close()

    with open(story_urls_output_file, 'w', encoding='utf-8',newline='') as csvfile:
        fieldnames = ['title', 'url', 'date', 'topics']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, delimiter=',')
        writer.writeheader()

        for story,story_data in stories_data.items():

            # remove duplicates in topics for the same story
            story_data['topics'] = list(set(story_data['topics']))
            topics = ','.join(story_data['topics'])
            
            writer.writerow(
                {
                    'title': story_data['title'],
                    'url': story_data['url'],
                    'date': story_data['date'],
                    'topics': topics,
                }
            )
        
        print("saved stories")
    csvfile.close()

###
run()