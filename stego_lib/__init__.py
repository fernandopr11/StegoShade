"""
stego_lib: Modular library for steganography on multiple images.
"""

__version__ = '1.0.0'

from stego_lib.core.encoder import StegoEncoder
from stego_lib.core.decoder import StegoDecoder
from stego_lib.io.directory_handler import get_png_images
from stego_lib.io.image_handler import ImageContainer
from stego_lib.utils.debug import set_debug


def enable_debug(enabled=False):
    """Enable or disable debug logging"""
    set_debug(enabled)

# Convenience functions for simplified API
def hide_message(message, image_paths, password=None, bits_per_channel=2):
    """Hide a message in a series of images"""
    encoder = StegoEncoder(password=password, bits_per_channel=bits_per_channel)
    return encoder.encode(message, image_paths)


def reveal_message(directory, password=None, bits_per_channel=2):
    """
    Revela un mensaje oculto en un directorio de imágenes PNG.

    Args:
        directory: Directorio que contiene las imágenes PNG.
        password: Contraseña para descifrar los datos (opcional).
        bits_per_channel: Número de bits modificados por canal (1-4).

    Returns:
        str: Mensaje revelado.
    """
    image_paths = get_png_images(directory)
    if not image_paths:
        raise ValueError("No se encontraron imágenes PNG en el directorio.")

    decoder = StegoDecoder(password=password, bits_per_channel=bits_per_channel)
    message = decoder.decode(image_paths)
    return message.decode('utf-8')

def calculate_capacity(image_paths, bits_per_channel=2):
    """Calculates available capacity in bytes for a list of images"""
    container = ImageContainer(bits_per_channel=bits_per_channel)
    return container.calculate_batch_capacity(image_paths)