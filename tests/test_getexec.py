from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import datalad.api as da
import datalad.distribution.dataset as ddd
import datalad.runner.exception
import hypothesis as h
import hypothesis.stateful as hst
import hypothesis.strategies as hs
import pytest

import datalad_getexec.remote


@pytest.fixture()
def dataset() -> Iterator[ddd.Dataset]:
    with generate_datasets() as datasets:
        yield datasets[0]


@contextmanager
def generate_datasets(spec="") -> Iterator[List[ddd.Dataset]]:
    try:
        paths = da.create_test_dataset(spec=spec)
        datasets = [ddd.Dataset(path) for path in paths]
        for dataset in datasets:
            dataset.create(force=True)
        yield datasets
    finally:
        # cleanup
        # datasets[0].remove(reckless="kill")
        pass


def test_remote_is_initialized(dataset: ddd.Dataset) -> None:
    dataset.getexec(
        [
            "bash",
            "-c",
            'printf "output on stdout"; printf "test" > "$1"',
            "test",
        ],
        path="test.txt",
    )
    sibling_uuids = map(lambda x: x["annex-uuid"], dataset.siblings())
    assert datalad_getexec.remote.GETEXEC_REMOTE_UUID in sibling_uuids


def test_invalid_command_raises_remote_error(dataset: ddd.Dataset) -> None:
    with pytest.raises(datalad.runner.exception.CommandError):
        dataset.getexec(["false"], path="test.txt")


def test_getexec_with_subdataset_gets_input(dataset: ddd.Dataset) -> None:
    subds = ddd.Dataset(dataset.pathobj / "subds")
    subds.create()
    dataset.save()
    subds.getexec(
        [
            "bash",
            "-c",
            'printf "output on stdout"; printf "test\n" > "$1"',
            "test",
        ],
        path="test.txt",
    )
    dataset.save()
    subds.drop("test.txt")
    assert not (subds.pathobj / "test.txt").exists(), "Dropping a file in the sub-dataset failed"
    dataset.getexec(
        [
            "bash",
            "-c",
            'printf "output on stdout"; cat subds/test.txt > "$1"; printf "some more\n" >> "$1"',
            "test",
        ],
        inputs=["subds/test.txt"],
        path="dependent.txt",
    )
    assert (subds.pathobj / "test.txt").exists(), "A file in the sub-dataset was not recreated"
    assert (dataset.pathobj / "dependent.txt").read_text() == "test\nsome more\n"


@dataclass
class FileRecord:
    name: str
    content: ContentRecord


@dataclass
class ContentRecord:
    content: bytes
    dataset: ddd.Dataset
    dependencies: Optional[List[FileRecord]] = None
    is_available: bool = True


class DatasetActions(hst.RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._files: List[FileRecord] = []
        self._content_records: Dict[ddd.Dataset, Dict[bytes, ContentRecord]] = {}

    # TODO: somehow test getexec in subdatasets
    datasets: hst.Bundle = hst.Bundle("datasets")
    files: hst.Bundle = hst.Bundle("files")

    @hst.initialize(target=datasets)
    def initial_dataset(self) -> ddd.Dataset:
        dataset_path = tempfile.mkdtemp()
        dataset = ddd.Dataset(dataset_path)
        dataset.create()
        self.root_dataset = dataset
        self._content_records[dataset] = {}
        return dataset

    def teardown(self) -> None:
        self.root_dataset.remove(reckless="kill")

    def _set_content_available(self, content_record: ContentRecord) -> None:
        if not content_record.is_available:
            content_record.is_available = True
            if content_record.dependencies is not None:
                for dependency in content_record.dependencies:
                    self._set_content_available(dependency.content)

    @hst.rule(
        target=files,
        dataset=datasets,
        depends_on=hs.lists(files),
        filename=hs.uuids(version=4).map(lambda x: str(x)),
        content=hs.binary(),
        message=hs.one_of(hs.none(), hs.text()),
    )
    def add_getexec_file(
        self,
        dataset: ddd.Dataset,
        depends_on: List[FileRecord],
        filename: str,
        content: bytes,
        message: Optional[str],
    ) -> FileRecord:
        h.assume(content not in self._content_records[dataset].keys())
        if isinstance(message, str):
            h.assume("\0" not in message)
        depends_on_filenames = list(
            map(
                str,
                map(
                    lambda x: (x.content.dataset.pathobj / x.name).relative_to(
                        dataset.pathobj
                    ),
                    depends_on,
                ),
            )
        )
        write_bytes_path = Path(__file__).parent / "resources/write_bytes.py"
        cmd = [str(write_bytes_path), repr(content)]
        dataset.getexec(
            cmd,
            path=filename,
            inputs=depends_on_filenames if depends_on else None,
            message=message,
        )
        content = (dataset.pathobj / filename).read_bytes()
        content_record = self._content_records.get(dataset, {}).get(
            content, ContentRecord(content, dataset, depends_on or None)
        )
        self._content_records[dataset][content] = content_record
        file_record = FileRecord(filename, content_record)
        self._files.append(file_record)
        for dependency in depends_on:
            self._set_content_available(dependency.content)
        self._content_records[dataset][content].is_available = True
        return file_record

    @hst.rule(file=files)
    def drop_file(self, file: FileRecord) -> None:
        result = file.content.dataset.drop(file.name)
        if file.content.is_available:
            assert result[0]["status"] == "ok"
            file.content.is_available = False
        else:
            assert result[0]["status"] == "notneeded"

    @hst.rule(file=files)
    def get_file(self, file: FileRecord) -> None:
        result = file.content.dataset.get(file.name)
        if not file.content.is_available:
            assert result[0]["status"] == "ok"
            self._set_content_available(file.content)
        else:
            assert result[0]["status"] == "notneeded"

    def _file_is_in_consistent_state(self, file: FileRecord) -> None:
        filepath = file.content.dataset.pathobj / file.name
        assert filepath.is_symlink(), "'{}' is expected to be a symlink".format(
            filepath
        )
        assert (
            filepath.exists() == file.content.is_available
        ), "'{}' is expected to exist if and only if it's content '{}' is available".format(
            filepath, file.content
        )
        if file.content.is_available:
            assert (
                filepath.read_bytes() == file.content.content
            ), "'{}' is expected to contain the content '{}'".format(
                filepath, file.content
            )

    @hst.invariant()
    def consistent_state(self) -> None:
        for e in self._files:
            self._file_is_in_consistent_state(e)


TestDatasetActions = DatasetActions.TestCase
