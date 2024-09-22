"""
Номера серверов "Интеллект":
    1 - ЖД Весовая
    - Камера 25 (Весовая автотранспорта 1) -> "id": "2"
    - Камера 26 (Весовая автотранспорта 2) -> "id": "3"
    - Камера 27 (Распознавание номеров КПП Выезд) -> "id": "4", direction = 1 - от камеры, 2 - к камере
    - Камера 28 (Распознавание номеров КПП Въезд) -> "id": "5", direction = 1 - от камеры, 2 - к камере
"""
INTELLECT_URL = "http://10.10.0.252:10001/lprserver/GetProtocolNumbers"  # intellect server address
INTELLECT_SERVER_LIST = [
    {
        'id': '1',
        'delta_minutes': 2
    },
    {
        'id': '2,3',
        'delta_minutes': 10
    },
    {
        'id': '4,5',
        'delta_minutes': 2
    }
]

GAS_LOADING_BATCH = {
    'command_start': False,
    'start_flag': False,
    'process_step': 0,
    'is_active': False,
    'truck_id': None,
    'trailer_id': None,
    'initial_mass_meter': 0,
    'final_mass_meter': 0,
    'gas_amount': 0,
    'truck_full_weight': 0,
    'truck_empty_weight': 0,
    'weight_gas_amount': 0
}

GAS_UNLOADING_BATCH = {
    'command_start': False,
    'start_flag': False,
    'process_step': 0,
    'is_active': False,
    'truck_id': None,
    'trailer_id': None,
    'initial_mass_meter': 0,
    'final_mass_meter': 0,
    'gas_amount': 0,
    'truck_full_weight': 0,
    'truck_empty_weight': 0,
    'weight_gas_amount': 0
}

RAILWAY_BATCH = {
    'command_start': False,
    'start_flag': False,
    'process_step': 0,
    'is_active': False,
    'tank_id': None,
    'tank_full_weight': 0,
    'tank_empty_weight': 0,
    'weight_gas_amount': 0
}
