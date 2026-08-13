# Команды, посылаемые на считыватель
COMMANDS = {
    'read_complete':            '02 000D FF 72 01 01 81 01 00 19 236B',  # зажигаем зелёную лампу на считывателе на 2.5 сек
    'read_complete_with_error': '02 000D FF 72 01 01 81 0B 00 14 BCC3',  # мигание зелёной лампы на считывателе 2 сек
    'inputs_read': '02 0007 FF 74 6660',  # чтение состояния входов
    'read_last_item_from_buffer': '02 000A FF 2B 00 FFFF 4914',
    'clean_buffer': '02 0007 FF 32 5447'  # команда очистки буфера
}

# Аутентификация
USERNAME = "reader"
PASSWORD = "rfid-device"


def command_frame(name: str) -> bytes:
    """Собирает байтовый кадр FEIG из hex-строки COMMANDS."""
    return bytes.fromhex(COMMANDS[name].replace(' ', ''))

