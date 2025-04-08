import os

def get_png_images(directory):
    """
    Obtiene una lista de imágenes PNG en un directorio, ordenadas por nombre.

    Args:
        directory: Ruta al directorio.

    Returns:
        list: Lista de rutas a imágenes PNG ordenadas.
    """
    images = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.png')]
    return sorted(images)