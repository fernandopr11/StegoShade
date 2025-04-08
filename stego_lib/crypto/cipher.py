"""
Módulo para el cifrado y descifrado de mensajes.
"""

import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


class MessageCipher:
    """Clase para cifrar y descifrar mensajes usando AES."""

    def __init__(self, password):
        """
        Inicializa el sistema de cifrado con una contraseña.

        Args:
            password: Contraseña para generar la clave de cifrado
        """
        self.password = password
        self._key, self._iv = self._derive_key_iv(password)

    def _derive_key_iv(self, password):
        """
        Deriva una clave y un vector de inicialización a partir de la contraseña.

        Args:
            password: Contraseña de usuario

        Returns:
            tuple: (key, iv) para uso en AES
        """
        if not password:
            return None, None

        # Convertir la contraseña a bytes si es una cadena
        if isinstance(password, str):
            password = password.encode('utf-8')

        # Generar clave y vector de inicialización usando PBKDF2
        salt = b'steganography_salt'  # En producción usar un salt aleatorio
        key = hashlib.pbkdf2_hmac('sha256', password, salt, 100000, 32)
        iv = hashlib.pbkdf2_hmac('sha256', password, salt + b'iv', 100000, 16)

        return key, iv

    def encrypt(self, plaintext):
        """
        Cifra un mensaje usando AES-256 en modo CBC.

        Args:
            plaintext: Mensaje a cifrar (bytes)

        Returns:
            bytes: Mensaje cifrado
        """
        # Aplicar padding PKCS7
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()

        # Cifrar con AES-256
        cipher = Cipher(algorithms.AES(self._key), modes.CBC(self._iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        return encrypted_data

    def decrypt(self, ciphertext):
        """
        Descifra un mensaje cifrado con AES-256 en modo CBC.

        Args:
            ciphertext: Mensaje cifrado (bytes)

        Returns:
            bytes: Mensaje original
        """
        # Descifrar con AES-256
        cipher = Cipher(algorithms.AES(self._key), modes.CBC(self._iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # Quitar el padding PKCS7
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()

        return data