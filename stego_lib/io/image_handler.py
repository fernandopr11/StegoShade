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
        """Calcula la capacidad total de un conjunto de imágenes."""
        total_capacity = 0
        individual_capacities = {}

        log_debug(f"Calculando capacidad para {len(image_paths)} imágenes")

        for path in image_paths:
            capacity = self.calculate_capacity(path)
            individual_capacities[path] = capacity
            total_capacity += capacity
            log_debug(f"  - {path}: {capacity} bytes ({capacity / 1024:.2f} KB)")

        log_debug(f"Capacidad total: {total_capacity} bytes ({total_capacity / 1024:.2f} KB)")
        return total_capacity, individual_capacities

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

        Args:
            image_path: Ruta a la imagen con datos ocultos

        Returns:
            bytes: Datos extraídos
        """
        try:
            # Cargar la imagen
            img = Image.open(image_path).convert('RGB')

            # Convertir a numpy array
            pixels = np.array(img)
            pixels_flat = pixels.reshape(-1)

            # Extraer los bits ocultos
            extracted_bits = []
            for pixel_value in pixels_flat:
                # Extraer los bits menos significativos
                for j in range(self.bits_per_channel):
                    extracted_bits.append((pixel_value >> j) & 1)

                if len(extracted_bits) >= StegoHeader.SIZE * 8:
                    # Ya tenemos suficientes bits para el encabezado
                    break

            # Reconstruir los bytes del encabezado
            header_bytes = bytearray()
            for i in range(0, StegoHeader.SIZE * 8, 8):
                if i + 8 > len(extracted_bits):
                    break
                byte = 0
                for j in range(8):
                    byte = (byte << 1) | extracted_bits[i + j]
                header_bytes.append(byte)

            # Analizar el encabezado
            header = StegoHeader.parse(header_bytes)

            # Determinar cuántos bits más necesitamos para el mensaje completo
            remaining_bits = (header.total_length - header.current_offset) * 8
            total_bits_needed = StegoHeader.SIZE * 8 + remaining_bits

            # Si necesitamos más bits, continuar extrayendo
            extracted_bits = []
            for pixel_value in pixels_flat:
                for j in range(self.bits_per_channel):
                    extracted_bits.append((pixel_value >> j) & 1)

                if len(extracted_bits) >= total_bits_needed:
                    break

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
