READER_LIST = [{} for i in range(1)]

# Считыватели на приёмке
# Г-образный
READER_LIST[0] = {
    'ip': '192.168.0.20',
    'port': 10001,
    'number': 1,
    'status': 'Регистрация пустого баллона на складе (из кассеты)',
    'input_state': 0,
    'previous_nfc_tags': [],
    'function': None,
    'batch': {'batch_id': 0, 'balloon_id': 0}
}

# Команды, посылаемые на считыватель
COMMANDS = {
    'host_read': '020009ffb001001843',
    'read_complete': '02000DFF72010181010019236B',  # зажигаем зелёную лампу на считывателе на 2.5 сек
    'read_complete_with_error': '02000DFF720101810B0014BCC3',  # мигание зелёной лампы на считывателе 2 сек
    'buffer_read': '020009FFB02B005B9D',  # чтение буферной памяти
    'inputs_read': '020007FF746660',  # чтение состояния входов
    'all_buffer_read': '02000AFF2B0000FF89EB',  # чтение всего буфера
    'read_last_item_from_buffer': '02000AFF2B00FFFF4914',
    'clean_buffer': '020007FF325447'  # команда очистки буфера
}
# 02 00 08 FF B0 84 4F DB   Reader: RF-Warning - если нет данных с ридера
