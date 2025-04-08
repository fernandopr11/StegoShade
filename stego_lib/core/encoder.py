"""
Módulo para codificar mensajes en imágenes usando esteganografía.
"""

import os
from stego_lib.crypto.cipher import MessageCipher
from stego_lib.crypto.hash import create_message_hash
from stego_lib.formats.header import StegoHeader
from stego_lib.io.image_handler import ImageContainer


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

    def encode(self, message, image_paths):
        """
        Oculta un mensaje en una serie de imágenes.

        Args:
            message: Mensaje a ocultar (bytes o str)
            image_paths: Lista de rutas a imágenes donde ocultar el mensaje

        Returns:
            list: Rutas a las imágenes modificadas con el mensaje oculto
        """
        # Asegurar que el mensaje esté en bytes
        if isinstance(message, str):
            message = message.encode('utf-8')

        # Verificar que hay espacio suficiente
        total_capacity, _ = self.container.calculate_batch_capacity(image_paths)
        if len(message) > total_capacity:
            raise ValueError(
                f"El mensaje es demasiado grande ({len(message)} bytes) para las imágenes proporcionadas (capacidad: {total_capacity} bytes)")

        # Generar hash del mensaje original (para verificación)
        message_hash = create_message_hash(message)

        # Cifrar el mensaje si se proporcionó contraseña
        if self.cipher:
            message = self.cipher.encrypt(message)

        # Dividir y almacenar el mensaje en las imágenes
        bytes_written = 0
        bytes_remaining = len(message)

        for img_path in image_paths:
            if bytes_remaining <= 0:
                break

            # Calcular cuántos bytes caben en esta imagen
            capacity = self.container.calculate_capacity(img_path)

            # Determinar cuánto vamos a escribir en esta imagen
            bytes_to_write = min(capacity, bytes_remaining)

            if bytes_to_write <= 0:
                continue

            # Crear encabezado para esta imagen
            header = StegoHeader.create(
                total_message_length=len(message),
                current_offset=bytes_written,
                message_hash=message_hash,
                has_next_part=(bytes_written + bytes_to_write < len(message))
            )

            # Extraer la parte correspondiente del mensaje
            message_part = message[bytes_written:bytes_written + bytes_to_write]

            # Escribir en la imagen original (sobrescribir)
            self.container.write_data(
                img_path,
                img_path,  # Sobrescribe la imagen original
                header + message_part
            )

            bytes_written += bytes_to_write
            bytes_remaining -= bytes_to_write

        return image_paths

    def _get_output_path(self, original_path):
        """Genera una ruta para la imagen de salida."""
        directory, filename = os.path.split(original_path)
        name, ext = os.path.splitext(filename)
        stego_path = os.path.join(directory, f"{name}_stego{ext}")
        return stego_path
