"""
Módulo para gestionar locks de lectores/escritores para imágenes.
"""
from readerwriterlock import rwlock
import os


class ImageLockManager:
    """Gestiona locks tipo reader-writer para imágenes."""

    def __init__(self):
        """Inicializa el gestor de locks."""
        self._locks = {}  # Diccionario que mapea rutas de imagen a locks

    def get_lock(self, image_path):
        """
        Obtiene o crea un lock para una imagen específica.

        Args:
            image_path: Ruta absoluta de la imagen

        Returns:
            rwlock.RWLockFair: Lock para la imagen especificada
        """
        # Normalizar la ruta para evitar problemas con diferentes formatos
        abs_path = os.path.abspath(image_path)

        # Crear lock si no existe
        if abs_path not in self._locks:
            self._locks[abs_path] = rwlock.RWLockFair()

        return self._locks[abs_path]

    def acquire_read_lock(self, image_path):
        """
        Adquiere un lock de lectura para la imagen.

        Args:
            image_path: Ruta de la imagen

        Returns:
            objeto context manager para el lock de lectura
        """
        lock = self.get_lock(image_path)
        return lock.gen_rlock()

    def acquire_write_lock(self, image_path):
        """
        Adquiere un lock de escritura para la imagen.

        Args:
            image_path: Ruta de la imagen

        Returns:
            objeto context manager para el lock de escritura
        """
        lock = self.get_lock(image_path)
        return lock.gen_wlock()