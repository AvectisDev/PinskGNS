import requests


def get_balloon_by_nfc_tag(nfc_tag):
    url = f'https://publicapi-vitebsk.cloud.gas.by/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    try:
        response = requests.get(url, timeout=1)
        if response.status_code == 200:
            if response.json()['status'] == "Ok":
                return True, response.json()['List']

            else:  # ['status'] == "Error"
                return False, response.json()['error']
        else:
            return False, {"status": response.status_code}
    except KeyError:
        return False, {"status": "no valid response"}
    except:
        return False, {"status": "no valid response"}


def search_balloon_by_nfc_tag(nfc_tag):
    url = f'https://publicapi-vitebsk.cloud.gas.by/searchballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'
    headers = {
        'accept': 'application/json',
        'Authorization': 'Basic cGluc2tyZmlkZ25zOlhpbzhCemgzY0JRa0xtNQ=='
    }
    response = requests.get(url, timeout=1)
    if response.status_code == 200:
        try:
            if response.json()['status'] == "Ok":
                return True, response.json()['List']

            else:  # ['status'] == "Error"
                return False, response.json()['error']
        except KeyError:
            return False, {"status": "no valid response"}
    else:
        return False, {"status": response.status_code}
