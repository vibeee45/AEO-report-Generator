import requests
from bs4 import BeautifulSoup

from app.utils.logger import logger

def scrape_website(url):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        )
    }

    try:
        logger.info(f"Scraping website: {url}")
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        title = soup.title.text.strip() if soup.title else ""

        meta = soup.find(
            "meta",
            attrs={"name": "description"}
        )

        meta_description = ""

        if meta:
            meta_description = meta.get("content", "")

        h1_count = len(soup.find_all("h1"))
        h2_count = len(soup.find_all("h2"))
        h3_count = len(soup.find_all("h3"))

        return {
            "title": title,
            "meta_description": meta_description,
            "h1_count": h1_count,
            "h2_count": h2_count,
            "h3_count": h3_count,
            "soup": soup
        }

    except requests.exceptions.Timeout:
        logger.error(f"Request to {url} timed out")
        return {
            "error": "Website request timed out"
        }

    except requests.exceptions.ConnectionError:
        logger.error(f"Unable to connect to website: {url}")
        return {
            "error": "Unable to connect to website"
        }

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        return {
            "error": str(e)
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while scraping website: {e}")
        return {
            "error": str(e)
        }
