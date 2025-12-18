import os
import json
import logging

class JsonHelpers:
    """Json helpers for any/all projects, not 'my' projects."""

    @staticmethod
    def stringify_jsons(jsons : list[dict]) -> str:
        """Convert a list of json objects into a single json string"""

        # Convert JSON to a string for the prompt
        returnValue = json.dumps(jsons, indent=2)

        return returnValue

    @staticmethod
    def loadExamplePropietaryJsons(folder_path : str, pattern : str) -> list[dict]:
        """Search a folder for json files and return a list of (json) objects (where the json object is stored as a dict)"""


        files = [f for f in os.listdir(folder_path) if pattern in f and f.endswith(".json")]


        all_data = []

        for filename in files:
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r') as f:
                try:
                    data = json.load(f)
                    all_data.append(data)

                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding {filename}: {e}")

        return all_data


