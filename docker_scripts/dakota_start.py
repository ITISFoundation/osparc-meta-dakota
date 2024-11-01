import contextlib
import logging
import multiprocessing
import os
import pathlib as pl
import shutil
import sys
import time
import uuid

import dakota.environment as dakenv
from osparc_filecomms import handshakers

logging.basicConfig(
    level=logging.INFO, format="[%(filename)s:%(lineno)d] %(message)s"
)
logger = logging.getLogger(__name__)

sys.path.append(str((pl.Path(__file__) / "tools").resolve().parent))
print(
    "Added to python search python: "
    f"{str(pl.Path(__file__).resolve().parent)}"
)

import map.maps  # NOQA


class DakotaService:
    def __init__(self, settings):
        self.settings = settings
        self.uuid = uuid.uuid4()
        self.caller_uuid = None
        self.map_uuid = None

        self.input0_dir_path = self.settings.input_path / "input_0"
        self.input1_dir_path = self.settings.input_path / "input_1"

        self.output0_dir_path = self.settings.output_path / "output_0"
        self.output1_dir_path = self.settings.output_path / "output_1"

        self.dakota_conf_path = self.input0_dir_path / "dakota.in"

        self.map_caller_file_path = self.output1_dir_path / "input_tasks.json"
        self.map_reply_file_path = self.input1_dir_path / "output_tasks.json"

        self.caller_handshaker = handshakers.FileHandshaker(
            self.uuid,
            self.input0_dir_path,
            self.output0_dir_path,
            is_initiator=True,
        )

        if self.output0_dir_path.exists():
            self.clean_output(self.output0_dir_path)

    def clean_output(self, dir_path):
        for item in dir_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    def start(self):
        self.map_object = map.maps.oSparcFileMap(
            self.map_reply_file_path.resolve(),
            self.map_caller_file_path.resolve(),
        )

        self.caller_uuid = self.caller_handshaker.shake()

        while not self.dakota_conf_path.exists():
            time.sleep(self.settings.file_polling_interval)
        dakota_conf = self.dakota_conf_path.read_text()

        clear_directory(
            self.output0_dir_path,
        )

        shutil.copytree(
            self.input0_dir_path,
            self.output0_dir_path,
            ignore=shutil.ignore_patterns("handshake.json"),
            dirs_exist_ok=True,
        )

        first_error_time = None

        while True:
            try:
                process = multiprocessing.Process(
                    target=self.start_dakota,
                    args=(dakota_conf, self.output0_dir_path),
                )
                process.start()
                process.join()
                logging.info(f"PROCESS ended with exitcode {process.exitcode}")
                if process.exitcode != 0:
                    raise RuntimeError("Dakota subprocess failed")
                break
            except RuntimeError as error:
                if not self.settings.restart_on_error:
                    raise error
                if first_error_time is None:
                    first_error_time = time.time()
                if (
                    time.time() - first_error_time
                    >= self.settings.restart_on_error_max_time
                ):
                    logging.info(
                        "Received a RunTimeError from Dakota, "
                        "max retry time reached, raising error"
                    )
                    raise error
                else:
                    logging.info(
                        f"Received a RunTimeError from Dakota ({error}), "
                        "retrying ..."
                    )
                    time.sleep(self.settings.restart_on_error_polling_interval)
                    max_wait_time = self.settings.restart_on_error_max_time - (
                        time.time() - first_error_time
                    )
                    logging.info(
                        f"Will wait for a maximum of {max_wait_time} "
                        "seconds for a change in dakota conf file..."
                    )
                    dakota_conf = self.wait_for_dakota_conf_change(
                        dakota_conf, max_wait_time
                    )
                    logging.info("Change in dakota conf file detected")
                    continue

    def wait_for_dakota_conf_change(self, old_dakota_conf, max_wait_time):
        new_dakota_conf = None
        start_time = time.time()
        while new_dakota_conf is None or new_dakota_conf == old_dakota_conf:
            if time.time() - start_time > max_wait_time:
                raise TimeoutError("Waiting too long for new dakota.conf")
            new_dakota_conf = self.dakota_conf_path.read_text()
            time.sleep(self.settings.file_polling_interval)
        return new_dakota_conf

    def model_callback(self, dak_inputs):
        param_sets = [
            {
                **{
                    label: value
                    for label, value in zip(
                        dak_input["cv_labels"], dak_input["cv"]
                    )
                },
                **{
                    label: value
                    for label, value in zip(
                        dak_input["div_labels"], dak_input["div"]
                    )
                },
            }
            for dak_input in dak_inputs
        ]
        all_response_labels = [
            dak_input["function_labels"] for dak_input in dak_inputs
        ]
        obj_sets = self.map_object.evaluate(param_sets)
        dak_outputs = [
            {
                "fns": [
                    obj_set[response_label]
                    for response_label in response_labels
                ]
            }
            for obj_set, response_labels in zip(obj_sets, all_response_labels)
        ]
        return dak_outputs

    def start_dakota(self, dakota_conf, output_dir):
        dakota_restart_path = output_dir / "dakota.rst"
        with working_directory(output_dir):
            callbacks = {"model": self.model_callback}
            study = dakenv.study(
                callbacks=callbacks,
                input_string=dakota_conf,
                read_restart=str(dakota_restart_path)
                if dakota_restart_path.exists()
                else "",
            )
            study.execute()


@contextlib.contextmanager
def working_directory(path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = pl.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def clear_directory(path):
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.unlink(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
