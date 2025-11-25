# fetcher.py
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

USER_AGENT = "searchagent/1.0 (+https://github.com/yourname)"

def fetch_url_text(url, timeout=10):
    """
    Return (title, text) or raise.
    Keep this simple; you can enhance with readability/parsing libs later.
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
    except RequestException as e:
        raise

    soup = BeautifulSoup(r.text, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    # Remove script/style and get visible text
    for s in soup(["script", "style", "noscript", "header", "footer", "svg"]):
        s.extract()
    texts = soup.get_text(separator="\n")
    # Normalize whitespace
    lines = [ln.strip() for ln in texts.splitlines() if ln.strip()]
    text = "\n".join(lines)
    return title, text
