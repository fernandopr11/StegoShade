"""
Módulo para codificar mensajes en imágenes usando esteganografía.
"""

import os
from stego_lib.crypto.cipher import MessageCipher
from stego_lib.crypto.hash import create_message_hash
from stego_lib.formats.header import StegoHeader
from stego_lib.io.directory_handler import get_png_images
from stego_lib.io.image_handler import ImageContainer
from stego_lib.core.decoder import StegoDecoder


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

    def encode(self, message, directory):
        """
        Oculta un mensaje en un directorio de imágenes PNG.

        Args:
            message: Mensaje a ocultar (bytes o str).
            directory: Directorio que contiene las imágenes PNG.

        Returns:
            list: Rutas a las imágenes modificadas con el mensaje oculto.
        """
        # Obtener imágenes PNG del directorio
        image_paths = get_png_images(directory)
        if not image_paths:
            raise ValueError("No se encontraron imágenes PNG en el directorio.")

        # Asegurar que el mensaje esté en bytes
        if isinstance(message, str):
            message = message.encode('utf-8')

        # Leer mensajes existentes
        existing_message = b""
        decoder = StegoDecoder(password=self.cipher.password, bits_per_channel=self.bits_per_channel)
        try:
            existing_message = decoder.decode(image_paths)
        except Exception:
            pass

        # Concatenar el mensaje nuevo con los existentes
        combined_message = existing_message + b"\n" + message if existing_message else message

        # Verificar que hay espacio suficiente
        total_capacity, _ = self.container.calculate_batch_capacity(image_paths)
        if len(combined_message) > total_capacity:
            raise ValueError(
                f"El mensaje combinado es demasiado grande ({len(combined_message)} bytes) para las imágenes proporcionadas (capacidad: {total_capacity} bytes)")

        # Generar hash del mensaje combinado
        message_hash = create_message_hash(combined_message)

        # Cifrar el mensaje combinado si se proporcionó contraseña
        if self.cipher:
            combined_message = self.cipher.encrypt(combined_message)

        # Dividir y almacenar el mensaje combinado en las imágenes
        bytes_written = 0
        bytes_remaining = len(combined_message)
        modified_images = []

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
                total_message_length=len(combined_message),
                current_offset=bytes_written,
                message_hash=message_hash,
                has_next_part=(bytes_written + bytes_to_write < len(combined_message))
            )

            # Extraer la parte correspondiente del mensaje
            message_part = combined_message[bytes_written:bytes_written + bytes_to_write]

            # Escribir en la imagen original (sobrescribir)
            self.container.write_data(
                img_path,
                img_path,  # Sobrescribe la imagen original
                header + message_part
            )

            modified_images.append(img_path)
            bytes_written += bytes_to_write
            bytes_remaining -= bytes_to_write

        return modified_images

    def _get_output_path(self, original_path):
        """Genera una ruta para la imagen de salida."""
        directory, filename = os.path.split(original_path)
        name, ext = os.path.splitext(filename)
        stego_path = os.path.join(directory, f"{name}_stego{ext}")
        return stego_path
