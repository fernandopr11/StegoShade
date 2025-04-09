# stego_lib/utils/debug.py
import time
import logging
from functools import wraps

# Configurar el logger
logger = logging.getLogger('stego_lib')
logger.setLevel(logging.DEBUG)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Variables para controlar el debug
DEBUG_ENABLED = True


def set_debug(enabled=False):
    """Habilita o deshabilita el modo debug"""
    global DEBUG_ENABLED
    DEBUG_ENABLED = enabled
    logger.setLevel(logging.DEBUG if enabled else logging.INFO)


def log_debug(message):
    """Registra un mensaje de debug"""
    if DEBUG_ENABLED:
        logger.debug(message)


def time_it(func):
    """Decorador para medir el tiempo de ejecución de una función"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not DEBUG_ENABLED:
            return func(*args, **kwargs)

        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time

        func_name = func.__name__
        logger.debug(f"Función {func_name} completada en {elapsed_time:.4f} segundos")
        return result

    return wrapper