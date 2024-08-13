"""Test client for validation"""

import logging
import os
import pathlib as pl
import shutil
import string
import time
import uuid

import pandas
from osparc_filecomms import handshakers

logging.basicConfig(
    level=logging.INFO,
    format="Validation client: [%(filename)s:%(lineno)d] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Started validation client")

    client_uuid = str(uuid.uuid4())
    client_input_path = pl.Path(os.environ["VALIDATION_CLIENT_INPUT_PATH"])
    client_output_path = pl.Path(os.environ["VALIDATION_CLIENT_OUTPUT_PATH"])
    use_rst = os.environ["VALIDATION_CLIENT_RST"] in ["1"]
    dak_opt_path = client_input_path / "opt.dat"

    this_dir = pl.Path(__file__).parent
    expected_dak_opt_path = this_dir.parent / "validation" / "opt.dat.expected"

    handshaker = handshakers.FileHandshaker(
        client_uuid,
        client_input_path,
        client_output_path,
        is_initiator=False,
        verbose_level=logging.DEBUG,
        polling_interval=0.1,
        print_polling_interval=100,
    )
    dakota_uuid = handshaker.shake()
    logger.info(f"Handshake done, dakota service uuid: {dakota_uuid}")

    if use_rst:
        dakota_rst_path = this_dir / "dakota.rst"
        shutil.copyfile(dakota_rst_path, client_output_path / "dakota.rst")
        model_string = '"dummy_model"'
    else:
        model_string = '"model"'

    dakota_in_template_path = this_dir / "dakota.in.template"

    dakota_in_template = string.Template(dakota_in_template_path.read_text())
    dakota_in_path = client_output_path / "dakota.in"

    dakota_in_path.write_text(
        dakota_in_template.substitute(model=model_string)
    )

    while not os.path.exists(dak_opt_path):
        logger.info(f"Waiting for dak.opt at {dak_opt_path}")
        time.sleep(0.1)

    while len(pandas.read_csv(dak_opt_path).index) == 0:
        logger.info(f"Waiting for dak.opt at {dak_opt_path} not empty")
        time.sleep(1.0)

    dak_opt = pandas.read_csv(dak_opt_path)
    expected_dak_opt = pandas.read_csv(expected_dak_opt_path)
    logger.info(f"Dakota result: \n{dak_opt}")
    logger.info(f"Dakota expected result: \n{expected_dak_opt}")
    pandas.testing.assert_frame_equal(dak_opt, expected_dak_opt)


if __name__ == "__main__":
    main()
