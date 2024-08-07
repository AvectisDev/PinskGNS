readers = [{} for i in range(8)]

# Считыватели на приёмке
# Г-образный
readers[0] = {
    'ip': '10.10.2.20',
    'port': 10001,
    'number': 1,
    'status': 'Регистрация пустого баллона на складе (из кассеты)',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

# Г-образный
readers[1] = {
    'ip': '10.10.2.21',
    'port': 10001,
    'number': 2,
    'status': 'Погрузка полного баллона в кассету',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

# Считыватели на отгрузке
readers[2] = {
    'ip': '10.10.2.22',
    'port': 10001,
    'number': 3,
    'status': 'Погрузка полного баллона на трал 1',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

readers[3] = {
    'ip': '10.10.2.23',
    'port': 10001,
    'number': 4,
    'status': 'Погрузка полного баллона на трал 2',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

readers[4] = {
    'ip': '10.10.2.24',
    'port': 10001,
    'number': 5,
    'status': 'Регистрация полного баллона на складе',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

readers[5] = {
    'ip': '10.10.2.25',
    'port': 10001,
    'number': 6,
    'status': 'Регистрация пустого баллона на складе (рампа)',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

# Считыватели в цеху
readers[6] = {
    'ip': '10.10.2.26',
    'port': 10001,
    'number': 7,
    'status': 'Регистрация пустого баллона на складе (цех)',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

readers[7] = {
    'ip': '10.10.2.27',
    'port': 10001,
    'number': 8,
    'status': 'Наполнение баллона сжиженным газом',
    'input_state': 0,
    'day_amount': 0,
    'nfc_tag': ''
}

# Команды, посылаемые на считыватель
COMMANDS = {
    'host_read': '020009ffb001001843',
    'read_complete': '02000DFF72010181010019236B',  # зажигаем зелёную лампу на считывателе на 2.5 сек
    'read_complete_with_error': '',
    'buffer_read': '020009FFB02B005B9D',  # чтение буферной памяти
    'inputs_read': '020007FF746660'  # чтение состояния входов
}
