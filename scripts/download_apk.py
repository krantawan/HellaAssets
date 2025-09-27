#!/usr/bin/env python3

import argparse
import os
from playwright.sync_api import sync_playwright
import re
import requests
import sys


def get_apk_url(server, user_agent):
    retries = 5
    for attempt in range(retries):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent=user_agent)
                page = context.new_page()

                if server == 'cn':
                    page.goto("https://www.biligame.com/detail/?id=101772", wait_until="networkidle", timeout=90000)
                    content = page.content()
                    matches = re.findall(r'<a href="https://pkg\.bili[^"]+\.apk', content)
                    download_url = re.sub(r'^.*href="', '', matches[0])
                    return download_url

                elif server == 'en':
                    with page.expect_download(timeout=90000) as download_info:
                        try:
                            page.goto("https://d.apkpure.com/b/XAPK/com.YoStarEN.Arknights?version=latest", timeout=90000)
                        except Exception as e:
                            if (not "Page.goto: net::ERR_ABORTED at" in str(e) and not "Page.goto: Download is starting" in str(e)):
                                raise e
                        download = download_info.value
                        return download.url

                browser.close()
                break
        except Exception as e:
            print(f'URL attempt {attempt + 1} failed: {e}', file=sys.stderr)
            if attempt == retries - 1:
                print(f'Failed to get APK url after {retries} attempts.', file=sys.stderr)
                exit(1)


def download_apk(server, url, dest, user_agent):
    retries = 5
    for attempt in range(retries):
        try:
            headers = {'User-Agent': user_agent}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            os.makedirs(dest, exist_ok=True)
            with open(f'{dest}/{server}.apk', 'wb') as f:
                f.write(response.content)
            break
        except requests.exceptions.RequestException as e:
            print(f'Download attempt {attempt + 1} failed: {e}', file=sys.stderr)
            if attempt == retries - 1:
                print(f'Failed to download APK after {retries} attempts.', file=sys.stderr)
                exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=str, dest='server', choices=['cn', 'en'], required=True, help='Server to download from.')
    parser.add_argument('--dest', type=str, dest='dest', default='download', help='Directory to download APK file into.')
    parser.add_argument('--old-url', type=str, dest='old_url', default='', help='Old APK URL to compare against.')
    args = parser.parse_args()

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81"

    apk_url = get_apk_url(args.server, user_agent)
    print(apk_url)

    if args.old_url and apk_url == args.old_url:
        print('Up to date.')
        exit()

    download_apk(args.server, apk_url, args.dest, user_agent)


if __name__ == "__main__":
    main()
