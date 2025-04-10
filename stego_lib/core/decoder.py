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
        Extrae múltiples mensajes ocultos de una serie de imágenes.

        Args:
            image_paths: Lista de rutas a imágenes con los mensajes ocultos

        Returns:
            list: Lista de mensajes extraídos
        """
        log_debug(f"Iniciando decodificación de {len(image_paths)} imágenes")

        # Diccionario para agrupar partes de mensajes por ID
        messages = {}

        # Almacenar IDs de mensajes ya completados para evitar procesarlos nuevamente
        completed_messages = set()

        for i, img_path in enumerate(image_paths):
            log_debug(f"Procesando imagen {i + 1}/{len(image_paths)}: {os.path.basename(img_path)}")

            try:
                # Leer todos los mensajes y fragmentos de esta imagen
                raw_messages = self.container.read_all_messages(img_path)
                log_debug(f"Encontrados {len(raw_messages)} segmentos de mensajes en {os.path.basename(img_path)}")

                for raw_data in raw_messages:
                    if not raw_data or len(raw_data) < StegoHeader.SIZE:
                        continue

                    try:
                        # Extraer y validar el encabezado
                        header = StegoHeader.parse(raw_data[:StegoHeader.SIZE])

                        # Si este mensaje ya está completo, ignorarlo
                        if header.message_id in completed_messages:
                            continue

                        log_debug(f"Encabezado extraído: longitud={header.total_length}, "
                                  f"offset={header.current_offset}, id={header.message_id}")

                        # Inicializar almacenamiento para el mensaje si es necesario
                        if header.message_id not in messages:
                            messages[header.message_id] = {
                                "total_length": header.total_length,
                                "message_hash": header.message_hash,
                                "parts": bytearray(header.total_length),
                                "bytes_read": 0
                            }

                        # Verificar consistencia del mensaje
                        message_info = messages[header.message_id]
                        if header.total_length != message_info["total_length"]:
                            log_debug(
                                f"Error de consistencia: longitud total inconsistente para id={header.message_id}")
                            continue

                        # Extraer los datos del mensaje (sin el encabezado)
                        part_length = min(len(raw_data) - StegoHeader.SIZE, header.total_length - header.current_offset)
                        message_part = raw_data[StegoHeader.SIZE:StegoHeader.SIZE + part_length]
                        message_info["parts"][header.current_offset:header.current_offset + part_length] = message_part
                        message_info["bytes_read"] += len(message_part)

                        log_debug(
                            f"Progreso para id={header.message_id}: {message_info['bytes_read']}/{message_info['total_length']} bytes")

                        # Si el mensaje está completo, marcarlo
                        if message_info["bytes_read"] >= message_info["total_length"]:
                            log_debug(f"Mensaje id={header.message_id} completado")
                            completed_messages.add(header.message_id)

                    except Exception as e:
                        log_debug(f"Error al procesar segmento: {str(e)}")
            except Exception as e:
                log_debug(f"Error al procesar imagen {os.path.basename(img_path)}: {str(e)}")

        # Reconstruir y validar los mensajes
        decoded_messages = []
        for message_id, message_info in messages.items():
            # Solo procesar mensajes completos
            if message_info["bytes_read"] == message_info["total_length"]:
                encrypted_message = bytes(message_info["parts"])
                log_debug(f"Mensaje id={message_id} recopilado: {len(encrypted_message)} bytes")

                # Descifrar si es necesario
                if self.cipher:
                    log_debug(f"Descifrando mensaje id={message_id}...")
                    try:
                        decrypted_message = self.cipher.decrypt(encrypted_message)
                    except Exception as e:
                        log_debug(f"Error al descifrar mensaje id={message_id}: {str(e)}")
                        continue
                else:
                    decrypted_message = encrypted_message

                # Verificar el hash
                log_debug(f"Verificando integridad del mensaje id={message_id}...")
                if verify_message_hash(decrypted_message, message_info["message_hash"]):
                    log_debug(f"Hash verificado correctamente para id={message_id}")
                    decoded_messages.append(decrypted_message)
                else:
                    log_debug(f"Error: El hash del mensaje id={message_id} no coincide")
            else:
                log_debug(
                    f"Mensaje id={message_id} incompleto: {message_info['bytes_read']}/{message_info['total_length']} bytes")

        log_debug(f"Decodificación completada con éxito: {len(decoded_messages)} mensajes recuperados")
        return decoded_messages