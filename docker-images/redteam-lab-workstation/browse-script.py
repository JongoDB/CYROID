#!/usr/bin/env python3
"""
Simulates an employee browsing the company WordPress site.
This will trigger BeEF hooks if the attacker has injected them.
"""

import os
import time
import random
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By

def get_browser():
    options = Options()
    options.add_argument('--headless')
    service = Service('/usr/local/bin/geckodriver')
    return webdriver.Firefox(options=options, service=service)

def browse_wordpress():
    wordpress_url = os.environ.get('WORDPRESS_URL', 'http://wordpress')
    print(f"[*] Starting simulated browsing to {wordpress_url}")

    browser = get_browser()

    try:
        print(f"[*] Visiting homepage...")
        browser.get(wordpress_url)
        time.sleep(random.uniform(2, 5))

        print(f"[*] Visiting employee directory...")
        browser.get(f"{wordpress_url}/employees/")
        time.sleep(random.uniform(3, 8))

        try:
            links = browser.find_elements(By.TAG_NAME, 'a')
            if links:
                link = random.choice(links[:5])
                link.click()
                time.sleep(random.uniform(2, 5))
        except Exception as e:
            print(f"[!] Error clicking: {e}")

        print(f"[*] Searching employee directory...")
        browser.get(f"{wordpress_url}/employees/?search=IT")
        time.sleep(random.uniform(3, 6))

    except Exception as e:
        print(f"[!] Browser error: {e}")
    finally:
        browser.quit()

def main():
    interval = int(os.environ.get('BROWSE_INTERVAL', '60'))
    print(f"[*] Workstation simulation started, interval: {interval}s")

    while True:
        try:
            browse_wordpress()
        except Exception as e:
            print(f"[!] Error in browse cycle: {e}")

        sleep_time = interval + random.randint(-10, 10)
        print(f"[*] Sleeping {sleep_time} seconds...")
        time.sleep(sleep_time)

if __name__ == '__main__':
    main()
