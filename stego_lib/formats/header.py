"""
Definición del formato de encabezado para esteganografía.
"""
import struct
from dataclasses import dataclass


@dataclass
class StegoHeader:
    """Encabezado para los datos ocultos en imágenes."""

    # Tamaño total del encabezado en bytes
    SIZE = 36
    # Firma para identificar archivos estego
    MAGIC = b'STEG'

    # Versión actual del formato
    VERSION = 1

    # Campos del encabezado
    total_length: int  # Longitud total del mensaje en bytes
    current_offset: int  # Posición actual en el mensaje
    message_hash: bytes  # Hash para verificación
    message_id: int  # ID único del mensaje

    @classmethod
    def create(cls, total_message_length, current_offset, message_hash, message_id):
        """
        Crea un nuevo encabezado y lo serializa.

        Args:
            total_message_length: Longitud total del mensaje
            current_offset: Posición actual en el mensaje
            message_hash: Hash del mensaje completo
            message_id: ID único del mensaje

        Returns:
            bytes: Encabezado serializado
        """
        header = bytearray(cls.SIZE)

        # Firma de 4 bytes
        header[0:4] = cls.MAGIC

        # Versión (1 byte)
        header[4] = cls.VERSION

        # Longitud total (8 bytes)
        struct.pack_into('>Q', header, 5, total_message_length)

        # Offset actual (8 bytes)
        struct.pack_into('>Q', header, 13, current_offset)

        # Hash (8 bytes, truncado del hash original)
        header[21:29] = message_hash[:8]

        # ID del mensaje (4 bytes)
        struct.pack_into('>I', header, 29, message_id)

        return bytes(header)

    @classmethod
    def parse(cls, header_bytes):
        """
        Analiza un encabezado serializado.

        Args:
            header_bytes: Bytes del encabezado (36 bytes)

        Returns:
            StegoHeader: Objeto con la información del encabezado

        Raises:
            ValueError: Si el encabezado es inválido
        """
        if len(header_bytes) != cls.SIZE:
            raise ValueError(f"El encabezado debe tener {cls.SIZE} bytes")

        # Verificar firma
        if header_bytes[0:4] != cls.MAGIC:
            raise ValueError("Firma de encabezado inválida")

        # Verificar versión
        version = header_bytes[4]
        if version != cls.VERSION:
            raise ValueError(f"Versión no soportada: {version}")

        # Extraer datos
        total_length = struct.unpack('>Q', header_bytes[5:13])[0]
        current_offset = struct.unpack('>Q', header_bytes[13:21])[0]
        message_hash = header_bytes[21:29]
        message_id = struct.unpack('>I', header_bytes[29:33])[0]

        return cls(
            total_length=total_length,
            current_offset=current_offset,
            message_hash=message_hash,
            message_id=message_id
        )