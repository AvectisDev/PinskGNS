import requests


def get_loading_batch_balloons():
    url = f'http://10.10.12.253:8000/api/rfid/GetShippingBatchBalloons'
    # url = f'http://127.0.0.1:8000/api/rfid/GetLoadingBatchBalloons'
    try:
        response = requests.get(url, timeout=1)
        if response.status_code == 200:
            if response.json()['status'] == "ok":
                return True, response.json()['loading_batch_id']

            else:  # ['status'] == "error"
                return False, response.json()['error']
        else:
            return False, {"status": response.status_code}
    except KeyError:
        return False, {"status": "no valid response"}
    except:
        return False, {"status": "no valid response"}


def update_loading_batch_balloons(reader: dict):
    url = f'http://10.10.12.253:8000/api/rfid/UpdateShippingBatchBalloons'
    # url = f'http://127.0.0.1:8000/api/rfid/UpdateLoadingBatchBalloons'
    data = {
        'loading_batch_id': reader['batch']['loading_batch_id'],
        'balloons_list': reader['batch']['balloons_list']
    }
    try:
        response = requests.post(url, json=data, timeout=1)
        if response.status_code == 200:
            return True, {"status": "ok"}
        else:
            return False, {"status": response.status_code}
    except KeyError:
        return False, {"status": "no valid response"}
    except:
        return False, {"status": "no valid response"}

#
# data = {'batch': {'loading_batch_id': '6', 'balloons_list': ['sdg', 'sdg', 'sdg', 'sdg']}}
# print(get_loading_batch_balloons())
# print(update_loading_batch_balloons(data))
