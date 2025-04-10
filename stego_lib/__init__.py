"""
stego_lib: Modular library for steganography on multiple images.
"""

__version__ = '1.0.0'

from stego_lib.core.encoder import StegoEncoder
from stego_lib.core.decoder import StegoDecoder
from stego_lib.io.directory_handler import get_png_images
from stego_lib.io.image_handler import ImageContainer
from stego_lib.utils.debug import set_debug
import os


def enable_debug(enabled=False):
    """
    Enable or disable debug logging for the library.

    Args:
        enabled (bool): If True, enables debug mode. Default is False.
    """
    set_debug(enabled)


def hide_message(message, image_paths, password=None, bits_per_channel=2):
    """
    Hides a message across a list of images.

    Args:
        message (str): The message to hide.
        image_paths (list): List of paths to PNG images.
        password (str, optional): Password used for optional encryption.
        bits_per_channel (int): Number of bits to use per color channel (1-4).

    Returns:
        list: List of image paths with the hidden message.
    """
    encoder = StegoEncoder(password=password, bits_per_channel=bits_per_channel)
    return encoder.encode(message, image_paths)


def reveal_messages(directory, password=None, bits_per_channel=2):
    """
    Reveals one or more hidden messages from PNG images in a directory.

    Args:
        directory (str): Directory containing PNG images.
        password (str, optional): Password to decrypt the data, if any.
        bits_per_channel (int): Number of bits used per color channel (1-4).

    Returns:
        str: Concatenated messages found in the images.
    """
    image_paths = get_png_images(directory)
    if not image_paths:
        raise ValueError("No PNG images found in the specified directory.")

    decoder = StegoDecoder(password=password, bits_per_channel=bits_per_channel)
    messages_bytes = decoder.decode(image_paths)

    # Convert each message from bytes to text and concatenate
    messages = []
    for i, msg_bytes in enumerate(messages_bytes):
        try:
            messages.append(f"--- Message #{i + 1} ---\n{msg_bytes.decode('utf-8')}")
        except UnicodeDecodeError:
            messages.append(f"--- Message #{i + 1} --- [Binary data]")

    return "\n\n".join(messages)


def calculate_image_capacities(directory, bits_per_channel=2):
    """
    Calculates and prints the capacity of each image in a directory for hiding data.

    Args:
        directory (str): Directory containing PNG images.
        bits_per_channel (int): Number of bits per channel to use (1-4).

    Returns:
        dict: Dictionary containing detailed storage info for each image.
    """
    from stego_lib.io.directory_handler import get_png_images
    from stego_lib.io.image_handler import ImageContainer
    import os

    image_paths = get_png_images(directory)
    if not image_paths:
        raise ValueError("No PNG images found in the specified directory.")

    # Sort image paths lexicographically by filename
    image_paths = sorted(image_paths, key=lambda x: os.path.basename(x))

    container = ImageContainer(bits_per_channel=bits_per_channel)
    _, _, space_info = container.calculate_batch_capacity(image_paths)

    # Generate a summarized report
    summary = {}
    for img_path in image_paths:
        used, available, capacity = space_info[img_path]
        percent_used = (used / capacity * 100) if capacity > 0 else 0
        summary[img_path] = {
            "filename": os.path.basename(img_path),
            "capacity_bytes": capacity,
            "capacity_kb": capacity / 1024,
            "used_bytes": used,
            "used_kb": used / 1024,
            "available_bytes": available,
            "available_kb": available / 1024,
            "percent_used": percent_used
        }

        # Print per-image info
        print(f"{os.path.basename(img_path)}: {capacity / 1024:.2f} KB | "
              f"Used: {used / 1024:.2f} KB ({percent_used:.1f}%) | "
              f"Available: {available / 1024:.2f} KB")

    # Compute total summary
    total_capacity = sum(info[2] for info in space_info.values())
    total_used = sum(info[0] for info in space_info.values())
    total_available = sum(info[1] for info in space_info.values())
    percent_used_total = (total_used / total_capacity * 100) if total_capacity > 0 else 0

    print("\nOverall summary:")
    print(f"Total capacity: {total_capacity / 1024:.2f} KB")
    print(f"Total used: {total_used / 1024:.2f} KB ({percent_used_total:.1f}%)")
    print(f"Total available: {total_available / 1024:.2f} KB")

    return summary