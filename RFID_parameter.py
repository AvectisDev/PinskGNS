readers = [{} for i in range(8)]

# Считыватели на приёмке
# Г-образный
readers[0] = {
    'ip': '10.10.2.20', 
    'port': 10001, 
    'status': 'Регистрация пустого баллона на складе (из кассеты)',
    'nfc_tag': ''
    }

# Г-образный
readers[1] = {
    'ip': '10.10.2.21', 
    'port': 10001, 
    'status': 'Погрузка полного баллона в кассету',
    'nfc_tag': ''
    }

# Считыватели на отгрузке
readers[2] = {
    'ip': '10.10.2.22', 
    'port': 10001, 
    'status': 'Погрузка полного баллона на тралл 1',
    'nfc_tag': ''
    }

readers[3] = {
    'ip': '10.10.2.23', 
    'port': 10001, 
    'status': 'Погрузка полного баллона на тралл 2',
    'nfc_tag': ''
    }

readers[4] = {
    'ip': '10.10.2.24', 
    'port': 10001, 
    'status': 'Регистрация полного баллона на складе',
    'nfc_tag': ''
    }

readers[5] = {
    'ip': '10.10.2.25', 
    'port': 10001, 
    'status': 'Регистрация пустого баллона на складе (рампа)',
    'nfc_tag': ''
    }

# Считыватели в цеху
readers[6] = {
    'ip': '10.10.2.26', 
    'port': 10001, 
    'status': 'Регистрация пустого баллона на складе (цех)',
    'nfc_tag': ''
    }

readers[7] = {
    'ip': '10.10.2.27', 
    'port': 10001, 
    'status': 'Наполнение баллона сжиженным газом',
    'nfc_tag': ''
    }

# Комманды, посылаемые на считыватель
COMMANDS = {
    'host_read': '020009ffb001001843'
}