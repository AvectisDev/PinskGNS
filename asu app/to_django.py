import requests

BASE_URL = "http://10.10.12.253:8000/api"  # server address
TRUCKS_URL = "http://10.10.12.253:8000/api/trucks"
TRAILERS_URL = "http://10.10.12.253:8000/api/trailers"
USERNAME = "reader"
PASSWORD = "rfid-device"


def get_transport(number, transport_type):
    if transport_type == 'truck':
        BASE_URL = TRUCKS_URL
    elif transport_type == 'trailer':
        BASE_URL = TRAILERS_URL

    try:
        response = requests.get(f"{BASE_URL}?registration_number={number}", auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return True, response.json()

    except requests.RequestException as e:
        return False, e.response.status_code if e.response else None


def create_transport(data, transport_type):
    if transport_type == 'truck':
        BASE_URL = TRUCKS_URL
    elif transport_type == 'trailer':
        BASE_URL = TRAILERS_URL

    try:
        response = requests.post(BASE_URL, json=data, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return True, response.json()

    except requests.RequestException as e:
        return False, e.response.status_code if e.response else None


def update_transport(data, transport_type):
    if transport_type == 'truck':
        BASE_URL = TRUCKS_URL
    elif transport_type == 'trailer':
        BASE_URL = TRAILERS_URL

    try:
        response = requests.patch(BASE_URL, json=data, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return True, response.json()

    except requests.RequestException as e:
        return False, e.response.status_code if e.response else None


def get_batch_gas():
    """Проверяет наличие в базе данных активных партий отгрузки газа в автоцистернах и возвращает признак True и данные
    активной партии, если партия есть в базе, и False - если таких партий нет.

    Returns:
        tuple: (bool, str or dict) - статус наличия партии и данные партии или сообщение об ошибке.
    """

    try:
        response = requests.get(f"{BASE_URL}/auto-gas-loading", timeout=1, auth=(USERNAME, PASSWORD))
        response.raise_for_status()  # Проверка на успешный статус-код
    except requests.exceptions.RequestException as e:
        return False, {"status": str(e)}  # Вернет сообщение об ошибке запроса

    try:
        data = response.json()
        if response.status_code == 200:
            return True, data

        return False, {'error', "Unknown error"}
    except (ValueError, KeyError):  # Обработка ошибок кода JSON и ключей
        return False, {"status": "invalid response"}


def create_batch_gas(data):
    try:
        response = requests.post(f"{BASE_URL}/auto-gas-loading", json=data, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return True, response.json()

    except requests.RequestException as e:
        return False, e.response.status_code if e.response else None


def update_batch_gas(data):
    try:
        response = requests.patch(f"{BASE_URL}/auto-gas-loading", json=data, timeout=1, auth=(USERNAME, PASSWORD))
        response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
        return True, {"status": "ok"}
    except KeyError:
        return False, {"status": "no valid response - missing key"}
    except requests.RequestException as e:  # Уточняем исключения requests
        return False, {"status": f"request failed: {str(e)}"}
