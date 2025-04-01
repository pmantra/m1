import csv
import io
from typing import IO, Iterable

import chardet

from utils.log import logger

log = logger(__name__)


def decode_data(data: io.BytesIO) -> io.TextIOWrapper:
    data.seek(0)
    detector = chardet.UniversalDetector()
    for line in data:
        detector.feed(line)
        if detector.done:
            break
    detector.close()
    data.seek(0)
    return io.TextIOWrapper(data, encoding=detector.result["encoding"])


def _stream(*lines: str) -> io.BytesIO:
    stream = io.BytesIO()
    stream.writelines(lines)  # type: ignore[arg-type] # Argument 1 to "writelines" of "IOBase" has incompatible type "Tuple[str, ...]"; expected "Iterable[Buffer]"
    stream.seek(0)
    return stream


def split_csv(file_obj: IO, max_lines: int = 10_000) -> Iterable[IO]:
    file_obj.seek(0)
    headers = file_obj.readline()
    if isinstance(headers, bytes):
        headers = b",".join(h.strip() for h in headers.split(b",")) + b"\n"
    else:
        headers = ",".join(h.strip() for h in headers.split(",")) + "\n"
    files = 0
    out_lines = []
    for row in file_obj:
        if len(out_lines) == max_lines:
            files += 1
            yield _stream(headers, *out_lines)
            out_lines = []

        out_lines.append(row)
    if out_lines:
        files += 1
        yield _stream(headers, *out_lines)

    log.info("CSV split", max_lines=max_lines, chunk_count=files)


def dict_to_csv(dicts: list[dict]) -> io.BytesIO:
    """Util function to convert a list of dicts (same schema) to a BytesIO in-mem rep of CSV"""
    if not len(dicts):
        return io.BytesIO()

    fp = io.StringIO()
    fieldnames = list(dicts[0].keys())
    writer = csv.DictWriter(f=fp, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rowdicts=dicts)

    byte_buffer = io.BytesIO(fp.getvalue().encode("utf-8"))
    return byte_buffer
