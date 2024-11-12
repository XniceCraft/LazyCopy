"""
Lazy file copy
"""

# pylint: disable=logging-fstring-interpolation
import argparse
import logging
import os
import sys
import time
from typing import Optional
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("Copy")


def is_binary(file_path: str) -> bool:
    """Check if the file is binary

    Parameters
    ----------
    file_path : str
        Path to the file

    Returns
    -------
    bool
        True if file is binary
    """
    try:
        with open(file_path, "r", encoding="utf-8") as fp:
            fp.read(16)
            return False
    except UnicodeDecodeError:
        return True


class Worker:
    """
    File copy worker
    """

    def __init__(self, chunk_size: int = 4 * 1024):
        self._bar: Optional[tqdm] = None
        self._curr_path: str = None
        self.chunk_size = chunk_size

    def init_bar(self):
        """Initialize progress bar"""
        file_size = os.path.getsize(self._curr_path)
        self._bar = tqdm(
            total=file_size,
            unit="B",
            unit_scale=True,
            desc=f"{os.path.basename(self._curr_path)}",
        )

    def close_bar(self):
        """
        Close progress bar
        """
        if self._bar:
            self._bar.close()
            self._bar = None

    def link_file(self, src: str, dest: str):
        """Do a symlink

        Parameters
        ----------
        src : str
            Source
        dest : str
            Destination
        """
        try:
            os.symlink(src, dest)
            logger.error(f"Success linking {src} to {dest}\n")
        except OSError:
            logger.error(f"Failed to link {src} to {dest}\n")

    def copy_file(self, src: str, dest: str):
        """Copy the file

        Parameters
        ----------
        src : str
            Source file
        dest : str
            Destination
        """
        if os.path.exists(dest):
            while True:
                print(
                    f"Duplicate file found at {dest} - Overwrite (O), Skip (S), Exit (E)?"
                )
                resp = input("> ")

                resp = resp.lower()
                if resp == "s":
                    return
                if resp == "e":
                    sys.exit(1)
                if resp == "o":
                    break

        self._curr_path = src
        self.init_bar()
        check_is_binary = is_binary(src)

        try:
            with open(  # pylint: disable=unspecified-encoding
                src, "rb" if check_is_binary else "r", encoding=None
            ) as src_file, open(  # pylint: disable=unspecified-encoding
                dest, "wb" if check_is_binary else "w", encoding=None
            ) as target_file:
                while buffer := src_file.read(self.chunk_size):
                    start = time.time()
                    target_file.write(buffer)
                    latency = (time.time() - start) * 1000

                    self._bar.update(len(buffer))
                    self._bar.set_description(
                        f"{os.path.basename(self._curr_path)} - {latency:.2f} ms"
                    )

            self.close_bar()
            logger.info(f"Success copying {src} to {dest}\n")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.close_bar()
            logger.error(f"Error copying {src} to {dest}: {e}\n")

    def run(self, src_path: str, dest_path: str) -> None:
        """Run the copy program

        Parameters
        ----------
        src_path : str
            Source path
        dest_path : str
            Destination path
        """
        if os.path.islink(src_path):
            if os.path.isdir(dest_path):
                dest_path = os.path.join(dest_path, os.path.basename(src_path))
            self.link_file(src_path, dest_path)
            return

        if os.path.isfile(src_path):
            if os.path.isdir(dest_path):
                dest_path = os.path.join(dest_path, os.path.basename(src_path))
            self.copy_file(src_path, dest_path)
            return

        for item in os.scandir(src_path):
            src = item.path
            target = os.path.join(dest_path, item.name)

            if item.is_symlink():
                self.link_file(src, target)
                continue
            if item.is_file():
                self.copy_file(src, target)
                continue
            if item.is_dir():
                os.makedirs(target, exist_ok=True)
                self.run(src, target)
                continue


def main():
    """
    Program entry point
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chunk-size",
        metavar="size",
        help="How large the buffer (bytes)",
        default=4096,
        type=int,
    )
    parser.add_argument(
        "--max-latency",
        metavar="ms",
        help="How many ms for max write latency",
        default=100,
        type=int,
    )
    parser.add_argument(
        "--priority",
        metavar="type",
        help="What you would prioritize?",
        default="latency",
        const="latency",
        nargs="?",
        choices = ["latency", "chunksize"]
    )
    parser.add_argument("source", metavar="src", help="Source file or dir")
    parser.add_argument("destination", metavar="dest", help="Destination dir or file name")
    args = parser.parse_args()

    if not os.path.splitext(os.path.basename(args.destination))[1] and not os.path.isdir(
        args.destination
    ):
        os.mkdir(args.destination)

    logger.info(f"Starting file copy from {args.source} to {args.destination}")
    worker = Worker(args.chunk_size)
    try:
        worker.run(args.source, args.destination)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    logger.info("File copy operation finished")


main()
