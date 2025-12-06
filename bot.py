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
from urllib.parse import urlparse, parse_qs, urljoin
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from vplink_bypass import bypass_vplink

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

# --- HELPER FUNCTIONS ---
def rot13(s):
    return codecs.encode(s, 'rot_13')

def is_hubdrive_url(url):
    return "hubdrive.space" in url or "hubdrive.me" in url or "hubdrive" in url

def is_hubcloud_url(url):
    return "hubcloud" in url

def is_gofile_url(url):
    return "gofile.io" in url

def is_hubcdn_url(url):
    return "hubcdn" in url

def is_vplink_url(url):
    return "vplink" in url or "short" in url # Basic heuristic based on the image

def is_skymovieshd_url(url):
    return "skymovieshd" in url

def is_howblogs_url(url):
    return "howblogs.xyz" in url

def is_4khdhub_url(url):
    return "4khdhub.fans" in url

def is_filmyfiy_url(url):
    return "filmyfiy" in url

def is_vegamovies_url(url):
    return "vegamovies" in url

def is_katmoviehd_url(url):
    return "katmovie" in url

def is_mymp4movies_url(url):
    return "mymp4movies" in url

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

        # Try to find the result item container first
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

        # Fallback to old method if container structure fails but image is found
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

        # Prioritize Google thumbnails which are usually reliable
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('https://encrypted-tbn0.gstatic.com'):
                return src

        # Fallback to other images if no thumbnail found (less reliable)
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

# --- SEARCH FUNCTION ---
def search_movies(query):
    print(f"Searching for '{query}'...")
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
        logging.error(f"Search Error: {e}")
        return []

# --- BYPASSERS ---

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
        
        # Find all download items
        for item in soup.find_all('div', class_='download-item'):
            # Extract header text for quality info
            header = item.find('div', class_='download-header')
            if not header:
                continue
            
            header_text_div = header.find('div', class_='flex-1')
            if not header_text_div:
                continue
            
            quality_text = header_text_div.get_text(" ", strip=True)

            # Find the content div
            file_id = header.get('data-file-id')
            if not file_id:
                continue
                
            content_div = item.find('div', id=f"content-{file_id}")
            if not content_div:
                continue
                
            # Find links
            for a in content_div.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                
                # Clean up text
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

        # Find the intermediate download link
        download_link = None

        # Strategy 1: Look for specific text
        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            if "Download 480p 720p 1080p" in text:
                download_link = a['href']
                break
        
        # Strategy 2: If not found, look for any link to linkmake.in
        if not download_link:
            for a in soup.find_all('a', href=True):
                if "linkmake.in" in a['href']:
                    download_link = a['href']
                    break
        
        if not download_link:
            logging.error("Could not find the intermediate download link (linkmake.in) on the page.")
            return []
        
        logging.info(f"Found intermediate link: {download_link}")

        # Now scrape the intermediate page
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
        
        # Check for Cloudflare or other protections
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
            
            # Filter for likely download links based on keywords
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

            # Skip if href is just a fragment or relative root
            if not href or href.startswith('#') or href == '/':
                continue
            
            # Skip tag and category links
            if '/tag/' in href or '/category/' in href:
                continue
            
            # Skip self link if it matches the current url
            if href.rstrip('/') == url.rstrip('/'):
                continue

            # Check if text contains quality indicators
            if re.search(r'(480p|720p|1080p|2160p|4k)', text, re.IGNORECASE):
                # Additional check: usually download links are on specific domains or text explicitly says "Links" or "Download"
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
        # Try importing cloudscraper for advanced bypass if available
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url)
        except ImportError:
            response = requests.get(url, headers=headers, timeout=15)

        # Check for Cloudflare or other protections
        if response.status_code in [403, 503]:
             logging.error(f"Access denied (Status: {response.status_code}). Site might be protected by Cloudflare.")
             return []

        response.raise_for_status()
        soup = get_soup(response.content)

        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text().strip()
            href = a['href']
            
            # Skip empty links or javascript
            if not href or href.startswith('#') or href.startswith('javascript'):
                continue

            text_lower = text.lower()
            # Heuristic for download links from your snippet
            if any(q in text_lower for q in ['480p', '720p', '1080p', 'download']):
                links.append({'text': text, 'link': href})
        
        return links
    except Exception as e:
        logging.error(f"Mymp4Movies Scrape Error: {e}")
        return []

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

        # Check for gadgetsweb in scraped links (e.g. from 4khdhub)
        if "gadgetsweb.xyz" in original:
            gw_bypassed = bypass_gadgetsweb(original)
            if gw_bypassed:
                # Update original to the bypassed link so further checks can work
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
    
    try:
        loop = asyncio.get_running_loop()
        hits = await loop.run_in_executor(None, search_movies, user_text)
        
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)

        if not hits:
            await update.message.reply_text("❌ No results found.")
            return

        keyboard = []
        for hit in hits:
            title = hit['document']['post_title']
            permalink = hit['document']['permalink']
            
            full_url = f"https://hdhub4u.rehab{permalink}"
            
            search_id = str(uuid.uuid4())[:8]
            SEARCH_CACHE[search_id] = full_url
            
            keyboard.append([InlineKeyboardButton(title, callback_data=search_id)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Found {len(hits)} results for '{html.escape(user_text)}':", reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"Error during search: {html.escape(str(e))}", parse_mode='HTML')

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    search_id = query.data
    url = SEARCH_CACHE.get(search_id)
    
    if not url:
        await query.edit_message_text("❌ Link expired or invalid. Please search again.")
        return
        
    await query.edit_message_text(f"✅ Selected. Processing...")
    
    await perform_scrape_and_reply(url, update, context)

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('p', get_poster_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_button))
    
    print("Bot is running...")
    application.run_polling()
