"""
Web scraper — fetches pages and extracts media download/view links.
Includes safety measures against injection and malicious content.
"""

import re
import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB max response

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Patterns for media links
MAGNET_RE = re.compile(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+', re.IGNORECASE)
THUNDER_RE = re.compile(r'thunder://[a-zA-Z0-9+/=]+', re.IGNORECASE)
PAN_RE = re.compile(r'https?://pan\.baidu\.com/s/[a-zA-Z0-9_-]+', re.IGNORECASE)
PAN_EXTRACT_RE = re.compile(
    r'(?:https?://)?(?:pan\.baidu\.com/s/[a-zA-Z0-9_-]+)'
    r'(?:\s*(?:提取码|密码|pwd)[：:\s]*([a-zA-Z0-9]{4}))?',
    re.IGNORECASE,
)
ALIYUN_RE = re.compile(r'https?://www\.aliyundrive\.com/s/[a-zA-Z0-9]+', re.IGNORECASE)
QUARK_RE = re.compile(r'https?://pan\.quark\.cn/s/[a-zA-Z0-9]+', re.IGNORECASE)
M3U8_RE = re.compile(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', re.IGNORECASE)

DANGEROUS_TAGS = {"script", "iframe", "object", "embed", "applet", "form"}


def _sanitize_html(soup: BeautifulSoup) -> None:
    """Remove dangerous tags and attributes from parsed HTML."""
    for tag_name in DANGEROUS_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    dangerous_attrs = {"onerror", "onload", "onclick", "onmouseover",
                       "onfocus", "onblur"}
    for tag in soup.find_all(True):
        for attr in list(tag.attrs.keys()):
            val = str(tag[attr]).lower()
            if attr.lower() in dangerous_attrs:
                del tag[attr]
            elif any(d in val for d in
                     ("javascript:", "data:text/html", "vbscript:")):
                del tag[attr]


def _is_valid_url(url: str) -> bool:
    """Check if URL is well-formed and not suspicious."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https", "magnet", "thunder", "ed2k"):
            return False
        if len(url) > 2048:
            return False
        return True
    except Exception:
        return False


def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT):
    """Fetch a page. Returns (html_content | None, error_message | None)."""
    try:
        with httpx.Client(
            timeout=timeout, headers=HEADERS,
            follow_redirects=True, max_redirects=5,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

            content_length = len(resp.content)
            if content_length > MAX_RESPONSE_SIZE:
                logger.warning(f"Response too large ({content_length}B): {url}")
                content = resp.content[:MAX_RESPONSE_SIZE]
            else:
                content = resp.content

            if resp.encoding:
                html = content.decode(resp.encoding, errors="replace")
            else:
                html = content.decode("utf-8", errors="replace")
            return html, None

    except httpx.HTTPStatusError as e:
        return None, f"HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        return None, "timeout"
    except Exception as e:
        return None, str(e)[:200]


def extract_links(html: str, base_url: str = "") -> dict:
    """Extract media links from HTML. Returns dict of categorized links."""
    result = {
        "magnets": [], "thunder": [], "pan": [],
        "aliyun": [], "quark": [], "m3u8": [], "online": [],
    }

    soup = BeautifulSoup(html, "lxml")
    _sanitize_html(soup)

    all_links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        if base_url and not href.startswith(("http", "magnet", "thunder")):
            href = urljoin(base_url, href)
        if not _is_valid_url(href):
            continue

        all_links.add(href)
        text = a_tag.get_text(strip=True).lower()

        if href.startswith("magnet:"):
            result["magnets"].append({"url": href, "label": "磁力链接"})
        elif href.startswith("thunder://"):
            result["thunder"].append({"url": href, "label": "迅雷链接"})
        elif "pan.baidu.com" in href:
            result["pan"].append({"url": href, "label": "百度网盘"})
        elif "aliyundrive.com" in href:
            result["aliyun"].append({"url": href, "label": "阿里云盘"})
        elif "pan.quark.cn" in href:
            result["quark"].append({"url": href, "label": "夸克网盘"})

    # Raw text extraction for links not in <a> tags
    page_text = soup.get_text()
    for match in MAGNET_RE.finditer(page_text):
        url = match.group(0)
        if url not in {m["url"] for m in result["magnets"]}:
            result["magnets"].append({"url": url, "label": "磁力链接"})

    for match in THUNDER_RE.finditer(page_text):
        url = match.group(0)
        if url not in {t["url"] for t in result["thunder"]}:
            result["thunder"].append({"url": url, "label": "迅雷链接"})

    for match in PAN_EXTRACT_RE.finditer(page_text):
        url_part = match.group(1)
        if not url_part.startswith("http"):
            url = "https://" + url_part
        else:
            url = url_part
        code = match.group(2) or ""
        existing = [p for p in result["pan"] if p["url"] == url]
        if not existing:
            entry = {"url": url, "label": "百度网盘"}
            if code:
                entry["code"] = code
            result["pan"].append(entry)
        elif code and "code" not in existing[0]:
            existing[0]["code"] = code

    for match in M3U8_RE.finditer(page_text):
        url = match.group(0)
        result["m3u8"].append({"url": url, "label": "M3U8 流"})

    # Online viewing pages
    watch_kw = ["/play", "/watch", "/video", "/detail", "/episode",
                "/movie", "/tv", "/show", "/vod", "/live", "/player", "/stream"]
    for href in all_links:
        parsed = urlparse(href)
        path_lower = parsed.path.lower()
        if any(kw in path_lower for kw in watch_kw):
            if not href.startswith(("magnet:", "thunder://")):
                result["online"].append({"url": href, "label": "在线观看"})

    # Deduplicate
    for key in result:
        seen = set()
        unique = []
        for item in result[key]:
            if item["url"] not in seen:
                seen.add(item["url"])
                unique.append(item)
        result[key] = unique

    return result


def scrape_for_media(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Fetch a page and extract media links."""
    html, error = fetch_page(url, timeout=timeout)
    if error or html is None:
        return {"url": url, "error": error or "unknown error", "links": {}}
    links = extract_links(html, base_url=url)
    return {"url": url, "error": None, "links": links}


def scrape_search_results(
    search_results: list[dict],
    max_pages: int = 8,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Scrape top N pages from search results for media links."""
    results = []
    urls = [r["href"] for r in search_results[:max_pages]
            if r.get("href") and _is_valid_url(r["href"])]

    logger.info(f"Scraping {len(urls)} pages from search results")
    for url in urls:
        scraped = scrape_for_media(url, timeout=timeout)
        results.append(scraped)
    return results
