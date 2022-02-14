from selenium import webdriver
import time
import re
import requests
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC 
from selenium.webdriver.common.by import By
import json
import math
from concurrent.futures import ThreadPoolExecutor
import threading
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass
class ProductItem:
    text: str

options = webdriver.ChromeOptions()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--incognito')
options.add_argument("--disable-geolocation")
# options.add_argument('--headless')

# 0 - Default, 1 - Allow, 2 - Block
options.add_experimental_option("prefs", { "profile.default_content_setting_values.geolocation": 2})

token = ""
def notify(title, message, link):
    requests.post("https://ha.rsymington.com/api/events/alert", headers={
        "Authorization": f"Bearer {token}"
    }, json={
        "title": title,
        "message": message,
        "clickAction": link
    })

# notify("test", "testing", "https://google.com")

def get_products(driver: WebDriver, rootSelector: str, selectors: dict):
    products = driver.find_elements_by_css_selector(rootSelector)
    ret = []
    for product in products:
        selObj = {}
        for k, sel in selectors.items():
            try:
                selObj[k] = product.find_element_by_css_selector(sel)
            except:
                selObj[k] = ProductItem(**{"text": ""})
        ret.append(selObj)
    return ret


def extract_products(url: str, pages: bool, loadmore: bool, pageSelector: str, rootSelector: str, selectors: dict, maxPages=10):
    maxPages=float(maxPages)
    ret = []

    driver = webdriver.Chrome("./chromedriver.exe", chrome_options=options)
    driver.get(url)

    if pages:
        if loadmore:
            p=0
            try:
                while p < maxPages and (el:=WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, pageSelector)))):
                    driver.execute_script("arguments[0].click();", el)
                    p+=1
            except Exception as e:
                pass

            ret = get_products(driver, rootSelector, selectors)
        else:
            p=0
            try:
                while p < maxPages and (el:=WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, pageSelector)))):
                    driver.execute_script("arguments[0].click();", el)
                    p+=1

                    ret += get_products(driver, rootSelector, selectors)
            except Exception as e:
                pass
    else:
        el = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, rootSelector)))
        ret += get_products(driver, rootSelector, selectors)
    return (driver, ret)

def product_filter(product: dict, filterDict: dict):
    filterResults=[]
    for k, filters in filterDict.items():
        for filter in filters:
            regex, exists = filter
            
            match = re.search(f"{regex}", product[k].text, re.IGNORECASE)
            if exists and match:
                filterResults.append(True)
            elif not (exists or match):
                filterResults.append(True)
            else:
                filterResults.append(False)
    return all(filterResults)

def _s(product, url: str, rootSelector: str,
selectors: dict, filterDict: dict, pages: bool, loadmore: bool = True, _scrape: dict = None, pageSelector: str = "", maxPages=10):
    href = product[url].get_attribute("href")    
    try:
        driver, products = extract_products(href, pages, loadmore, pageSelector, rootSelector, selectors, maxPages=maxPages)
        try:
            products = list(filter(lambda product: product_filter(product, filterDict), products))

            product["_scrape"] = products[0]

            if len(products):
                if _scrape:
                    return _s(product["_scrape"], **_scrape)
                else:
                    return True

            return False
        finally:
            driver.close()
    except: 
        return False

def scrape(title: str, url: str, pages: bool, loadmore: bool, pageSelector: str, rootSelector: str,
selectors: dict, filterDict: dict, notifyFilter: list, _scrape: dict = None, maxPages=10, urlSelector: str = None):
    driver, products = extract_products(url, pages, loadmore, pageSelector, rootSelector, selectors, maxPages=maxPages)
    products = list(filter(lambda product: product_filter(product, filterDict), products))
    
    if _scrape:
        products = list(filter(lambda product: _s(product, **_scrape), products))

    if(len(products)):
        for product in products:
            if pages:
                if urlSelector:
                    url = product[urlSelector].get_attribute("href")
            else:
                url = url
            notify(title, product["title"].text, url)
            print(f"{product['price'].text}, {product['title'].text}")
    driver.close()

def task(s):
    while True:
        scrape(**s)
        time.sleep(2*60)

if __name__ == "__main__":
    scrapes = {}
    with open("scrapes.json", "r", encoding="utf-8") as fp:
        scrapes = json.load(fp)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures=[]
        for s in scrapes:
            futures.append(executor.submit(task, (s)))
        for f in futures:
            f.result()
        # time.sleep(2*60)
