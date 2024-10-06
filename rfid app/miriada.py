import aiohttp
import asyncio

BASE_URL = 'https://publicapi-vitebsk.cloud.gas.by'  # miriada server address


async def get_balloon_by_nfc_tag(nfc_tag: str):
    url = f'{BASE_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=2) as response:
                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                result = await response.json()

                if result.get('status') == "Ok":
                    return result['List']
                else:
                    return []

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_balloon_by_nfc_tag function error: {error}')
            return None
        except Exception as error:
            print(f'get_balloon_by_nfc_tag function error: {error}')
            return None


async def search_balloon_by_nfc_tag(nfc_tag):
    url = f'{BASE_URL}/searchballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'
    headers = {
        'accept': 'application/json',
        'Authorization': 'Basic cGluc2tyZmlkZ25zOlhpbzhCemgzY0JRa0xtNQ=='
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=2) as response:
                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                result = await response.json()

                if result.get('status') == "Ok":
                    return result['List']
                else:
                    return []

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_balloon_by_nfc_tag function error: {error}')
            return None
        except Exception as error:
            print(f'get_balloon_by_nfc_tag function error: {error}')
            return None
