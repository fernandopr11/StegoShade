"""
Módulo para decodificar mensajes ocultos en imágenes.
"""

from stego_lib.crypto.cipher import MessageCipher
from stego_lib.crypto.hash import verify_message_hash
from stego_lib.formats.header import StegoHeader
from stego_lib.io.image_handler import ImageContainer


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

    def decode(self, image_paths):
        """
        Extrae un mensaje oculto de una serie de imágenes.

        Args:
            image_paths: Lista de rutas a imágenes con el mensaje oculto

        Returns:
            bytes: Mensaje extraído
        """
        message_parts = []
        total_length = None
        message_hash = None
        bytes_read = 0

        for img_path in image_paths:
            # Leer datos desde la imagen
            raw_data = self.container.read_data(img_path)
            if not raw_data:
                continue

            # Extraer y validar el encabezado
            header = StegoHeader.parse(raw_data[:StegoHeader.SIZE])

            # En la primera imagen obtenemos la longitud total y el hash
            if total_length is None:
                total_length = header.total_length
                message_hash = header.message_hash

            # Verificar que el encabezado sea consistente
            if header.total_length != total_length or header.current_offset != bytes_read:
                raise ValueError(f"El encabezado de la imagen {img_path} es inconsistente con la secuencia esperada")

            # Extraer los datos del mensaje (sin el encabezado)
            part_length = min(len(raw_data) - StegoHeader.SIZE, total_length - bytes_read)
            message_part = raw_data[StegoHeader.SIZE:StegoHeader.SIZE + part_length]

            message_parts.append(message_part)
            bytes_read += len(message_part)

            # Si no hay más partes, terminamos
            if not header.has_next_part:
                break

        # Combinar las partes del mensaje
        encrypted_message = b''.join(message_parts)

        # Descifrar si es necesario
        if self.cipher:
            try:
                decrypted_message = self.cipher.decrypt(encrypted_message)
            except Exception as e:
                raise ValueError(f"Error al descifrar: {e}. La contraseña podría ser incorrecta.")
        else:
            decrypted_message = encrypted_message

        # Verificar el hash
        if not verify_message_hash(decrypted_message, message_hash):
            raise ValueError(
                "El mensaje extraído no coincide con el hash original. Podría estar corrupto o incompleto.")

        return decrypted_message