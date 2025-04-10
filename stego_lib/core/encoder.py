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
        Oculta un mensaje en un directorio de imágenes PNG.
        Llena una imagen completamente antes de pasar a la siguiente.
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

        # Mostrar información detallada de cada imagen
        for img_path, (used, available, capacity) in space_info.items():
            percent_used = (used / capacity * 100) if capacity > 0 else 0
            log_debug(f"  - {os.path.basename(img_path)}: Capacidad: {capacity} bytes | "
                      f"Usado: {used} bytes ({percent_used:.1f}%) | "
                      f"Disponible: {available} bytes")

        # Ordenar imágenes por espacio USADO (de mayor a menor)
        # Esto hace que se llene primero una imagen antes de pasar a la siguiente
        sorted_images = sorted(
            [(img_path, space_info[img_path][1]) for img_path in image_paths if space_info[img_path][1] > 0],
            key=lambda x: space_info[x[0]][0],  # Ordenar por bytes usados (columna 0 de space_info)
            reverse=True  # Imágenes más llenas primero
        )

        if not sorted_images or sum(available for _, available in sorted_images) < len(message):
            log_debug(f"Error: No hay suficiente espacio disponible para el mensaje")
            raise ValueError(
                f"El mensaje es demasiado grande ({len(message)} bytes) para la capacidad disponible")

        # Generar hash y cifrar mensaje
        message_hash = create_message_hash(message)
        if self.cipher:
            message = self.cipher.encrypt(message)

        # Generar un ID único para el mensaje
        message_id = int(time.time())  # Usar timestamp como ID único

        # Mantener seguimiento del offset actual en el mensaje
        current_offset = 0
        remaining_message = message
        modified_images = []

        for img_path, available in sorted_images:
            if available <= StegoHeader.SIZE:
                continue

            # Comprobar cuántos bytes del mensaje podemos escribir en esta imagen
            bytes_to_write = min(available - StegoHeader.SIZE, len(remaining_message))

            # Crear encabezado con el offset correcto
            header = StegoHeader.create(
                total_message_length=len(message),  # Longitud total del mensaje original
                current_offset=current_offset,  # Posición actual dentro del mensaje
                message_hash=message_hash,
                message_id=message_id  # Mantener el mismo ID para todos los fragmentos
            )

            # Escribir fragmento en la imagen
            self.container.write_data(img_path, img_path, header + remaining_message[:bytes_to_write])
            modified_images.append(img_path)

            log_debug(
                f"Fragmento escrito en {os.path.basename(img_path)}: {bytes_to_write} bytes (offset={current_offset})")

            # Actualizar offset y mensaje restante
            current_offset += bytes_to_write
            remaining_message = remaining_message[bytes_to_write:]

            # Si el mensaje está completo, terminamos
            if len(remaining_message) == 0:
                log_debug(f"Mensaje completo almacenado en {len(modified_images)} imágenes")
                break

            log_debug(f"Continúa en la siguiente imagen: {len(remaining_message)} bytes restantes")

        log_debug(f"Codificación completa: mensaje escrito en {len(modified_images)} imágenes")
        return modified_images