from __future__ import annotations

import os
from typing import Any


def build_logging_config(logs_dir: str) -> dict[str, Any]:
    logging_config: dict[str, Any] = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'style': '{',
                'format': '{asctime} - {levelname} - {module}:{lineno} - {message}',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'with_msecs': {
                'format': '%(asctime)s.%(msecs)03d - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'ocr_compare': {
                'format': '%(asctime)s %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'filling_station_file': {
                'level': 'DEBUG',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'filling_station/filling_station.log'),
                'maxBytes': 50 * 1024 * 1024,  # 50MB
                'backupCount': 30,
                'formatter': 'verbose',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
            'carousel_file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'carousel/carousel.log'),
                'when': 'midnight',
                'backupCount': 30,
                'formatter': 'with_msecs',
                'encoding': 'utf-8',
                'delay': True,
            },
            'rfid_file': {
                'level': 'DEBUG',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'rfid/rfid.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 30,
                'formatter': 'verbose',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
            'celery_file': {
                'level': 'DEBUG',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'celery/celery.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 30,
                'formatter': 'verbose',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
            'railway_file': {
                'level': 'DEBUG',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'railway/railway.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 30,
                'formatter': 'verbose',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
            'ocr_compare_file': {
                'level': 'INFO',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'railway/ocr_compare.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 30,
                'formatter': 'ocr_compare',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
            'autogas_file': {
                'level': 'DEBUG',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'autogas/autogas.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 30,
                'formatter': 'verbose',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
            'kpp_file': {
                'level': 'DEBUG',
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(logs_dir, 'transport/kpp.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 30,
                'formatter': 'verbose',
                'encoding': 'utf-8',
                'delay': True,
                'use_gzip': False,
            },
        },
        'loggers': {
            'filling_station': {
                'handlers': ['filling_station_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'carousel': {
                'handlers': ['carousel_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'rfid': {
                'handlers': ['rfid_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery': {
                'handlers': ['celery_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'railway': {
                'handlers': ['railway_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'railway.ocr_compare': {
                'handlers': ['ocr_compare_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'autogas': {
                'handlers': ['autogas_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'kpp': {
                'handlers': ['kpp_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
        },
    }

    for handler_cfg in logging_config['handlers'].values():
        filename = handler_cfg.get('filename')
        if not filename:
            continue
        log_dir = os.path.dirname(filename)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    return logging_config
