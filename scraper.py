import re
import logging
from urllib.parse import urlparse, urljoin, parse_qs
from bs4 import BeautifulSoup
from utils.constants import stopwords, seed_urls
import urllib.robotparser
from collections import defaultdict
import copy


unique_pages = set()
longest_page = {'url': 'default', 'length': 0}
word_frequency = defaultdict(int)
sub_domains = defaultdict(int)


def scraper(url, resp):
    #if url !=
    links = extract_next_links(url, resp)
    logging_data()
    return links

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    #Initial check 
    if resp.raw_response:
        if url != resp.raw_response.url:
            if url not in resp.raw_response.url:
                log_invalid(url, 'Redirection of url')
                return list()

        
    if url != resp.url or resp.status != 200: 
        return list()
        
    # Check for Less quality pages
    if not is_high_quality(resp):
        return list()

    linked_pages = set()
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")

    for a_tag in soup.findAll("a"):
        href = a_tag.attrs.get("href")

        if href is None:
            continue
        
        possibleInd = href.find('#')
        if possibleInd != -1:
            href = href[:possibleInd]

        href = modify_if_relative(href,url)

        condition, reason = is_valid(href)
        
        if condition:
            linked_pages.add(href)
        elif reason != "Non-seed-url":
            log_invalid(href, reason)
    
    ## Returning Delivrables for this url
    deliverables(url,resp)
    return list(linked_pages)

def log_invalid(url, reason):
    logger = logging.getLogger('invalid')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('invalid_url.log')
    formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(f"Invalid url - {url},Reason - {reason}")

def modify_if_relative(relative_url,parent_url):
    if relative_url and (relative_url.startswith("/") or relative_url.startswith("../")):
        path_levels = relative_url.count("../")

        parent_components = urlparse(parent_url)
        parent_domain = f"{parent_components.scheme}://{parent_components.netloc}"
        parent_path = parent_components.path

        if relative_url.startswith("/"):
            return urljoin(parent_domain, parent_path + "/" + relative_url)

        # Remove that many directory levels from base path
        for i in range(path_levels):
            parent_components = urlparse(parent_path)
            parent_path = parent_components.path.rsplit("/", 1)[0]
        
        parent_url = urljoin(parent_domain,parent_path)

        return urljoin(parent_url,relative_url.split("/../")[-1])
    return relative_url

def can_crawl(url, parsed):
    # checking robots.txt
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url("http://" + parsed.netloc + "/robots.txt")
        rp.read()
        return rp.can_fetch("*", url)
    except:
        # means that there is no robots.txt for that website
        return True

def is_trap(parsed):
    # was able to identify what causes traps and get regular expressions from:
    # https://support.archive-it.org/hc/en-us/articles/208332943-Identify-and-avoid-crawler-traps-

    # long url traps
    if len(str(parsed.geturl())) > 200:
        return True, "Long url traps"

    # duplicate url traps
    path_segments = parsed.path.lower().split("/")
    path_segments = path_segments[1:]
    
    REPEATER = re.compile(r"(.+/)\1+")
    match = REPEATER.findall(f"{parsed.geturl()}/")
    
    if(len(match) > 0):
        return True, "Duplicate Path Trap"
    

    # Check for Session ID traps
    if "session" in path_segments or "session" in parsed.query:   
        return True, "Session Trap"


    # repeating directories
    if re.match("^.*?(/.+?/).*?\1.*$|^.*?/(.+?/)\2.*$", parsed.path):
        return True, "Repeating Directories Trap"

    # extra directories
    if re.match("^.*(/misc|/sites|/all|/themes|/modules|/profiles|/css|/field|/node|/theme){3}.*$", parsed.path):
        return True, "Extra Directories Trap"

    # empty
    if parsed is None:
        return False, ""
    
    #dynamic trap check
    url_query = parsed.query
    if url_query != "":
        query_params = parse_qs(url_query)
        if len(query_params) > 7:
            return True, "Dynamic Trap"

    # avoid club pages have events from too early
    if re.match(r".*(calendar|date|gallery|image|wp-content|pdf|img_).*?$", parsed.path.lower()):
        return True, "Club Page Trap"

    # avoid informatics' monthly archives
    if re.match(r".*\/20\d\d-\d\d*", parsed.path.lower()):
        return True, "Month Trap"

    # no event calendars
    if "/event/" in parsed.path or "/events/" in parsed.path:
        return True, "Calendar Trap"
    return False, ""

def is_high_quality(resp):
    try:
        # checks if high quality by amount of text
        amount_of_text = len(get_text(resp))
        if amount_of_text > 100:
            return True
        return False
    except:
        return False

def get_text(resp):
    # scraps entire webpage's text and tokenizes
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    words = soup.get_text(" ", strip=True)
    words = words.lower()
    words = re.sub('[^A-Za-z0-9]+', ' ', words)

    # takes all duplicates out
    word_list = words.split()
    word_set = set(word_list)
    copy_set = copy.deepcopy(word_set)

    # removes words that shouldn't be considered
    for word in copy_set:
        if len(word) < 3:
            word_set.remove(word)
    return word_set

def deliverables(url, resp):
    global unique_pages
    global longest_page
    global word_frequency
    global sub_domains
    global stopwords

    try:
        text = get_text(resp)
    except:
        text = 0
    
    parsed = urlparse(url)
    page = parsed.scheme + "://" + parsed.netloc + parsed.path

   # increments unique urls to find total
    unique_pages.add(page)

    # compares for longest page
    if len(text) > longest_page['length']:
        longest_page['length'] = len(text)
        longest_page['url'] = page

    # finds most common word
    for word in text:
        if word not in stopwords:
            word_frequency[word] += 1
    
    #finding no of subdomains in ics.uci.edu
    if url.find('ics.uci.edu') > 0:
        sub_domains[page] += 1
        
def logging_data():
    top50 = list(sorted(word_frequency.items(), key=lambda x: x[1], reverse=True))[:50]
    logger = logging.getLogger('report')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('report_data.log')
    formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(f"Unique Pages:{len(unique_pages)}, Longest Page:{longest_page['url']} of len {longest_page['length']}\n"
                f"Most Common:{top50}\nSubDomains: {sub_domains}")

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.

    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False, "Https missing"
        
        #Checking if url exists in seed_urls
        if not any(check_url in url for check_url in seed_urls):
            return False, "Non-seed-url"

        if not can_crawl(url, parsed):
            return False, "Non crawllable"

        #Checking if trap exist in url
        trap_bool, trap_reason = is_trap(parsed)
        if trap_bool:
            return False, f"Is a Trap - {trap_reason}"
        
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False, "Re Matching Failed"
    
        return True, ""

    except TypeError:
        print ("TypeError for ", parsed)
        raise


def generate_report_txt():
    unique_pages_found = list(unique_pages)
    
    with open('report.txt', 'w') as report:
        print("number of unique pages found: "+ str(len(unique_pages_found)))

        report.write("------------------Report------------------"+ "\n")
        report.write("" + "\n")

        report.write("------------------QUESTION #1------------------"+"\n")
        report.write("Unique pages found: " + str(len(unique_pages_found)) + "\n")
        report.write("" + "\n")
        report.write("" + "\n")

        report.write("------------------QUESTION #2------------------"+"\n")
        #report.write("URL with the largest word count: "+ max(unique_pages_found, key=unique_pages_found.get) + "\n")
        if unique_pages_found:
            #max_url = max(unique_pages_found, key=unique_pages_found.get)
            report.write("URL with the largest word count: " + longest_page['url'] + "\n")
        else:
            report.write("No URLs found with word count. The dictionary is empty.\n")
        report.write("" + "\n")
        report.write("" + "\n")

        report.write("------------------QUESTION #3------------------"+"\n")
        report.write("The following are the 50 most common words" + "\n")
        top_50_words = sorted(word_frequency.items(), key=lambda item: item[1], reverse=True)[:50]
        for word, frequency in top_50_words:
            report.write(f"Word: {word} - Frequency: {frequency}" + "\n")
        report.write("" + "\n")
        report.write("" + "\n")

        report.write("------------------QUESTION #4------------------"+"\n")
        report.write("Number of subdomains in the ics.uci.edu domain: " + str(len(sub_domains.keys()))+ "\n")
        sorted_subdomains = sorted(sub_domains.keys())
        for subdomain in sorted_subdomains:
            num_pages = sub_domains[subdomain]
            report.write(f"{subdomain}, {num_pages}\n")
        report.write("" + "\n")
        report.write("" + "\n")