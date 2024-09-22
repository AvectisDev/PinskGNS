import aiohttp
import asyncio

BASE_URL = 'https://publicapi-vitebsk.cloud.gas.by'  # miriada server address


async def get_balloon_by_nfc_tag(nfc_tag: str):
    url = f'{BASE_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=1) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data.get('status') == "Ok":
                        return True, response_data['List']
                    else:
                        return False, response_data.get('error', "Unknown error")
                else:
                    return False, {"status": response.status}
        except asyncio.TimeoutError:
            return False, {"status": "request timed out"}
        except Exception as e:
            return False, {"status": str(e)}


async def search_balloon_by_nfc_tag(nfc_tag):
    url = f'{BASE_URL}/searchballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'
    headers = {
        'accept': 'application/json',
        'Authorization': 'Basic cGluc2tyZmlkZ25zOlhpbzhCemgzY0JRa0xtNQ=='
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=1) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data.get('status') == "Ok":
                        return True, response_data.get('List', [])
                    else:
                        return False, response_data.get('error', "Unknown error")
                else:
                    return False, {"status": response.status}

        except asyncio.TimeoutError:
            return False, {"status": "request timed out"}
        except Exception as e:
            return False, {"status": str(e)}
