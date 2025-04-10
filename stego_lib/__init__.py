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

def reveal_messages(directory, password=None, bits_per_channel=2):
    """
    Revela uno o más mensajes ocultos en un directorio de imágenes PNG.

    Args:
        directory: Directorio que contiene las imágenes PNG.
        password: Contraseña para descifrar los datos (opcional).
        bits_per_channel: Número de bits modificados por canal (1-4).

    Returns:
        str: Mensajes revelados concatenados.
    """
    from stego_lib.io.directory_handler import get_png_images
    from stego_lib.core.decoder import StegoDecoder

    image_paths = get_png_images(directory)
    if not image_paths:
        raise ValueError("No se encontraron imágenes PNG en el directorio.")

    decoder = StegoDecoder(password=password, bits_per_channel=bits_per_channel)
    messages_bytes = decoder.decode(image_paths)

    # Convertir cada mensaje a texto y concatenarlos
    messages = []
    for i, msg_bytes in enumerate(messages_bytes):
        try:
            messages.append(f"--- Mensaje #{i + 1} ---\n{msg_bytes.decode('utf-8')}")
        except UnicodeDecodeError:
            messages.append(f"--- Mensaje #{i + 1} --- [Datos binarios]")

    return "\n\n".join(messages)