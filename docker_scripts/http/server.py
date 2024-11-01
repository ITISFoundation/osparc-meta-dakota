import http.server
import logging
import pathlib as pl
import socketserver
import threading

logging.basicConfig(
    level=logging.INFO, format="[%(filename)s:%(lineno)d] %(message)s"
)
logger = logging.getLogger(__name__)

HTTP_PORT = 8888


def main():
    http_dir_path = pl.Path(__file__).parent

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
            httpd.serve_forever()
    except Exception as err:  # pylint: disable=broad-except
        logger.error(f"{err} . Stopping %s", exc_info=True)


if __name__ == "__main__":
    main()
