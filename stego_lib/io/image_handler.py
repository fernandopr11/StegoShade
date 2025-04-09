"""
Manejo de imágenes para esteganografía.
"""

import numpy as np
from PIL import Image
from stego_lib.formats.header import StegoHeader
from stego_lib.utils.debug import log_debug, time_it


class ImageContainer:
    """Gestiona la lectura y escritura de datos en imágenes."""

    def __init__(self, bits_per_channel=2):
        """
        Inicializa el contenedor de imágenes.

        Args:
            bits_per_channel: Número de bits a modificar por canal (1-4)
        """
        if not 1 <= bits_per_channel <= 4:
            raise ValueError("El número de bits por canal debe estar entre 1 y 4")

        self.bits_per_channel = bits_per_channel
        self.mask = (1 << bits_per_channel) - 1
        self.inverse_mask = 0xFF & ~self.mask

    def calculate_capacity(self, image_path):
        """
        Calcula cuántos bytes se pueden ocultar en una imagen.

        Args:
            image_path: Ruta a la imagen

        Returns:
            int: Capacidad en bytes
        """
        try:
            img = Image.open(image_path)
            width, height = img.size

            # Total de píxeles disponibles
            total_pixels = width * height

            # Bits disponibles (3 canales × bits por canal)
            available_bits = total_pixels * 3 * self.bits_per_channel

            # Convertir a bytes
            available_bytes = available_bits // 8

            # Restar el tamaño del encabezado
            available_bytes -= StegoHeader.SIZE

            return max(0, available_bytes)
        except Exception as e:
            raise IOError(f"Error al calcular la capacidad de {image_path}: {e}")

    @time_it
    def calculate_batch_capacity(self, image_paths):
        """
        Calcula la capacidad total, usada y restante de un conjunto de imágenes.

        Args:
            image_paths: Lista de rutas a imágenes PNG

        Returns:
            tuple: (capacidad_total, capacidades_individuales, info_espacio)
                   donde info_espacio contiene (usado, disponible, total) para cada imagen
        """
        total_capacity = 0
        individual_capacities = {}
        space_info = {}  # Nuevo diccionario para almacenar información de espacio

        log_debug(f"Calculando capacidad para {len(image_paths)} imágenes")

        for path in image_paths:
            capacity = self.calculate_capacity(path)
            individual_capacities[path] = capacity
            total_capacity += capacity

            # Calcular espacio usado y disponible
            try:
                # Intentar leer datos existentes para verificar si hay un mensaje
                raw_data = self.read_data(path)
                bytes_used = 0
                bytes_available = capacity

                if raw_data and len(raw_data) >= StegoHeader.SIZE:
                    try:
                        # Extraer el encabezado
                        header = StegoHeader.parse(raw_data[:StegoHeader.SIZE])

                        # Si el mensaje continúa en otras imágenes, todo el espacio está usado
                        if header.has_next_part:
                            bytes_used = capacity
                            bytes_available = 0
                        else:
                            # Calcular parte del mensaje en esta imagen
                            part_length = min(
                                len(raw_data) - StegoHeader.SIZE,
                                header.total_length - header.current_offset
                            )
                            bytes_used = part_length + StegoHeader.SIZE
                            bytes_available = capacity - bytes_used
                    except Exception:
                        # Si no se puede extraer el encabezado, asumimos que no hay datos
                        pass

                # Guardar la información de espacio
                space_info[path] = (bytes_used, bytes_available, capacity)

                # Log detallado con información de uso
                percent_used = (bytes_used / capacity * 100) if capacity > 0 else 0
                log_debug(f"  - {path}: {capacity} bytes ({capacity / 1024:.2f} KB) | "
                          f"Usado: {bytes_used} bytes ({percent_used:.1f}%) | "
                          f"Disponible: {bytes_available} bytes")

            except Exception as e:
                log_debug(f"  - {path}: Error al analizar espacio: {e}")
                space_info[path] = (0, capacity, capacity)  # En caso de error, asumimos vacía

        log_debug(f"Capacidad total: {total_capacity} bytes ({total_capacity / 1024:.2f} KB)")

        # Calcular totales de espacio usado/disponible
        total_used = sum(used for used, _, _ in space_info.values())
        total_available = sum(available for _, available, _ in space_info.values())

        percent_used_total = (total_used / total_capacity * 100) if total_capacity > 0 else 0
        log_debug(f"Espacio total usado: {total_used} bytes ({total_used / 1024:.2f} KB) - {percent_used_total:.1f}%")
        log_debug(f"Espacio total disponible: {total_available} bytes ({total_available / 1024:.2f} KB)")

        return total_capacity, individual_capacities, space_info

    def write_data(self, input_path, output_path, data):
        """
        Escribe datos en una imagen utilizando esteganografía.

        Args:
            input_path: Ruta de la imagen original
            output_path: Ruta donde guardar la imagen con datos ocultos
            data: Bytes a ocultar

        Returns:
            bool: True si la operación fue exitosa
        """
        try:
            # Cargar la imagen
            img = Image.open(input_path).convert('RGB')
            width, height = img.size

            # Convertir a numpy array para procesar más rápido
            pixels = np.array(img)
            pixels_flat = pixels.reshape(-1)

            # Verificar que hay espacio suficiente
            max_bytes = (len(pixels_flat) * self.bits_per_channel) // 8
            if len(data) > max_bytes:
                raise ValueError(f"No hay suficiente espacio en la imagen para {len(data)} bytes")

            # Convertir los datos a bits
            bits = []
            for byte in data:
                for i in range(7, -1, -1):
                    bits.append((byte >> i) & 1)

            # Rellenar con ceros si es necesario para completar un byte
            if len(bits) % self.bits_per_channel != 0:
                bits.extend([0] * (self.bits_per_channel - (len(bits) % self.bits_per_channel)))

            # Modificar los últimos bits de cada componente de color
            bit_index = 0
            for i in range(len(pixels_flat)):
                if bit_index >= len(bits):
                    break

                # Limpiar los bits que vamos a modificar
                pixels_flat[i] = pixels_flat[i] & self.inverse_mask

                # Escribir los nuevos bits
                bits_to_write = min(self.bits_per_channel, len(bits) - bit_index)
                for j in range(bits_to_write):
                    pixels_flat[i] |= (bits[bit_index] << j)
                    bit_index += 1
                    if bit_index >= len(bits):
                        break

            # Reconstruir la imagen
            stego_img = Image.fromarray(pixels.reshape(height, width, 3))

            # Guardar la imagen resultante
            stego_img.save(output_path, quality=100)

            return True
        except Exception as e:
            raise IOError(f"Error al escribir datos en {input_path}: {e}")

    def read_data(self, image_path):
        """
        Lee datos ocultos en una imagen.
        """
        try:
            # Cargar la imagen
            img = Image.open(image_path).convert('RGB')

            # Convertir a numpy array
            pixels = np.array(img)
            pixels_flat = pixels.reshape(-1)

            # Extraer todos los bits ocultos de una vez
            extracted_bits = []
            for pixel_value in pixels_flat:
                for j in range(self.bits_per_channel):
                    extracted_bits.append((pixel_value >> j) & 1)

            # Convertir los bits a bytes
            data = bytearray()
            for i in range(0, len(extracted_bits), 8):
                if i + 8 > len(extracted_bits):
                    break
                byte = 0
                for j in range(8):
                    byte = (byte << 1) | extracted_bits[i + j]
                data.append(byte)

            return bytes(data)
        except Exception as e:
            raise IOError(f"Error al leer datos de {image_path}: {e}")
