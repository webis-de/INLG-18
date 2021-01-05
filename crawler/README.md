# Python 3

# Description

Crawl and save the data of all news articles on allsides.com. Every news article has a sub-list of 3 articles (on external websites) categorized as "center", "left" or "right" bias of the news article.

# Process

**1- (Optional) config/*.txt**

Some websites are crawled via rules in a text file, while others are crawled via a function in the src/run.py file.

**2- (Required) src/get_list_of_stories.py:**

Fetch all the news articles with their topics and sub-articles (center, left or right).
The results are saved as a CSV file under "results/stories.csv"

**3- (Required) src/run.py:**

Crawl and fetch the data of the news articles list fetched from point 1.

- This creates a results pickle file "newest.pickle" under results/pickle.
- The previous results pickle file "current.pickle" contains the results of the previous run.
- When satisfied with the latest results of "newest.pickle", delete "current.pickle" and rename "newest.pickle" as "current.pickle".
- Log files can be found under results/logs/*.txt

**4- (Optional) src/test_fetch_site.py:**

Debug the crawling process of a single article URL.

**5- (Optional) Other files**

Optional test / old / unused files.

**6- ml/*

Directory for machine learning experiments using the allsides data or other data.

** ml/d2v
Doc-to-vec vectors

** ml/lda
Lda vectors

** ml/experiment-allsides
Use LSH + SVC to find similar documents in the allsides data

** ml/experiment-hyperpartisan
Find similar documents in the Hyperpartisan dataset using our models
