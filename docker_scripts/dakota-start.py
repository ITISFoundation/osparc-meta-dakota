import contextlib
import http.server
import logging
import os
import pathlib as pl
import shutil
import socketserver
import sys
import threading
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

import tools.maps  # NOQA


NOISE_MUS = [0.0, 0.0]
NOISE_SIGMAS = [5.0, 10.0]

POLLING_TIME = 0.1
HTTP_PORT = 8888


def main():
    dakota_service = DakotaService()

    http_dir_path = pl.Path(__file__).parent / "http"

    class HTTPHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(
                *args, **kwargs, directory=http_dir_path.resolve()
            )

    try:
        logger.info(
            f"Starting http server at port {HTTP_PORT} and serving path {http_dir_path}"
        )
        with socketserver.TCPServer(("", HTTP_PORT), HTTPHandler) as httpd:
            httpd_thread = threading.Thread(target=httpd.serve_forever)
            httpd_thread.start()
            dakota_service.start()
            httpd.shutdown()
    except Exception as err:  # pylint: disable=broad-except
        logger.error(f"{err} . Stopping %s", exc_info=True)


class DakotaService:
    def __init__(self):
        self.uuid = uuid.uuid4()
        self.caller_uuid = None
        self.map_uuid = None

        self.input_dir_path = pl.Path(os.environ["DY_SIDECAR_PATH_INPUTS"])
        self.input0_dir_path = self.input_dir_path / "input_0"
        self.input1_dir_path = self.input_dir_path / "input_1"

        self.output_dir_path = pl.Path(os.environ["DY_SIDECAR_PATH_OUTPUTS"])
        self.output0_dir_path = self.output_dir_path / "output_0"
        self.output1_dir_path = self.output_dir_path / "output_1"

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
        self.map_object = tools.maps.oSparcFileMap(
            self.map_reply_file_path.resolve(),
            self.map_caller_file_path.resolve(),
        )

        self.caller_uuid = self.caller_handshaker.shake()

        while not self.dakota_conf_path.exists():
            time.sleep(POLLING_TIME)
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

        self.start_dakota(dakota_conf, self.output0_dir_path)

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


if __name__ == "__main__":
    main()
