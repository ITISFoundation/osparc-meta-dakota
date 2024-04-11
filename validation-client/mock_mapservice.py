"""Test client for validation"""

import json
import logging
import os
import pathlib as pl
import time
import uuid

from osparc_filecomms import handshakers

logging.basicConfig(
    level=logging.INFO,
    format="Mock map service: [%(filename)s:%(lineno)d] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Started validation client")

    map_uuid = str(uuid.uuid4())
    map_input_path = pl.Path(os.environ["MOCK_MAP_INPUT_PATH"])
    map_output_path = pl.Path(os.environ["MOCK_MAP_OUTPUT_PATH"])
    input_tasks_path = map_input_path / "input_tasks.json"
    output_tasks_path = map_output_path / "output_tasks.json"

    this_dir = pl.Path(__file__).parent

    handshaker = handshakers.FileHandshaker(
        map_uuid,
        map_input_path,
        map_output_path,
        is_initiator=True,
        verbose_level=logging.DEBUG,
        polling_interval=0.1,
        print_polling_interval=100,
    )
    dak_uuid = handshaker.shake()

    logger.info(f"Handshake done with dakota uuid: {dak_uuid}")
    while not os.path.exists(input_tasks_path):
        time.sleep(0.1)

    input_tasks = json.loads(input_tasks_path.read_text())

    assert input_tasks["map_uuid"] == map_uuid

    logger.info(f"Map received tasks: {input_tasks}")

    output_tasks = input_tasks

    for output_task in output_tasks["tasks"]:
        output_task["status"] = "SUCCESS"
        output_task["output"]["OutputFile1"]["value"] = output_task["input"][
            "InputFile1"
        ]["value"]

    output_tasks_path.write_text(json.dumps(output_tasks))
    # stop_command = {
    #     "caller_uuid": client_uuid,
    #     "map_uuid": map_uuid,
    #     "command": "stop",
    # }
    # input_tasks_path.write_text(json.dumps(stop_command))


if __name__ == "__main__":
    main()
