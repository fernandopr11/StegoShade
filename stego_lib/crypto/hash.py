"""
Hash functions for integrity verification.
"""
import hashlib

def create_message_hash(message):
    """
    Crea un hash SHA-256 del mensaje.
    Args:
        message: Mensaje a hashear (bytes)
    Returns:
        bytes: Hash SHA-256 del mensaje
    """
    return hashlib.sha256(message).digest()


def verify_message_hash(message, expected_hash):
    """
    Verifica que el hash del mensaje coincida con el esperado.
    Args:
        message: Mensaje a verificar
        expected_hash: Hash esperado (primeros bytes del SHA-256)
    Returns:
        bool: True si el hash coincide
    """
    actual_hash = create_message_hash(message)
    return actual_hash[:len(expected_hash)] == expected_hash