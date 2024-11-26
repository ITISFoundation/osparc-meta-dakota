import json
import logging

import pydantic as pyda
import pydantic_settings
from osparc_filecomms import tools

import dakota_start

logging.basicConfig(
    level=logging.INFO, format="[%(filename)s:%(lineno)d] %(message)s"
)
logger = logging.getLogger(__name__)

INPUT_CONF_KEY = "input_2"
CONF_SCHEMA_KEY = "conf_json_schema"

DEFAULT_FILE_POLLING_INTERVAL = 0.1
RESTART_ON_ERROR_MAX_TIME = 3600.0
RESTART_ON_ERROR_POLLING_INTERVAL = 1.0


def main():
    """Main"""

    settings = DakotaDynamicSettings()

    # Wait for and read the settings file
    logger.info(
        f"Waiting for settings file to appear at {settings.settings_file_path}"
    )
    settings.read_settings_file()
    logger.info("Settings file was read")

    # Create and start the dakota service
    dakservice = dakota_start.DakotaService(settings)
    dakservice.start()


class DakotaDynamicSettings:
    def __init__(self):
        self._settings = self.DakotaMainSettings()
        conf_json_schema_path = (
            self._settings.output_path / CONF_SCHEMA_KEY / "schema.json"
        )

        settings_schema = self._settings.model_json_schema()

        # Hide some settings from the user
        for field_name in [
            "DY_SIDECAR_PATH_INPUTS",
            "DY_SIDECAR_PATH_OUTPUTS",
        ]:
            settings_schema["properties"].pop(field_name)

        conf_json_schema_path.write_text(json.dumps(settings_schema, indent=2))

        self.settings_file_path = (
            self._settings.input_path / INPUT_CONF_KEY / "settings.json"
        )

    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            self.read_settings_file()
            return getattr(self._settings, name)

    def read_settings_file(self):
        tools.wait_for_path(self.settings_file_path)
        self._settings = self._settings.parse_file(self.settings_file_path)

    class DakotaMainSettings(pydantic_settings.BaseSettings):
        batch_mode: bool = pyda.Field(default=False)
        file_polling_interval: float = pyda.Field(
            default=DEFAULT_FILE_POLLING_INTERVAL
        )
        input_path: pyda.DirectoryPath = pyda.Field(
            alias="DY_SIDECAR_PATH_INPUTS"
        )
        output_path: pyda.DirectoryPath = pyda.Field(
            alias="DY_SIDECAR_PATH_OUTPUTS"
        )
        restart_on_error: bool = pyda.Field(default=False)
        restart_on_error_max_time: float = pyda.Field(
            default=RESTART_ON_ERROR_MAX_TIME, ge=0
        )
        restart_on_error_polling_interval: float = pyda.Field(
            default=RESTART_ON_ERROR_POLLING_INTERVAL, ge=0
        )


if __name__ == "__main__":
    main()
