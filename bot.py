# Copyright (c) 2025 Kaustav Ray
# This code is proprietary and written by Kaustav Ray.

import logging
import requests
import re
import base64
import json
import codecs
import asyncio
import uuid
import time
import html
import urllib.parse
import threading
import cloudscraper
import random
from flask import Flask
from urllib.parse import urlparse, parse_qs, urljoin, unquote
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- PLAYWRIGHT IMPORT ---
# NOTE: Ensure you have run 'pip install playwright' and 'playwright install chromium'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    logging.warning("Playwright not installed. OxxFile scraper will fail.")

# --- CONFIGURATION ---
TOKEN = "8213744935:AAGo_g4JSj2mrreYYT6yFHIdyYu67P1ZKB8"

# --- LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Global Cache for Search Results
SEARCH_CACHE = {}

# --- FLASK SERVER FOR UPTIMEROBOT ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- HELPER FUNCTIONS ---
def rot13(s):
    return codecs.encode(s, 'rot_13')

# Domain Checkers
def is_hubdrive_url(url): return "hubdrive.space" in url or "hubdrive.me" in url or "hubdrive" in url
def is_hubcloud_url(url): return "hubcloud" in url
def is_gofile_url(url): return "gofile.io" in url
def is_hubcdn_url(url): return "hubcdn" in url and "pixel" not in url
def is_pixel_hubcdn_url(url): return "pixel.hubcdn" in url
def is_vplink_url(url): return "vplink" in url or "short" in url
def is_gplinks_url(url): return "gplinks" in url or "get2.in" in url
def is_skymovieshd_url(url): return "skymovieshd" in url
def is_howblogs_url(url): return "howblogs.xyz" in url
def is_4khdhub_url(url): return "4khdhub.fans" in url
def is_filmyfiy_url(url): return "filmyfiy" in url
def is_vegamovies_url(url): return "vegamovies" in url
def is_katmoviehd_url(url): return "katmovie" in url
def is_mymp4movies_url(url): return "mymp4movies" in url
def is_kmhd_link_url(url): return "links.kmhd.net" in url
def is_pikahd_url(url): return "pikahd" in url
def is_katdrama_url(url): return "katdrama" in url
def is_toonworld4all_url(url): return "toonworld4all" in url
def is_moviesmod_url(url): return "moviesmod" in url or "modpro" in url
def is_animeflix_url(url): return "animeflix" in url
def is_uhdmovies_url(url): return "uhdmovies" in url
def is_cinevood_url(url): return "cinevood" in url or "1cinevood" in url
def is_extraflix_url(url): return "extraflix" in url
def is_extralink_url(url): return "extralink.ink" in url
def is_filepress_url(url): return "filepress" in url
def is_hdwebmovies_url(url): return "hdwebmovies" in url
def is_oxxfile_url(url): return "oxxfile" in url

def get_soup(content):
    """Helper to parse HTML with fallback."""
    try:
        return BeautifulSoup(content, 'lxml')
    except Exception as e:
        logging.warning(f"lxml parsing failed ({e}). Falling back to html.parser.")
        return BeautifulSoup(content, 'html.parser')

def get_poster_url(query):
    try:
        url = "https://www.imdb.com/find/"
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, params={"q": query}, timeout=10)
        response.raise_for_status()
        soup = get_soup(response.content)

        item = soup.find('li', class_='ipc-metadata-list-summary-item')
        if item:
            img = item.find('img', class_='ipc-image')
            link = item.find('a', href=True)

            poster_url = None
            imdb_link = None

            if img and img.get('src'):
                src = img['src']
                if "@" in src:
                    poster_url = src.split("@")[0] + "@.jpg"
                else:
                    poster_url = src

            if link:
                imdb_link = "https://www.imdb.com" + link['href']
                if "?" in imdb_link:
                    imdb_link = imdb_link.split("?")[0]

            if poster_url:
                return poster_url, imdb_link

        img = soup.find('img', class_='ipc-image')
        if img and img.get('src'):
            src = img['src']
            if "@" in src:
                return src.split("@")[0] + "@.jpg", None
            return src, None

    except Exception as e:
        logging.error(f"Poster Scrape Error: {e}")
    return None, None

def get_google_poster_url(query):
    try:
        url = f"https://www.google.com/search?q={query}+movie+poster&tbm=isch"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('https://encrypted-tbn0.gstatic.com'):
                return src

        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('http') and 'google' not in src:
                 return src

    except Exception as e:
        logging.error(f"Google Scrape Error: {e}")
    return None

def get_cat_image_url():
    try:
        url = "https://api.thecatapi.com/v1/images/search"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data and len(data) > 0:
            return data[0]['url']
    except Exception as e:
         logging.error(f"Cat API Error: {e}")
    return None

# --- SEARCH FUNCTIONS ---

def search_movies_hdhub(query):
    """Searches Hdhub4u."""
    print(f"Searching Hdhub4u for '{query}'...")
    search_url = "https://search.pingora.fyi/collections/post/documents/search"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://hdhub4u.rehab/"
    }
    params = {
        "q": query,
        "query_by": "post_title",
        "sort_by": "sort_by_date:desc",
        "limit": "15",
        "highlight_fields": "none",
        "use_cache": "true",
        "page": "1"
    }
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('hits', [])
    except Exception as e:
        logging.error(f"Hdhub Search Error: {e}")
        return []

def search_skymovieshd(query):
    """Searches SkyMoviesHD."""
    print(f"Searching SkyMoviesHD for '{query}'...")
    base_url = "https://skymovieshd.mba"
    search_url = f"{base_url}/search.php?search={urllib.parse.quote(query)}&cat=All"
    headers = {"User-Agent": USER_AGENT}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = get_soup(response.content)
        results = []

        for div in soup.find_all('div', class_='L'):
            a_tag = div.find('a')
            if a_tag and a_tag.get('href', '').startswith('/movie/'):
                title = a_tag.get_text(strip=True)
                link = a_tag['href']
                if not link.startswith('http'):
                    link = base_url + link
                results.append((title, link))
        return results
    except Exception as e:
        logging.error(f"SkyMoviesHD Search Error: {e}")
        return []

def search_cinevood(query):
    """Searches Cinevood (1cinevood.fyi)."""
    print(f"Searching Cinevood for '{query}'...")
    base_url = "https://1cinevood.fyi"
    search_url = f"{base_url}/?s={urllib.parse.quote(query)}"
    scraper = cloudscraper.create_scraper()
    
    try:
        response = scraper.get(search_url, timeout=10)
        response.raise_for_status()
        soup = get_soup(response.content)
        results = []
        
        articles = soup.find_all('article')
        for article in articles:
            link_tag = article.find('a', href=True)
            if link_tag:
                title = link_tag.get('title') or link_tag.get_text().strip()
                url = link_tag['href']
                if title and url:
                    results.append((title, url))
        return results
    except Exception as e:
        logging.error(f"Cinevood Search Error: {e}")
        return []

# --- BYPASSERS ---

# --- GPLINKS SCRAPER CLASS (Cloudscraper version) ---
class GPLinksScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'windows','mobile': False})
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://gplinks.co/',
        })

    def decode_base64(self, s):
        try:
            return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8')
        except:
            return None

    def scrape(self, url):
        logging.info(f"GPLinks Scraper: Processing {url}")

        attempt = 0
        max_attempts = 10

        while attempt < max_attempts:
            attempt += 1
            logging.info(f"--- Attempt {attempt} ---")

            try:
                self.scraper.cookies.clear()

                resp = self.scraper.get(url, allow_redirects=True)
                landing_url = resp.url

                if "get2.in" in landing_url:
                    query = urlparse(landing_url).query
                    if query:
                        landing_url = unquote(query)
                        resp = self.scraper.get(landing_url, allow_redirects=True)
                        landing_url = resp.url

                logging.info(f"Landing URL: {landing_url}")

                parsed = urlparse(landing_url)
                qs = parse_qs(parsed.query)

                lid = qs.get('lid', [None])[0]
                pid = qs.get('pid', [None])[0]
                vid = qs.get('vid', [None])[0]
                pages_b64 = qs.get('pages', [None])[0]

                if not (lid and pid and vid):
                    logging.info("Could not extract parameters from URL.")
                    return None

                decoded_lid = self.decode_base64(lid)
                decoded_pid = self.decode_base64(pid)
                decoded_pages = self.decode_base64(pages_b64)

                try:
                    pages_num = int(decoded_pages)
                except:
                    pages_num = 3

                logging.info(f"LID: {decoded_lid}, PID: {decoded_pid}, VID: {vid}, Pages: {pages_num}")

                domain = parsed.netloc
                final_target = f"https://gplinks.co/{decoded_lid}/?pid={decoded_pid}&vid={vid}"

                if not self.scraper.cookies.get('lid'):
                    self.scraper.cookies.set('lid', decoded_lid, domain=domain)
                if not self.scraper.cookies.get('pid'):
                    self.scraper.cookies.set('pid', decoded_pid, domain=domain)
                if not self.scraper.cookies.get('vid'):
                    self.scraper.cookies.set('vid', vid, domain=domain)
                if not self.scraper.cookies.get('pages'):
                    self.scraper.cookies.set('pages', str(pages_num), domain=domain)

                self.scraper.cookies.set('step_count', '0', domain=domain)

                current_url = landing_url
                time.sleep(2)

                for step in range(pages_num + 1):
                    self.scraper.cookies.set('step_count', str(step), domain=domain)
                    logging.info(f"Processing Step {step}/{pages_num}")

                    post_url = landing_url

                    if step >= pages_num:
                        next_target = final_target
                    else:
                        next_target = landing_url

                    sleep_time = 18 + (attempt * 3)
                    logging.info(f"  Waiting {sleep_time}s...")
                    time.sleep(sleep_time)

                    data = {
                        'visitor_id': vid,
                        'next_target': next_target,
                        'ad_impressions': str(step * 5),
                        'step_id': '',
                        'form_name': 'ads-track-data'
                    }

                    headers = {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Referer': landing_url,
                        'Origin': f"{parsed.scheme}://{parsed.netloc}",
                        'User-Agent': self.scraper.headers['User-Agent'],
                        'X-Requested-With': 'XMLHttpRequest'
                    }

                    logging.info(f"  Posting to {post_url}")
                    resp = self.scraper.post(post_url, data=data, headers=headers, allow_redirects=True)
                    current_url = resp.url

                    if "gplinks.co" in current_url or "gplinks.com" in current_url:
                        if "error" in current_url:
                             logging.info(f"  Got error: {current_url}")
                             if "not_enough_time" in current_url:
                                 break
                             return current_url

                        try:
                            soup2 = BeautifulSoup(resp.content, 'lxml')
                        except:
                            soup2 = BeautifulSoup(resp.content, 'html.parser')
                            
                        meta = soup2.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
                        if meta:
                            content = meta.get("content", "")
                            if "url=" in content.lower():
                                 current_url = content.split("url=")[-1].strip()
                                 logging.info(f"  Final Meta Refresh to: {current_url}")
                                 resp = self.scraper.get(current_url, allow_redirects=True)
                                 current_url = resp.url

                        if "gplinks.co" in current_url:
                            logging.info("  Reached gplinks.co final page. Looking for link...")
                            time.sleep(5)

                            try:
                                soup3 = BeautifulSoup(resp.content, 'lxml')
                            except:
                                soup3 = BeautifulSoup(resp.content, 'html.parser')

                            links = soup3.find_all('a', href=True)
                            final_link = None
                            for a in links:
                                txt = a.get_text().strip().lower()
                                if any(x in txt for x in ["get link", "open link", "go to link", "submit"]):
                                    final_link = a['href']
                                    logging.info(f"  Found final link anchor: {final_link}")
                                    break

                            if not final_link:
                                for a in links:
                                    href = a['href']
                                    if "gplinks.co" not in href and "facebook" not in href and "javascript" not in href and "#" not in href:
                                         final_link = href
                                         logging.info(f"  Found candidate link: {final_link}")
                                         break

                            if final_link:
                                logging.info(f"  Visiting final link: {final_link}")
                                time.sleep(3)
                                resp = self.scraper.get(final_link, allow_redirects=True)
                                logging.info(f"  Final Destination Reached: {resp.url}")
                                return resp.url

                            logging.info("  Could not find final link on the page.")
                            return current_url

                        return current_url

            except Exception as e:
                logging.error(f"Error scraping gplinks: {e}")

        return None
# --- END GPLINKS SCRAPER CLASS ---

def decode_gadgetsweb_payload(o_val):
    try:
        d1 = base64.b64decode(o_val).decode('utf-8')
        d2 = base64.b64decode(d1).decode('utf-8')
        d3 = rot13(d2)
        d4 = base64.b64decode(d3).decode('utf-8')
        data = json.loads(d4)
        return data
    except Exception as e:
        logging.error(f"GadgetsWeb Decode Error: {e}")
        return None

def bypass_gadgetsweb(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        match = re.search(r"s\('o','([^']+)'", response.text)
        if not match:
            if "hblinks.dad" in response.url:
                return response.url
            return None

        o_val = match.group(1)
        data = decode_gadgetsweb_payload(o_val)
        
        if data and 'o' in data:
            final_url_b64 = data['o']
            final_url = base64.b64decode(final_url_b64).decode('utf-8')
            return final_url
        return None
    except Exception as e:
        logging.error(f"GadgetsWeb Bypass Error: {e}")
        return None

def bypass_hubcdn_link(url):
    print(f"Bypassing HubCDN: {url}")
    headers = {"User-Agent": USER_AGENT, "Referer": "https://hubcdn.fans/"}
    try:
        session = requests.Session()
        session.headers.update(headers)

        response = session.get(url, allow_redirects=True, timeout=15)
        response.raise_for_status()

        if "r2.dev" in response.url or response.headers.get('Content-Type') == 'application/octet-stream':
            return response.url

        final_url = None
        match = re.search(r'var\s+reurl\s*=\s*["\']([^"\']+)["\']', response.text)
        
        if match:
            redirect_url = match.group(1)
            parsed = urlparse(redirect_url)
            qs = parse_qs(parsed.query)
            if 'r' in qs:
                try:
                    final_url = base64.b64decode(qs['r'][0]).decode('utf-8')
                except:
                    pass
            if not final_url and redirect_url.startswith("http"):
                final_url = redirect_url

        if not final_url:
            soup = get_soup(response.content)
            meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
            if meta:
                content = meta.get("content", "")
                if "url=" in content.lower():
                    final_url = content.split("url=")[-1].strip()

        if not final_url:
            if '/dl/' in response.url:
                 final_url = response.url
            else:
                 return None

        session.headers.update({"Referer": url})
        if final_url != response.url:
            response = session.get(final_url, timeout=15)
            response.raise_for_status()

        soup = get_soup(response.content)
        a_tag = soup.find('a', id='vd')

        if a_tag and a_tag.get('href'):
            return a_tag['href']
            
        for btn in soup.find_all('a', class_=re.compile(r'btn-success|btn-primary')):
            if "download" in btn.get_text().lower():
                return btn['href']

        return None

    except Exception as e:
        logging.error(f"HubCDN Error: {e}")
        return None

def bypass_gofile(url):
    print(f"Bypassing GoFile: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        content_id = url.split('/')[-1]
        
        account_resp = requests.post("https://api.gofile.io/accounts", headers=headers, timeout=10)
        if account_resp.status_code != 200: return None
        account_data = account_resp.json()
        if account_data['status'] != 'ok': return None
        token = account_data['data']['token']

        content_url = f"https://api.gofile.io/contents/{content_id}?wt={token}"
        content_resp = requests.get(content_url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}, timeout=10)

        if content_resp.status_code == 200:
            content_data = content_resp.json()
            if content_data['status'] == 'ok':
                items = content_data['data']['children']
                results = []
                for item_id, item in items.items():
                    link = item.get('link')
                    name = item.get('name')
                    if link:
                        results.append({'text': name, 'link': link})
                return results
        return None
    except Exception as e:
        logging.error(f"GoFile Error: {e}")
        return None

def bypass_hubcloud(url):
    print(f"Bypassing HubCloud: {url}")
    headers = {"User-Agent": USER_AGENT}
    session = requests.Session()
    session.headers.update(headers)
    links = []

    try:
        response = session.get(url, allow_redirects=True, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        next_url = None
        generate_btn = soup.find('a', string=re.compile(r"Generate Direct Download Link", re.I))
        if generate_btn and generate_btn.get('href'):
            next_url = generate_btn['href']

        if not next_url:
            for a in soup.find_all('a', href=True):
                if "gamerxyt.com" in a['href']:
                    next_url = a['href']
                    break
        
        if next_url:
            response = session.get(next_url, allow_redirects=True, timeout=15)
            response.raise_for_status()
            soup = get_soup(response.content)
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text().strip()
            
            if any(x in href for x in ['pixeldrain', 'drive.google.com', 'mega.nz', '1fichier', 'gofile.io']):
                links.append({'text': text or "Download", 'link': href})
            elif any(q in text.lower() for q in ['480p', '720p', '1080p', 'mkv', 'zip', 'episode']):
                if href.startswith('http'):
                    links.append({'text': text, 'link': href})
            elif "download [" in text.lower() and "]" in text:
                if href.startswith('http'):
                    links.append({'text': text, 'link': href})
                    
        return links

    except Exception as e:
        logging.error(f"HubCloud Error: {e}")
        return []

def bypass_hubdrive(url):
    print(f"Bypassing Hubdrive: {url}")
    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": url,
        "Origin": "https://hubdrive.space"
    }
    session = requests.Session()
    session.headers.update(headers)

    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        for a in soup.find_all('a', href=True):
            if "HubCloud Server" in a.get_text() or "hubcloud" in a['href']:
                if "drive" in a['href']:
                    return bypass_hubcloud(a['href'])

        down_id_div = soup.find('div', id='down-id')
        if not down_id_div:
            return None
        
        file_id = down_id_div.get_text().strip()
        ajax_url = "https://hubdrive.space/ajax.php?ajax=direct-download"
        data = {'id': file_id}

        session.headers.update({"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})

        response = session.post(ajax_url, data=data, timeout=10)
        try:
            json_response = response.json()
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response from HubDrive.")
            return None
        
        if json_response.get('code') == "200":
            download_data = json_response.get('data')
            if isinstance(download_data, dict):
                gd_link = download_data.get('gd')
                return gd_link
            else:
                logging.error(f"Unexpected data format from HubDrive: {json_response}")
        else:
            logging.error(f"HubDrive API Error: {json_response.get('code')} - {json_response.get('file')}")
        
        return None

    except Exception as e:
        logging.error(f"HubDrive Error: {e}")
        return None

def bypass_howblogs(url):
    print(f"Bypassing HowBlogs: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        # 'cotent-box' is a typo in the website's HTML, do not correct it.
        content_box = soup.find('div', class_='cotent-box')
        if content_box:
            for a in content_box.find_all('a', href=True):
                href = a['href'].strip()
                text = a.get_text().strip()
                if href:
                    links.append({'text': text or "Download", 'link': href})
        return links
    except Exception as e:
        logging.error(f"HowBlogs Error: {e}")
        return []


# --- SCRAPERS ---

def scrape_hblinks(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)
        
        links = []
        known_domains = ["hubcloud", "hubdrive", "gofile", "katfile", "drivehub", "gdflix", "hubcdn"]

        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(domain in href for domain in known_domains):
                link_text = a.get_text().strip()
                if not link_text:
                    img = a.find('img')
                    if img and img.get('src'):
                        if "Cloud-Logo" in img['src']: link_text = "HubCloud"
                        elif "Hubdrive" in img['src']: link_text = "HubDrive"
                        elif "gofile" in img['src']: link_text = "GoFile"
                        else: link_text = "Download"
                
                links.append({'text': link_text or "Download", 'link': href})
        
        return links
    except Exception as e:
        logging.error(f"Hblinks Scrape Error: {e}")
        return []

def scrape_hdhub4u_page(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)
        
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text().strip()
            href = a_tag['href']

            if any(q in text.lower() for q in ['480p', '720p', '1080p', 'hevc', 'episode']):
                parent = a_tag.parent
                valid_parents = ['h2', 'h3', 'h4', 'p', 'strong', 'em']
                
                if parent.name in valid_parents:
                    links.append({'text': text, 'link': href})
                elif parent.name == 'span' and parent.parent and parent.parent.name in valid_parents:
                    links.append({'text': text, 'link': href})

        return links
    except Exception as e:
        logging.error(f"Hdhub4u Scrape Error: {e}")
        return []

def scrape_skymovieshd(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        bolly_div = soup.find('div', class_='Bolly')
        if bolly_div:
            for a in bolly_div.find_all('a', href=True):
                href = a['href'].strip()
                text = a.get_text().strip()
                if href and not href.startswith('#') and not href.startswith('javascript'):
                    links.append({'text': text or "Link", 'link': href})
        return links
    except Exception as e:
        logging.error(f"SkyMoviesHD Scrape Error: {e}")
        return []

def scrape_4khdhub(url):
    print(f"Scraping 4khdhub: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        
        for item in soup.find_all('div', class_='download-item'):
            header = item.find('div', class_='download-header')
            if not header:
                continue
            
            header_text_div = header.find('div', class_='flex-1')
            if not header_text_div:
                continue
            
            quality_text = header_text_div.get_text(" ", strip=True)

            file_id = header.get('data-file-id')
            if not file_id:
                continue
                
            content_div = item.find('div', id=f"content-{file_id}")
            if not content_div:
                continue
                
            for a in content_div.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                
                link_label = f"{quality_text} - {text}"
                
                links.append({'text': link_label, 'link': href})

        return links
    except Exception as e:
        logging.error(f"4KHDHub Scrape Error: {e}")
        return []

def scrape_filmyfiy(url):
    logging.info(f"Scraping Filmyfiy URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        download_link = None

        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            if "Download 480p 720p 1080p" in text:
                download_link = a['href']
                break
        
        if not download_link:
            for a in soup.find_all('a', href=True):
                if "linkmake.in" in a['href']:
                    download_link = a['href']
                    break
        
        if not download_link:
            logging.error("Could not find the intermediate download link (linkmake.in) on the page.")
            return []
        
        logging.info(f"Found intermediate link: {download_link}")

        response = requests.get(download_link, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            href = a['href']

            if "Download" in text and ("480p" in text or "720p" in text or "1080p" in text):
                links.append({'text': text, 'link': href})
        
        return links
    except Exception as e:
        logging.error(f"Filmyfiy Scrape Error: {e}")
        return []

def scrape_vegamovies(url):
    logging.info(f"Scraping Vegamovies URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code in [403, 503]:
             logging.error(f"Vegamovies access denied (Status: {response.status_code}). Site might be protected by Cloudflare.")
             return []

        response.raise_for_status()
        soup = get_soup(response.content)
        
        links = []
        
        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            href = a['href']
            text_lower = text.lower()
            
            if any(q in text_lower for q in ['480p', '720p', '1080p']):
                links.append({'text': text, 'link': href})
            elif "download" in text_lower and ("link" in text_lower or "server" in text_lower):
                 links.append({'text': text, 'link': href})
            elif "g-direct" in text_lower or "v-cloud" in text_lower:
                 links.append({'text': text, 'link': href})

        return links
    except Exception as e:
        logging.error(f"Vegamovies Scrape Error: {e}")
        return []

def scrape_katmoviehd(url):
    logging.info(f"Scraping KatMovieHD URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        
        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            href = a['href']

            if not href or href.startswith('#') or href == '/':
                continue
            
            if '/tag/' in href or '/category/' in href:
                continue
            
            if href.rstrip('/') == url.rstrip('/'):
                continue

            if re.search(r'(480p|720p|1080p|2160p|4k)', text, re.IGNORECASE):
                if "links" in text.lower() or "download" in text.lower():
                    links.append({'text': text, 'link': href})
                elif "links.kmhd.net" in href:
                    links.append({'text': text, 'link': href})

        return links
    except Exception as e:
        logging.error(f"KatMovieHD Scrape Error: {e}")
        return []

def scrape_mymp4movies(url):
    logging.info(f"Scraping Mymp4Movies URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url)
        except ImportError:
            response = requests.get(url, headers=headers, timeout=15)

        if response.status_code in [403, 503]:
             logging.error(f"Access denied (Status: {response.status_code}). Site might be protected by Cloudflare.")
             return []

        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            href = a['href']
            
            if not href or href.startswith('#') or href.startswith('javascript'):
                continue

            text_lower = text.lower()
            if any(q in text_lower for q in ['480p', '720p', '1080p', 'download']):
                links.append({'text': text, 'link': href})
        
        return links
    except Exception as e:
        logging.error(f"Mymp4Movies Scrape Error: {e}")
        return []

def scrape_kmhd_links(url):
    logging.info(f"Scraping KMHD Links URL: {url}")
    scraper = cloudscraper.create_scraper()

    try:
        response = scraper.get(url)
    except Exception as e:
        logging.error(f"Error fetching URL: {e}")
        return []

    final_html = response.text
    base_url = response.url

    if "locked" in base_url:
        logging.info("Page is locked. Attempting to unlock...")
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        if form:
            action = form.get('action')
            post_url = urllib.parse.urljoin(base_url, action)

            headers = {
                'Referer': base_url,
                'Origin': 'https://links.kmhd.net',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {}
            for input_tag in form.find_all('input'):
                name = input_tag.get('name')
                value = input_tag.get('value', '')
                if name:
                    data[name] = value

            post_response = scraper.post(post_url, data=data, headers=headers)

            if post_response.status_code == 200:
                logging.info("Unlock POST successful.")
                final_html = post_response.text
            else:
                logging.error(f"Unlock failed with status {post_response.status_code}")
                return []
        else:
            logging.error("Locked page but no form found.")
            return []

    links = []

    upload_links_match = re.search(r'upload_links\s*:\s*{([^}]+)}', final_html)

    if upload_links_match:
        upload_links_str = upload_links_match.group(1)
        res_ids = re.findall(r'([a-zA-Z0-9_]+)\s*:\s*"([^"]+)"', upload_links_str)

        for key, value in res_ids:
            if value == "None" or value == "null":
                continue

            link_config_pattern = re.compile(rf'{key}\s*:\s*{{[^}}]*link\s*:\s*"([^"]+)"')
            link_config_match = link_config_pattern.search(final_html)

            if link_config_match:
                base_link = link_config_match.group(1)
                full_link = base_link + value
                
                text_label = key.replace('_res', '').capitalize()
                links.append({'text': text_label, 'link': full_link})
            else:
                pass

    return links

def scrape_pixel_hubcdn(url):
    """
    Scrapes download links from pixel.hubcdn.fans URLs.
    """
    logging.info(f"Scraping Pixel HubCDN URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        try:
            soup = BeautifulSoup(response.content, 'lxml')
        except Exception:
            soup = BeautifulSoup(response.content, 'html.parser')

        links = []

        vd_link = soup.find('a', id='vd')
        if vd_link and vd_link.get('href'):
            href = vd_link['href']
            links.append({'text': "Download Here", 'link': href})

        for btn in soup.find_all('a', class_=lambda c: c and ('btn-success' in c or 'btn-primary' in c or 'btn-brand' in c)):
            text = btn.get_text(strip=True)
            href = btn.get('href')

            if href and "download" in text.lower():
                if not any(l['link'] == href for l in links):
                     links.append({'text': text, 'link': href})

        logging.info(f"Found {len(links)} links on Pixel HubCDN page.")
        return links

    except Exception as e:
        logging.error(f"Pixel HubCDN Scrape Error: {e}")
        return []

def scrape_pikahd(url):
    logging.info(f"Scraping Pikahd URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        unique_hrefs = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)

            if not href or href.startswith('#') or href.startswith('javascript'):
                continue

            is_valid = False
            # Check domains
            if any(x in href for x in ["links.kmhd.net", "hubcloud", "drive.google", "mega.nz"]):
                is_valid = True
            # Check text
            elif "Download" in text or "Links" in text:
                if href.startswith("http") and not any(x in href for x in ["category", "wp-json", "feed"]):
                    is_valid = True

            if is_valid and href not in unique_hrefs:
                links.append({'text': text or "Download Link", 'link': href})
                unique_hrefs.add(href)

        return links
    except Exception as e:
        logging.error(f"Pikahd Scrape Error: {e}")
        return []

def scrape_katdrama(url):
    logging.info(f"Scraping KatDrama URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = get_soup(response.content)

        links = []

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if "links.kmhd.net" in href and "/file/" in href:
                link_text = a_tag.get_text(strip=True) or "Download Link"
                links.append({
                    'text': link_text,
                    'link': href
                })
        
        return links
    except Exception as e:
        logging.error(f"KatDrama Scrape Error: {e}")
        return []

def scrape_toonworld4all(url):
    """Scrapes download links from a toonworld4all.me URL."""
    logging.info(f"Scraping Toonworld4all URL: {url}")
    scraper = cloudscraper.create_scraper()

    try:
        response = scraper.get(url)
        response.raise_for_status()
        soup = get_soup(response.text)
        download_links = []
        all_links = soup.find_all("a", href=True)

        for link in all_links:
            href = link['href']
            text = link.get_text(strip=True)
            keywords = ["Download", "Watch Online", "G-Direct", "Mega", "Drive", "File", "Link"]
            if any(k.lower() in text.lower() for k in keywords):
                quality_header = "Link"
                header = link.find_previous(["h3", "h4", "h5", "h2", "strong", "b"])
                if header:
                    quality_header = header.get_text(strip=True)

                if not href.startswith("#") and "javascript" not in href.lower():
                    if not any(d['link'] == href for d in download_links):
                        display_text = f"[{quality_header}] {text}"
                        download_links.append({"text": display_text, "link": href})
        return download_links
    except Exception as e:
        logging.error(f"Error scraping toonworld4all: {e}")
        return []

def scrape_moviesmod(url):
    """Scrapes download links from a moviesmod.kids URL."""
    logging.info(f"Scraping MoviesMod URL: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = get_soup(response.text)
        download_links = []
        for link in soup.find_all("a", href=True):
            href = link['href']
            text = link.get_text(strip=True)
            if "links.modpro.blog" in href:
                quality_header = "Unknown Quality"
                header = link.find_previous(["h3", "h4", "h5", "h2"])
                if header:
                    quality_header = header.get_text(strip=True)
                download_links.append({"text": f"{quality_header} - {text}", "link": href})
        return download_links
    except Exception as e:
        logging.error(f"Error scraping MoviesMod: {e}")
        return []

def scrape_animeflix(url):
    """Scrapes AnimeFlix Links."""
    scraper = cloudscraper.create_scraper()
    try:
        logging.info(f"Fetching AnimeFlix URL: {url}")
        response = scraper.get(url)
        response.raise_for_status()
        soup = get_soup(response.text)
        links = []
        
        # Helper for driveseed
        def process_driveseed(ds_resp):
            ds_soup = get_soup(ds_resp.text)
            ds_links = []
            file_id = None
            for script in ds_soup.find_all('script'):
                if script.string:
                    match = re.search(r'window\.location\.replace\("(/file/[^"]+)"\)', script.string)
                    if match:
                        file_path = match.group(1)
                        file_url = 'https://driveseed.org' + file_path
                        try:
                            ds_resp = scraper.get(file_url)
                            ds_soup = get_soup(ds_resp.text)
                            file_id = file_path.split('/')[-1]
                        except: pass
                        break
            if not file_id and '/file/' in ds_resp.url:
                 file_id = ds_resp.url.split('/')[-1]
            if not file_id: return []
            
            instant_dl = ds_soup.find('a', string=re.compile('Instant Download'))
            if instant_dl: ds_links.append(instant_dl['href'])
            
            wfile_url = f"https://driveseed.org/wfile/{file_id}"
            for type_val in [1, 2]:
                try:
                    wfile_resp = scraper.get(f"{wfile_url}?type={type_val}")
                    wsoup = get_soup(wfile_resp.text)
                    for dl in wsoup.find_all('a', string=re.compile('Download')):
                        if dl.get('href') and 'workers.dev' in dl.get('href'):
                            ds_links.append(dl.get('href'))
                except: pass
            return ds_links

        for link in soup.find_all('a', string=re.compile(r'Gdrive \+ Mirrors')):
            archive_url = link.get('href')
            if not archive_url: continue
            quality_text = "Unknown"
            prev = link.previous_sibling
            if prev and isinstance(prev, str): quality_text = prev.strip()
            elif link.find_previous('p'): quality_text = link.find_previous('p').get_text(strip=True)
            if len(quality_text) > 50: quality_text = "Download"

            try:
                arch_resp = scraper.get(archive_url)
                arch_soup = get_soup(arch_resp.text)
                for gl in arch_soup.find_all('a', href=re.compile(r'/getlink/')):
                    gl_url = gl.get('href')
                    gl_text = gl.get_text(strip=True) or "Episode"
                    if gl_url.startswith('/'): gl_url = 'https://episodes.animeflix.pm' + gl_url
                    ds_resp = scraper.get(gl_url, allow_redirects=True)
                    if 'driveseed.org' in ds_resp.url:
                        final_links = process_driveseed(ds_resp)
                        for fl in final_links:
                            links.append({'text': f"{quality_text} - {gl_text}", 'link': fl})
            except Exception as e: logging.error(f"AnimeFlix Archive Error: {e}")
        return links
    except Exception as e:
        logging.error(f"Error scraping animeflix: {e}")
        return []

def scrape_uhdmovies(url):
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url)
        response.raise_for_status()
        soup = get_soup(response.content)
        content_div = soup.find('div', class_='entry-content')
        if not content_div: return []
        links = []
        for button in content_div.find_all('a', class_=lambda c: c and 'maxbutton' in c):
            link = button.get('href')
            if not link: continue
            title = "Unknown Quality"
            container = button.find_parent('p') or button.find_parent('div')
            if container:
                for sibling in container.find_previous_siblings():
                    if sibling.name == 'p' and (sibling.find('strong') or sibling.find('b')):
                        text = sibling.get_text(" ", strip=True)
                        if text and len(text) > 5:
                            title = text
                            break
                    elif sibling.name in ['h2', 'h3']:
                        title = sibling.get_text(" ", strip=True)
                        break
            links.append({'text': title, 'link': link})
        return links
    except Exception as e:
        logging.error(f"UHDMovies Error: {e}")
        return []

def scrape_cinevood(url):
    logging.info(f"Scraping Cinevood URL: {url}")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        response = scraper.get(url, timeout=15)
        if response.status_code in [403, 503]:
            logging.error(f"Access denied (Status: {response.status_code}). Site might be protected by Cloudflare.")
            return []
        
        response.raise_for_status()
        soup = get_soup(response.content)
        links = []
        
        content_div = soup.find('div', class_='post-single-content')
        if content_div:
            elements = content_div.find_all(['h5', 'h6', 'p'])
            current_quality = "Unknown Quality"
            for elem in elements:
                if elem.name in ['h5', 'h6']:
                    text = elem.get_text().strip()
                    if text: current_quality = text
                elif elem.name == 'p':
                    found_links = elem.find_all('a', href=True)
                    for link in found_links:
                        href = link['href']
                        text = link.get_text().strip()
                        if any(x in href for x in ['facebook.com', 'twitter.com', 'whatsapp://', 'telegram.me/share']): continue
                        if not text: text = link.get('title', '').strip() or "Download Link"
                        
                        display_text = f"[{current_quality}] {text}"
                        links.append({'text': display_text, 'link': href})
        return links
    except Exception as e:
        logging.error(f"Error scraping Cinevood: {e}")
        return []

def scrape_extraflix(url):
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url)
        response.raise_for_status()
        soup = get_soup(response.content)
        results = []
        for a in soup.find_all('a', href=lambda href: href and 'extralink.ink' in href):
            link = a['href']
            quality = "Unknown Quality"
            try:
                parent = a.find_parent()
                if parent:
                    prev = parent.find_previous_sibling()
                    if prev: quality = prev.get_text(strip=True)
            except: pass
            results.append({'text': quality, 'link': link})
        return results
    except Exception as e:
        logging.error(f"ExtraFlix Error: {e}")
        return []

def scrape_extralink(url):
    match = re.search(r'/s/([a-zA-Z0-9]+)', url)
    if not match: return []
    token = match.group(1)
    parsed_url = urlparse(url)
    api_url = f"{parsed_url.scheme}://{parsed_url.netloc}/api/s/{token}/"
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        links = []
        for key, name in [('filepressLink', 'FilePress'), ('streamhgLink', 'StreamHG'), ('vidhideLink', 'VidHide'), 
                          ('r2Link', 'R2 Direct'), ('vikingLink', 'VikingFile'), ('photoLink', 'Photo'), 
                          ('gdtotLink', 'GDTOT'), ('hubcloudLink', 'HubCloud'), ('pixeldrainLink', 'PixelDrain'), 
                          ('gofileLink', 'GoFile')]:
            if data.get(key): links.append({'text': name, 'link': data[key]})
        return links
    except Exception as e:
        logging.error(f"ExtraLink Error: {e}")
        return []

def scrape_filepress(url):
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url)
        response.raise_for_status()
        soup = get_soup(response.content)
        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            if not href.startswith(('http', 'https')): href = urljoin(url, href)
            if href == url or href.startswith('javascript'): continue
            if any(kw in text.lower() for kw in ['download', '480p', '720p', '1080p', 'get link']) or \
               any(host in href for host in ['drive.google', 'mega.nz', 'gofile.io', 'pixeldrain']):
                 links.append({'text': text, 'link': href})
        if not links:
            for btn in soup.find_all(class_=re.compile(r'btn|button|download', re.I)):
                if btn.name == 'a' and btn.get('href'):
                    href = btn['href']
                    if not href.startswith(('http', 'https')): href = urljoin(url, href)
                    links.append({'text': btn.get_text(strip=True) or "Download", 'link': href})
        return links
    except Exception as e:
        logging.error(f"FilePress Error: {e}")
        return []

def scrape_hdwebmovies(url):
    """Scrapes download links from HDWebMovies."""
    logging.info(f"Scraping HDWebMovies URL: {url}")
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url)
        response.raise_for_status()
        soup = get_soup(response.text)
        links_found = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            if "/tag/" in href or "/category/" in href or href.strip() == "#": continue
            if "download" in text.lower() and re.search(r'\d{3,4}p', text, re.IGNORECASE):
                links_found.append({"text": text, "link": href})
            elif "download now" in text.lower():
                 links_found.append({"text": text, "link": href})
            elif any(x in href for x in ['magnet:', 'drive.google.com', 'mega.nz', 'pixeldra', 'tmbcloud.pro', 'hwmlinks']):
                if not any(l['link'] == href for l in links_found):
                    links_found.append({"text": text or "Link", "link": href})
        return links_found
    except Exception as e:
        logging.error(f"HDWebMovies Error: {e}")
        return []

def scrape_oxxfile(url):
    logging.info(f"Scraping OxxFile URL: {url}")
    links = []

    # Requires playwright installed in the environment
    try:
        with sync_playwright() as p:
            # Use stealth arguments to avoid detection
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certifcate-errors",
                    "--ignore-certifcate-errors-spki-list",
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )

            # Mask webdriver property
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page = context.new_page()
            page.goto(url)
            page.wait_for_timeout(5000)

            # --- GDToT ---
            gdtot_btn = page.locator("button:has-text('Generate GDToT Link')")
            if gdtot_btn.count() > 0:
                max_retries = 3
                for i in range(max_retries):
                    if "fetch failed" in page.content():
                        logging.warning("GDToT fetch failed detected. Reloading page...")
                        page.reload()
                        page.wait_for_timeout(5000)
                        gdtot_btn = page.locator("button:has-text('Generate GDToT Link')")

                    if gdtot_btn.count() == 0: break
                    logging.info(f"Clicking GDToT button (Attempt {i+1})...")

                    try:
                        with context.expect_page(timeout=10000) as new_page_info:
                            try:
                                gdtot_btn.click()
                            except Exception as e:
                                logging.warning(f"Click failed: {e}")

                        new_page = new_page_info.value
                        new_page.wait_for_load_state()
                        url_found = new_page.url
                        logging.info(f"Opened: {url_found}")

                        if "alibaba" in url_found or "google" in url_found:
                            logging.info("Ad detected. Closing and retrying...")
                            new_page.close()
                            page.wait_for_timeout(2000)
                            continue

                        if url_found and url_found != "about:blank":
                            links.append({'text': "GDToT", 'link': url_found})
                            new_page.close()
                            break
                        new_page.close()
                    except Exception as e:
                        logging.warning(f"No new page opened or timeout in attempt {i+1}: {e}")
                        page.wait_for_timeout(2000)
                        continue

            # --- FilePress ---
            filepress_btn = page.locator("button:has-text('Filepress Download')")
            if filepress_btn.count() > 0:
                max_retries = 3
                for i in range(max_retries):
                    logging.info(f"Clicking FilePress button (Attempt {i+1})...")
                    try:
                        with context.expect_page(timeout=10000) as new_page_info:
                            try:
                                filepress_btn.click()
                            except Exception as e:
                                logging.warning(f"Click failed: {e}")

                        new_page = new_page_info.value
                        new_page.wait_for_load_state()
                        url_found = new_page.url
                        logging.info(f"Opened: {url_found}")

                        if "alibaba" in url_found or "google" in url_found:
                             logging.info("Ad detected. Closing and retrying...")
                             new_page.close()
                             page.wait_for_timeout(2000)
                             continue

                        if url_found and url_found != "about:blank":
                            links.append({'text': "FilePress", 'link': url_found})
                            new_page.close()
                            break
                        new_page.close()
                    except Exception as e:
                        logging.warning(f"No new page opened or timeout in attempt {i+1}: {e}")
                        page.wait_for_timeout(2000)
                        continue
            browser.close()
    except Exception as e:
        logging.error(f"OxxFile Scrape Error: {e}")

    return links

# --- MAIN CONTROLLER ---

def get_download_links(url):
    print(f"Processing: {url}")
    message = ""

    if "gadgetsweb.xyz" in url:
        message += "🔄 <b>Detected GadgetsWeb. Bypassing...</b>\n"
        bypassed_url = bypass_gadgetsweb(url)
        if bypassed_url:
            message += f"✅ Resolved to: {html.escape(bypassed_url)}\n\n"
            url = bypassed_url 
        else:
            return "❌ Failed to bypass GadgetsWeb link."

    # Direct Bypasses
    
    if is_gplinks_url(url):
        try:
            scraper = GPLinksScraper()
            result = scraper.scrape(url)
            if result:
                 return f"✅ <b>GPLinks Bypassed!</b>\n\n🔗 <a href='{result}'>Click to Download</a>"
            else:
                 return "❌ Failed to bypass GPLinks."
        except Exception as e:
             return f"❌ Error processing GPLinks: {html.escape(str(e))}"

    if is_hubcloud_url(url):
        results = bypass_hubcloud(url)
        if results:
            msg = f"✅ <b>HubCloud Bypassed!</b>\n\n"
            for r in results:
                msg += f"📦 {html.escape(r['text'])}: {r['link']}\n"
            return msg
        return "❌ Failed to bypass HubCloud link."
    
    if is_howblogs_url(url):
        results = bypass_howblogs(url)
        if results:
            msg = f"✅ <b>HowBlogs Extracted!</b>\n\n"
            for r in results:
                msg += f"📦 {html.escape(r['text'])}: {r['link']}\n"
            return msg
        return f"❌ Failed to extract HowBlogs: {url}"

    if is_gofile_url(url):
        results = bypass_gofile(url)
        if results:
            msg = f"✅ <b>GoFile Extracted!</b>\n\n"
            for r in results:
                msg += f"📂 {html.escape(r['text'])}: {r['link']}\n"
            return msg
        return f"❌ Failed to extract GoFile (or manual visit required): {url}"

    if is_hubcdn_url(url):
        link = bypass_hubcdn_link(url)
        if link:
            return f"✅ <b>HubCDN Bypassed!</b>\n\n🔗 <a href='{link}'>Click to Download</a>"
        return "❌ Failed to bypass HubCDN link."

    if is_hubdrive_url(url):
        result = bypass_hubdrive(url)
        if isinstance(result, list):
            msg = f"✅ <b>HubDrive (via HubCloud) Bypassed!</b>\n\n"
            for r in result:
                msg += f"📦 {html.escape(r['text'])}: {r['link']}\n"
            return msg
        elif isinstance(result, str):
             return f"✅ <b>HubDrive Bypassed!</b>\n\n🔗 <a href='{result}'>Click to Download</a>"
        return "❌ Failed to bypass HubDrive link."
    
    if is_vplink_url(url):
        result = bypass_vplink(url)
        return f"✅ <b>VPLink Processed!</b>\n\n🔗 <a href='{result}'>Result Link</a>"
    
    if is_extralink_url(url):
        results = scrape_extralink(url)
        if results:
            msg = f"✅ <b>ExtraLink Expanded!</b>\n\n"
            for r in results:
                msg += f"🔗 {html.escape(r['text'])}: {r['link']}\n"
            return msg
        return "❌ Failed to expand ExtraLink."

    # Scraping
    links = []
    if "hblinks.dad" in url:
        links = scrape_hblinks(url)
    elif is_skymovieshd_url(url):
        links = scrape_skymovieshd(url)
    elif is_4khdhub_url(url):
        links = scrape_4khdhub(url)
    elif is_filmyfiy_url(url):
        links = scrape_filmyfiy(url)
    elif is_vegamovies_url(url):
        links = scrape_vegamovies(url)
    elif is_katmoviehd_url(url):
        links = scrape_katmoviehd(url)
    elif is_mymp4movies_url(url):
        links = scrape_mymp4movies(url)
    elif is_kmhd_link_url(url):
        links = scrape_kmhd_links(url)
    elif is_pixel_hubcdn_url(url):
        links = scrape_pixel_hubcdn(url)
    elif is_pikahd_url(url):
        links = scrape_pikahd(url)
    elif is_katdrama_url(url):
        links = scrape_katdrama(url)
    elif is_toonworld4all_url(url):
        links = scrape_toonworld4all(url)
    elif is_moviesmod_url(url):
        links = scrape_moviesmod(url)
    elif is_animeflix_url(url):
        links = scrape_animeflix(url)
    elif is_uhdmovies_url(url):
        links = scrape_uhdmovies(url)
    elif is_cinevood_url(url):
        links = scrape_cinevood(url)
    elif is_extraflix_url(url):
        links = scrape_extraflix(url)
    elif is_filepress_url(url):
        links = scrape_filepress(url)
    elif is_hdwebmovies_url(url):
        links = scrape_hdwebmovies(url)
    elif is_oxxfile_url(url):
        links = scrape_oxxfile(url)
    else:
        links = scrape_hdhub4u_page(url)

    if not links:
        return message + "⚠️ No download links found on the page."

    message += f"✅ <b>Found {len(links)} links. Processing...</b>\n\n"
    
    for item in links:
        original = item['link']
        quality = item['text']
        bypassed = None
        source_type = "Original"

        safe_quality = html.escape(quality)

        if "gadgetsweb.xyz" in original:
            gw_bypassed = bypass_gadgetsweb(original)
            if gw_bypassed:
                original = gw_bypassed
                source_type = "GadgetsWeb->Direct"
            else:
                source_type = "GadgetsWeb (Failed)"

        if is_hubcloud_url(original):
            hc_results = bypass_hubcloud(original)
            if hc_results:
                message += f"🎬 <b>{safe_quality} (HubCloud Pack)</b>\n"
                for r in hc_results:
                    safe_text = html.escape(r['text'])
                    message += f"  └ 📦 <a href='{r['link']}'>{safe_text}</a>\n"
                message += "\n"
                continue
            else:
                source_type = "HubCloud (Failed)"

        elif is_gofile_url(original):
            gf_results = bypass_gofile(original)
            if gf_results:
                message += f"🎬 <b>{safe_quality} (GoFile Folder)</b>\n"
                for r in gf_results:
                     safe_text = html.escape(r['text'])
                     message += f"  └ 📂 <a href='{r['link']}'>{safe_text}</a>\n"
                message += "\n"
                continue
            else:
                source_type = "GoFile (Manual)"

        elif is_howblogs_url(original):
            hb_results = bypass_howblogs(original)
            if hb_results:
                message += f"🎬 <b>{safe_quality} (HowBlogs Pack)</b>\n"
                for r in hb_results:
                    safe_text = html.escape(r['text'])
                    message += f"  └ 📦 <a href='{r['link']}'>{safe_text}</a>\n"
                message += "\n"
                continue
            else:
                source_type = "HowBlogs (Failed)"

        elif is_hubcdn_url(original):
            bypassed = bypass_hubcdn_link(original)
            source_type = "HubCDN"
        
        elif is_hubdrive_url(original):
            res = bypass_hubdrive(original)
            if isinstance(res, list):
                message += f"🎬 <b>{safe_quality} (HubDrive->Cloud)</b>\n"
                for r in res:
                    safe_text = html.escape(r['text'])
                    message += f"  └ 📦 <a href='{r['link']}'>{safe_text}</a>\n"
                message += "\n"
                continue
            elif isinstance(res, str):
                bypassed = res
                source_type = "HubDrive"
        
        elif is_vplink_url(original):
            bypassed = bypass_vplink(original)
            source_type = "VPLink"
        
        message += f"🎬 <b>{safe_quality}</b>\n"
        if bypassed:
            message += f"🟢 <a href='{bypassed}'>Direct Download ({source_type})</a>\n\n"
        else:
            message += f"⚪ <a href='{original}'>Link ({source_type})</a>\n\n"
    
    return message

# --- ASYNC HELPER FOR SCRAPING ---
async def perform_scrape_and_reply(url, update, context):
    chat_id = update.effective_chat.id
    
    status_msg = await context.bot.send_message(chat_id=chat_id, text="⏳ Bypassing.....\n\nPlease wait, this may take a moment.", parse_mode='HTML')
    
    try:
        loop = asyncio.get_running_loop()
        result_text = await loop.run_in_executor(None, get_download_links, url)

        if len(result_text) > 4096:
            lines = result_text.split('\n')
            chunk = ""
            for line in lines:
                if len(chunk) + len(line) + 1 > 4096:
                    await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode='HTML', disable_web_page_preview=True)
                    chunk = ""
                chunk += line + "\n"
            if chunk:
                await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode='HTML', disable_web_page_preview=True)
            
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {html.escape(str(e))}", parse_mode='HTML')
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
    except:
        pass

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I am Kaustav Ray's Scraper Bot.\n\n"
        "<b>How to use:</b>\n"
        "1. <b>Send a Link:</b> I will scrape and bypass it.\n"
        "2. <b>Send a Movie Name:</b> I will search for it.\n"
        "3. <b>/p Movie Name:</b> I will send the poster."
    )

async def get_poster_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /p <movie name>")
        return

    query = ' '.join(context.args)
    status_msg = await update.message.reply_text(f"🔎 Fetching poster for '{html.escape(query)}'...", parse_mode='HTML')

    try:
        loop = asyncio.get_running_loop()
        poster_url, _ = await loop.run_in_executor(None, get_poster_url, query)
        source = "IMDb"

        if not poster_url:
            poster_url = await loop.run_in_executor(None, get_google_poster_url, query)
            source = "Google"

        if not poster_url:
            poster_url = await loop.run_in_executor(None, get_cat_image_url)
            source = "CatImages"

        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)

        if poster_url:
            caption = f"Poster for: {query}"
            if source == "Google":
                caption += " (from Google)"
            elif source == "CatImages":
                caption = f"Movie not found. Here is a cat from {source} instead!"
            await update.message.reply_photo(photo=poster_url, caption=caption)
        else:
            await update.message.reply_text("❌ Poster not found.")

    except Exception as e:
        await update.message.reply_text(f"Error fetching poster: {html.escape(str(e))}", parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    # 1. URL HANDLING
    if user_text.startswith("http"):
        urls = [u.strip() for u in user_text.split(',')]
        for url in urls:
            if not url: continue
            await perform_scrape_and_reply(url, update, context)
        return

    # 2. SEARCH HANDLING
    status_msg = await update.message.reply_text(f"🔎 Searching for '{html.escape(user_text)}'...", parse_mode='HTML')
    
    user_id = update.effective_user.id
    message_id = update.message.message_id
    
    try:
        loop = asyncio.get_running_loop()
        
        # Run searches in parallel
        hdhub_hits_future = loop.run_in_executor(None, search_movies_hdhub, user_text)
        skymovies_hits_future = loop.run_in_executor(None, search_skymovieshd, user_text)
        cine_hits_future = loop.run_in_executor(None, search_cinevood, user_text)
        
        hdhub_hits = await hdhub_hits_future
        skymovies_hits = await skymovies_hits_future
        cine_hits = await cine_hits_future
        
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)

        if not hdhub_hits and not skymovies_hits and not cine_hits:
            await update.message.reply_text("❌ No results found.")
            return

        keyboard = []

        # Process Hdhub4u hits
        for hit in hdhub_hits:
            title = hit['document']['post_title']
            permalink = hit['document']['permalink']
            full_url = f"https://hdhub4u.rehab{permalink}"
            
            search_id = str(uuid.uuid4())[:8]
            SEARCH_CACHE[search_id] = full_url
            callback_data = f"{search_id}|{user_id}|{message_id}"
            
            display_title = (title[:30] + '..') if len(title) > 30 else title
            keyboard.append([InlineKeyboardButton(f"[Hub] {display_title}", callback_data=callback_data)])

        # Process SkyMoviesHD hits
        for title, link in skymovies_hits:
            search_id = str(uuid.uuid4())[:8]
            SEARCH_CACHE[search_id] = link
            callback_data = f"{search_id}|{user_id}|{message_id}"
            
            display_title = (title[:30] + '..') if len(title) > 30 else title
            keyboard.append([InlineKeyboardButton(f"[Sky] {display_title}", callback_data=callback_data)])

        # Process Cinevood hits
        for title, link in cine_hits:
            search_id = str(uuid.uuid4())[:8]
            SEARCH_CACHE[search_id] = link
            callback_data = f"{search_id}|{user_id}|{message_id}"
            
            display_title = (title[:30] + '..') if len(title) > 30 else title
            keyboard.append([InlineKeyboardButton(f"[Cine] {display_title}", callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        total_hits = len(hdhub_hits) + len(skymovies_hits) + len(cine_hits)
        await update.message.reply_text(f"Found {total_hits} results for '{html.escape(user_text)}':", reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"Error during search: {html.escape(str(e))}", parse_mode='HTML')

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Check if the callback_data contains user verification info
    data_parts = query.data.split('|')
    
    if len(data_parts) == 3:
        search_id, owner_id, owner_message_id = data_parts
        if int(owner_id) != query.from_user.id:
            await query.answer(text="This is not your movie request...", show_alert=True)
            return
    else:
        # Fallback for old buttons or different format
        search_id = query.data

    await query.answer()
    
    url = SEARCH_CACHE.get(search_id)
    
    if not url:
        await query.edit_message_text("❌ Link expired or invalid. Please search again.")
        return
        
    await query.edit_message_text(f"✅ Selected. Processing...")
    
    await perform_scrape_and_reply(url, update, context)

if __name__ == '__main__':
    # Start Flask Server for UptimeRobot
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('p', get_poster_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_button))
    
    print("Bot is running...")
    application.run_polling()
