#!/usr/bin/env python3

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import requests
import time


def download_file(item, assets_url, download_dir):
    filename = item['name']
    print(round(item['totalSize']/1000/1000, 1), 'MB', filename)
    filename = filename.replace('/', '_').replace('#', '__').split('.')[0] + '.dat'
    retries = 5
    for attempt in range(retries):
        try:
            response = requests.get(f'{assets_url}/{filename}')
            response.raise_for_status()
            with open(f'{download_dir}/{filename}', 'wb') as f:
                f.write(response.content)
            os.system(f'unzip -q "{download_dir}/{filename}" -d "{download_dir}/"')
            os.remove(f'{download_dir}/{filename}')
            break
        except requests.exceptions.RequestException as e:
            print(f'Attempt {attempt + 1} failed: {e}')
            if attempt == retries - 1:
                print(f'Failed to download {filename} after {retries} attempts.')
            else:
                time.sleep(attempt * 2 + 1)


def main():
    parser = argparse.ArgumentParser(description='CLI tool to download Arknights "hot update" asset files.')
    parser.add_argument('--server', type=str, dest='server', choices=['cn', 'en'], required=True, help='Server to download from.')
    parser.add_argument('--dest', type=str, dest='dest', default='download', help='Directory to download files into.')
    parser.add_argument('--old-list', type=str, dest='old_list', default='hot_update_list.json', help='Path to old hot update list.')
    parser.add_argument('--always', type=str, dest='always', default='', help='Semi-colon separated list of filenames to always download. Uses substring matching. Takes precedence over --skip-download.')
    parser.add_argument('--skip', type=str, dest='skip', default='', help='Semi-colon separated list of filenames to skip. Uses substring matching.')
    args = parser.parse_args()

    server_urls = {
        'cn': 'https://ak-conf.hypergryph.com/config/prod/b/network_config',
        'en': 'https://ak-conf.arknights.global/config/prod/official/network_config'
    }
    server_url = server_urls[args.server]
    dest = args.dest
    old_list_file = args.old_list
    always_downloads = args.always.split(';') if len(args.always) > 0 else []
    skip_downloads = args.skip.split(';') if len(args.skip) > 0 else []

    network_config = requests.get(server_url).json()
    network_contents = json.loads(network_config['content'])
    network_urls = network_contents['configs'][network_contents['funcVer']]['network']
    res_version = requests.get(network_urls['hv'].replace('{0}', 'Android')).json()['resVersion']
    assets_url = f'{network_urls["hu"]}/Android/assets/{res_version}'

    if not os.path.exists(old_list_file) or os.stat(old_list_file).st_size == 0:
        old_list = {'versionId': '', 'abInfos': []}
    else:
        with open(old_list_file, 'r') as f:
            old_list = json.load(f)
            if (old_list['versionId'] == res_version and not always_downloads):
                print('Up to date.')
                exit(0)

    new_list = requests.get(f'{assets_url}/hot_update_list.json').json()
    with open(old_list_file, 'w') as f:
        f.write(json.dumps(new_list))
        print(f'Updated {old_list_file}: {old_list["versionId"]} -> {res_version}')

    os.makedirs(dest, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        for item in new_list['abInfos']:
            filename = item['name']
            hash = item['hash']

            is_force_file = any(always in filename or always == filename for always in always_downloads)
            is_skip_file = any(x for x in skip_downloads if x in filename)
            is_old_file = any(x for x in old_list['abInfos'] if x['name'] == filename and x['hash'] == hash)

            if is_force_file:
                pass
            else:
                if is_skip_file:
                    # print('Skipping', round(item['totalSize']/1000/1000, 1), 'MB', filename)
                    continue
                if is_old_file:
                    continue

            executor.submit(download_file, item, assets_url, dest)


if __name__ == "__main__":
    main()
