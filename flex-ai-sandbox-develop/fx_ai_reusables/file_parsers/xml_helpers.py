import os
import xml.etree.ElementTree as ElementTree
import logging

class XmlHelpers:
    """Xml helpers for any/all projects, not 'my' projects."""


    @staticmethod
    def combine_xmls(xmls : dict[str, ElementTree]) -> str:
        """Convert a dict of (string,xml-ElementTree) objects into single xml string """


        # Create a new root to hold all elements
        combined_root = ElementTree.Element("super_root")

        # Append each tree's root to the new root
        for elem in xmls.values():
            combined_root.append(elem.getroot())

        # Convert to a single XML string
        combined_xml = ElementTree.tostring(combined_root, encoding='unicode')

        return combined_xml

    @staticmethod
    def load_xmls(folder_path : str, pattern : str, endsWith : str) -> dict[str, ElementTree]:
        """Search a folder for xml files and return a dict of (string,xml-ElementTree) objects"""

        files : list[str] = [f for f in os.listdir(folder_path) if pattern in f and f.endswith(endsWith)]

        # Load all Xml files
        xmlTrees: dict[str, ElementTree] = {}

        for filename in files:

            file_path = os.path.join(folder_path, filename)
            try:
                tree = ElementTree.parse(file_path)
                xmlTrees[filename] = tree
                root = tree.getroot()
                logging.info(f"{filename}: Root tag is '{root.tag}'")
            except ElementTree.ParseError as e:
                logging.error(f"{filename}: Failed to parse XML - {e}")



        # Now `schemas` is a dictionary with filenames as keys and XMLSchema objects as values
        return xmlTrees


