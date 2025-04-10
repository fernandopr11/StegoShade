"""
Módulo para codificar mensajes en imágenes usando esteganografía.
"""

import os
import time
from stego_lib.crypto.cipher import MessageCipher
from stego_lib.crypto.hash import create_message_hash
from stego_lib.formats.header import StegoHeader
from stego_lib.io.directory_handler import get_png_images
from stego_lib.io.image_handler import ImageContainer
from stego_lib.core.decoder import StegoDecoder
from stego_lib.utils.debug import log_debug, time_it


class StegoEncoder:
    """Codificador para ocultar mensajes en imágenes."""

    def __init__(self, password=None, bits_per_channel=2):
        """
        Inicializa el codificador.

        Args:
            password: Contraseña para cifrar los datos (opcional)
            bits_per_channel: Número de bits a modificar por canal (1-4)
        """
        self.bits_per_channel = bits_per_channel
        self.cipher = MessageCipher(password) if password else None
        self.container = ImageContainer(bits_per_channel=bits_per_channel)

    @time_it
    def encode(self, message, directory):
        """
        Oculta un mensaje en un directorio de imágenes PNG sin sobrescribir mensajes anteriores.
        """
        log_debug(f"Iniciando codificación en directorio: {directory}")

        # Obtener imágenes PNG del directorio
        image_paths = get_png_images(directory)
        if not image_paths:
            log_debug("Error: No se encontraron imágenes PNG en el directorio.")
            raise ValueError("No se encontraron imágenes PNG en el directorio.")

        log_debug(f"Encontradas {len(image_paths)} imágenes PNG")

        # Asegurar que el mensaje esté en bytes
        if isinstance(message, str):
            message = message.encode('utf-8')

        log_debug(f"Tamaño del mensaje a ocultar: {len(message)} bytes")

        # Verificar que hay espacio suficiente
        log_debug("Calculando capacidad disponible en las imágenes...")
        total_capacity, individual_capacities, space_info = self.container.calculate_batch_capacity(image_paths)

        # Calcular el espacio realmente disponible
        total_available = sum(available for _, available, _ in space_info.values())
        log_debug(
            f"Espacio total disponible: {total_available} bytes ({total_available / 1024:.2f} KB, {total_available / (1024 * 1024):.3f} MB)")

        # Mostrar información detallada de cada imagen
        for img_path, (used, available, capacity) in space_info.items():
            percent_used = (used / capacity * 100) if capacity > 0 else 0
            log_debug(f"  - {os.path.basename(img_path)}: Capacidad: {capacity} bytes | "
                      f"Usado: {used} bytes ({percent_used:.1f}%) | "
                      f"Disponible: {available} bytes")

        if len(message) > total_available:
            log_debug(f"Error: Mensaje demasiado grande para la capacidad disponible")
            raise ValueError(
                f"El mensaje es demasiado grande ({len(message)} bytes) para la capacidad disponible ({total_available} bytes)")

        # Generar hash y cifrar mensaje
        message_hash = create_message_hash(message)
        if self.cipher:
            message = self.cipher.encrypt(message)

        # Generar un ID único para el mensaje
        message_id = int(time.time())  # Usar timestamp como ID único

        # Ordenar imágenes por espacio disponible (de mayor a menor)
        sorted_images = sorted(
            [(img_path, space_info[img_path][1]) for img_path in image_paths if space_info[img_path][1] > 0],
            key=lambda x: x[1],
            reverse=True
        )

        # Dividir y almacenar el mensaje en las imágenes
        bytes_written = 0
        bytes_remaining = len(message)
        modified_images = []

        log_debug(f"Iniciando escritura de {bytes_remaining} bytes en imágenes...")

        for img_path, available in sorted_images:
            if bytes_remaining <= 0:
                break

            if available <= 0:
                log_debug(f"Saltando imagen {os.path.basename(img_path)}: sin espacio disponible")
                continue

            log_debug(
                f"Imagen: {os.path.basename(img_path)}, espacio disponible: {available} bytes")

            # Determinar cuánto escribir en esta imagen
            bytes_to_write = min(available - StegoHeader.SIZE, bytes_remaining)
            if bytes_to_write <= 0:
                continue

            # Crear encabezado y escribir datos
            header = StegoHeader.create(
                total_message_length=len(message),
                current_offset=bytes_written,
                message_hash=message_hash,
                message_id=message_id
            )

            # Extraer parte del mensaje y escribir
            message_part = message[bytes_written:bytes_written + bytes_to_write]
            self.container.write_data(img_path, img_path, header + message_part)

            modified_images.append(img_path)
            bytes_written += bytes_to_write
            bytes_remaining -= bytes_to_write

            progress = (bytes_written / len(message)) * 100
            log_debug(f"Progreso: {bytes_written}/{len(message)} bytes ({progress:.1f}%)")

        log_debug(f"Codificación completa: {bytes_written} bytes escritos en {len(modified_images)} imágenes")
        return modified_images