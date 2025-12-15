# Команды, посылаемые на считыватель
COMMANDS = {
    'read_complete': '02000DFF72010181010019236B',  # зажигаем зелёную лампу на считывателе на 2.5 сек
    'read_complete_with_error': '02000DFF720101810B0014BCC3',  # мигание зелёной лампы на считывателе 2 сек
    'inputs_read': '020007FF746660',  # чтение состояния входов
    'read_last_item_from_buffer': '02 000A FF 2B 00 FFFF 4914',
    'clean_buffer': '020007FF325447'  # команда очистки буфера
}

# Аутентификация
USERNAME = "reader"
PASSWORD = "rfid-device"
