"""
stego_lib: Modular library for steganography on multiple images.
"""

__version__ = '1.0.0'

from stego_lib.core.encoder import StegoEncoder
from stego_lib.core.decoder import StegoDecoder
from stego_lib.io.image_handler import ImageContainer

# Convenience functions for simplified API
def hide_message(message, image_paths, password=None, bits_per_channel=2):
    """Hide a message in a series of images"""
    encoder = StegoEncoder(password=password, bits_per_channel=bits_per_channel)
    return encoder.encode(message, image_paths)

def reveal_message(stego_images, password=None):
    """Reveals a hidden message in images"""
    decoder = StegoDecoder(password=password)
    return decoder.decode(stego_images)

def calculate_capacity(image_paths, bits_per_channel=2):
    """Calculates available capacity in bytes for a list of images"""
    container = ImageContainer(bits_per_channel=bits_per_channel)
    return container.calculate_batch_capacity(image_paths)