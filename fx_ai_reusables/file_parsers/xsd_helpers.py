import os
import xmlschema
import logging

from xmlschema import XMLSchema10


class XsdHelpers:
    """Xsd helpers for any/all projects, not 'my' projects."""

    @staticmethod
    def loadXsds(folder_path : str, pattern : str) -> dict[str, XMLSchema10]:

        # Path to the folder containing XSD files

        files = [f for f in os.listdir(folder_path) if pattern in f and f.endswith(".xsd")]

        # Load all XSD files
        schemas: dict[str, XMLSchema10] = {}


        for filename in files:
            file_path = os.path.join(folder_path, filename)
            try:
                schema = xmlschema.XMLSchema(file_path)
                schemas[filename] = schema
                logging.info(f"Loaded Xsd File: {filename}")
            except xmlschema.XMLSchemaException as e:
                logging.error(f"Failed to load {filename}: {e}")

        # Now `schemas` is a dictionary with filenames as keys and XMLSchema objects as values
        return schemas