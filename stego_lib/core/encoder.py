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
        Oculta un mensaje en un directorio de imágenes PNG.

        Args:
            message: Mensaje a ocultar (bytes o str).
            directory: Directorio que contiene las imágenes PNG.

        Returns:
            list: Rutas a las imágenes modificadas con el mensaje oculto.
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
            log_debug(f"Convirtiendo mensaje a bytes (tamaño original: {len(message)} caracteres)")
            message = message.encode('utf-8')

        log_debug(f"Tamaño del mensaje a ocultar: {len(message)} bytes")

        # Leer mensajes existentes
        existing_message = b""
        decoder = StegoDecoder(password=self.cipher.password, bits_per_channel=self.bits_per_channel)
        try:
            log_debug("Intentando leer mensajes existentes...")
            start_time = time.time()
            existing_message = decoder.decode(image_paths)
            decode_time = time.time() - start_time
            log_debug(f"Mensaje existente encontrado: {len(existing_message)} bytes (en {decode_time:.4f} segundos)")
        except Exception as e:
            log_debug(f"No se encontraron mensajes existentes: {str(e)}")
            pass

        # Concatenar el mensaje nuevo con los existentes
        combined_message = existing_message + b"\n" + message if existing_message else message
        log_debug(f"Tamaño del mensaje combinado: {len(combined_message)} bytes")

        # Verificar que hay espacio suficiente
        log_debug("Calculando capacidad disponible en las imágenes...")
        total_capacity, individual_capacities = self.container.calculate_batch_capacity(image_paths)
        log_debug(f"Capacidad total disponible: {total_capacity} bytes ({total_capacity / 1024:.2f} KB)")

        for img_path, capacity in individual_capacities.items():
            log_debug(f"  - {os.path.basename(img_path)}: {capacity} bytes ({capacity / 1024:.2f} KB)")

        if len(combined_message) > total_capacity:
            log_debug(f"Error: Mensaje demasiado grande para la capacidad disponible")
            raise ValueError(
                f"El mensaje combinado es demasiado grande ({len(combined_message)} bytes) para las imágenes proporcionadas (capacidad: {total_capacity} bytes)")

        # Generar hash del mensaje combinado
        log_debug("Generando hash del mensaje...")
        start_time = time.time()
        message_hash = create_message_hash(combined_message)
        hash_time = time.time() - start_time
        log_debug(f"Hash generado en {hash_time:.4f} segundos")

        # Cifrar el mensaje combinado si se proporcionó contraseña
        if self.cipher:
            log_debug("Cifrando mensaje...")
            start_time = time.time()
            combined_message = self.cipher.encrypt(combined_message)
            encrypt_time = time.time() - start_time
            log_debug(f"Mensaje cifrado: {len(combined_message)} bytes (en {encrypt_time:.4f} segundos)")

        # Dividir y almacenar el mensaje combinado en las imágenes
        bytes_written = 0
        bytes_remaining = len(combined_message)
        modified_images = []

        log_debug(f"Iniciando escritura de {bytes_remaining} bytes en imágenes...")

        for i, img_path in enumerate(image_paths):
            if bytes_remaining <= 0:
                log_debug(f"Escritura completa. No quedan bytes por escribir.")
                break

            # Calcular cuántos bytes caben en esta imagen
            capacity = self.container.calculate_capacity(img_path)
            log_debug(f"Imagen {i + 1}/{len(image_paths)}: {os.path.basename(img_path)}, capacidad: {capacity} bytes")

            # Determinar cuánto vamos a escribir en esta imagen
            bytes_to_write = min(capacity, bytes_remaining)

            if bytes_to_write <= 0:
                log_debug(f"Omitiendo {os.path.basename(img_path)}: no hay espacio suficiente")
                continue

            # Crear encabezado para esta imagen
            has_next = bytes_written + bytes_to_write < len(combined_message)
            log_debug(f"Creando encabezado: offset={bytes_written}, "
                      f"has_next_part={has_next}, bytes_to_write={bytes_to_write}")

            header = StegoHeader.create(
                total_message_length=len(combined_message),
                current_offset=bytes_written,
                message_hash=message_hash,
                has_next_part=has_next
            )

            # Extraer la parte correspondiente del mensaje
            message_part = combined_message[bytes_written:bytes_written + bytes_to_write]

            # Escribir en la imagen original (sobrescribir)
            log_debug(f"Escribiendo {bytes_to_write} bytes en {os.path.basename(img_path)}...")
            start_time = time.time()
            self.container.write_data(
                img_path,
                img_path,  # Sobrescribe la imagen original
                header + message_part
            )
            write_time = time.time() - start_time
            log_debug(f"Escritura completada en {write_time:.4f} segundos")

            modified_images.append(img_path)
            bytes_written += bytes_to_write
            bytes_remaining -= bytes_to_write

            progress = (bytes_written / len(combined_message)) * 100
            log_debug(f"Progreso: {bytes_written}/{len(combined_message)} bytes ({progress:.1f}%)")

        log_debug(f"Codificación completa: {bytes_written} bytes escritos en {len(modified_images)} imágenes")
        return modified_images