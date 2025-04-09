"""
Módulo para decodificar mensajes ocultos en imágenes.
"""

from stego_lib.crypto.cipher import MessageCipher
from stego_lib.crypto.hash import verify_message_hash
from stego_lib.formats.header import StegoHeader
from stego_lib.io.image_handler import ImageContainer
import time
from stego_lib.utils.debug import log_debug, time_it
import os


class StegoDecoder:
    """Decodificador para extraer mensajes ocultos en imágenes."""

    def __init__(self, password=None, bits_per_channel=2):
        """
        Inicializa el decodificador.

        Args:
            password: Contraseña para descifrar los datos (opcional)
            bits_per_channel: Número de bits modificados por canal (1-4)
        """
        self.bits_per_channel = bits_per_channel
        self.cipher = MessageCipher(password) if password else None
        self.container = ImageContainer(bits_per_channel=bits_per_channel)

    @time_it
    def decode(self, image_paths):
        """
        Extrae un mensaje oculto de una serie de imágenes.

        Args:
            image_paths: Lista de rutas a imágenes con el mensaje oculto

        Returns:
            bytes: Mensaje extraído
        """
        log_debug(f"Iniciando decodificación de {len(image_paths)} imágenes")

        message_parts = []
        total_length = None
        message_hash = None
        bytes_read = 0

        for i, img_path in enumerate(image_paths):
            log_debug(f"Procesando imagen {i + 1}/{len(image_paths)}: {os.path.basename(img_path)}")

            # Leer datos desde la imagen
            start_time = time.time()
            try:
                raw_data = self.container.read_data(img_path)
                read_time = time.time() - start_time
                log_debug(f"Lectura completada en {read_time:.4f} segundos")

                if not raw_data:
                    log_debug(f"No se encontraron datos en {os.path.basename(img_path)}")
                    continue

                log_debug(f"Leídos {len(raw_data)} bytes de datos")
            except Exception as e:
                log_debug(f"Error al leer datos de {os.path.basename(img_path)}: {str(e)}")
                continue

            # Extraer y validar el encabezado
            try:
                header = StegoHeader.parse(raw_data[:StegoHeader.SIZE])
                log_debug(f"Encabezado extraído: longitud={header.total_length}, "
                          f"offset={header.current_offset}, "
                          f"has_next={header.has_next_part}")
            except Exception as e:
                log_debug(f"Error al procesar encabezado: {str(e)}")
                continue

            # En la primera imagen obtenemos la longitud total y el hash
            if total_length is None:
                total_length = header.total_length
                message_hash = header.message_hash
                log_debug(f"Información del mensaje: tamaño total={total_length} bytes")

            # Verificar que el encabezado sea consistente
            if header.total_length != total_length or header.current_offset != bytes_read:
                log_debug(f"Error de consistencia: offset esperado={bytes_read}, recibido={header.current_offset}")
                raise ValueError(f"El encabezado de la imagen {img_path} es inconsistente con la secuencia esperada")

            # Extraer los datos del mensaje (sin el encabezado)
            part_length = min(len(raw_data) - StegoHeader.SIZE, total_length - bytes_read)
            message_part = raw_data[StegoHeader.SIZE:StegoHeader.SIZE + part_length]

            log_debug(f"Extrayendo {part_length} bytes de datos del mensaje")

            message_parts.append(message_part)
            bytes_read += len(message_part)

            progress = (bytes_read / total_length) * 100 if total_length else 0
            log_debug(f"Progreso: {bytes_read}/{total_length} bytes ({progress:.1f}%)")

            # Si no hay más partes, terminamos
            if not header.has_next_part:
                log_debug("Se alcanzó el final del mensaje")
                break

        # Combinar las partes del mensaje
        encrypted_message = b''.join(message_parts)
        log_debug(f"Mensaje completo recopilado: {len(encrypted_message)} bytes")

        # Descifrar si es necesario
        if self.cipher:
            log_debug("Descifrando mensaje...")
            try:
                start_time = time.time()
                decrypted_message = self.cipher.decrypt(encrypted_message)
                decrypt_time = time.time() - start_time
                log_debug(f"Mensaje descifrado en {decrypt_time:.4f} segundos")
            except Exception as e:
                log_debug(f"Error al descifrar mensaje: {str(e)}")
                raise ValueError(f"Error al descifrar: {e}. La contraseña podría ser incorrecta.")
        else:
            log_debug("No se requiere descifrado (sin contraseña)")
            decrypted_message = encrypted_message

        # Verificar el hash
        log_debug("Verificando integridad del mensaje (hash)...")
        start_time = time.time()
        if verify_message_hash(decrypted_message, message_hash):
            verify_time = time.time() - start_time
            log_debug(f"Hash verificado correctamente en {verify_time:.4f} segundos")
        else:
            log_debug("Error: El hash del mensaje no coincide")
            raise ValueError(
                "El mensaje extraído no coincide con el hash original. Podría estar corrupto o incompleto.")

        log_debug(f"Decodificación completada con éxito: {len(decrypted_message)} bytes recuperados")
        return decrypted_message