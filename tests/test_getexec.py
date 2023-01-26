from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import datalad.api as da
import datalad.distribution.dataset as ddd
import datalad.runner.exception
import hypothesis as h
import hypothesis.stateful as hst
import hypothesis.strategies as hs
import pytest

import datalad_getexec.remote


@pytest.fixture()
def dataset():
    with generate_dataset() as dataset:
        yield dataset


@contextmanager
def generate_dataset():
    try:
        path = da.create_test_dataset(spec="")[0]
        ds = ddd.Dataset(path)
        ds.create(force=True)
        yield ds
    finally:
        # cleanup
        ds.remove(reckless="kill")


def test_remote_is_initialized(dataset):
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


def test_invalid_command_raises_remote_error(dataset):
    with pytest.raises(datalad.runner.exception.CommandError):
        dataset.getexec(["false"], path="test.txt")


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
    def __init__(self):
        super().__init__()
        self.files = []
        self.content_records = {}

    # TODO: somehow test getexec in subdatasets
    datasets: hst.Bundle = hst.Bundle("datasets")
    files: hst.Bundle = hst.Bundle("files")

    @hst.initialize(target=datasets)
    def initial_dataset(self):
        dataset_path = tempfile.mkdtemp()
        dataset = ddd.Dataset(dataset_path)
        dataset.create()
        self.root_dataset = dataset
        self.content_records[dataset] = {}
        return dataset

    def teardown(self):
        self.root_dataset.remove(reckless="kill")

    def _set_content_available(self, content_record):
        if not content_record.is_available:
            content_record.is_available = True
            if content_record.dependencies is not None:
                for dependency in content_record.dependencies:
                    self._set_content_available(dependency.content)

    @hst.rule(
        target=files,
        dataset=datasets,
        uuid=hs.uuids(version=4),
        content=hs.binary(),
        message=hs.one_of(hs.none(), hs.text()),
        depends_on=hs.lists(files),
    )
    def add_getexec_file(self, dataset, uuid, content, message, depends_on):
        if isinstance(message, str):
            h.assume("\0" not in message)
        filename = str(uuid)
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
        content_record = self.content_records.get(dataset, {}).get(
            content, ContentRecord(content, dataset, depends_on or None)
        )
        self.content_records[dataset][content] = content_record
        file_record = FileRecord(filename, content_record)
        self.files.append(file_record)
        if content_record.dependencies is not None:
            for dependency in content_record.dependencies:
                self._set_content_available(dependency.content)
        self._set_content_available(content_record)
        return file_record

    @hst.rule(file=files)
    def drop_file(self, file: FileRecord):
        result = file.content.dataset.drop(file.name)
        if file.content.is_available:
            assert result[0]["status"] == "ok"
            file.content.is_available = False
        else:
            assert result[0]["status"] == "notneeded"

    @hst.rule(file=files)
    def get_file(self, file: FileRecord):
        result = file.content.dataset.get(file.name)
        if not file.content.is_available:
            assert result[0]["status"] == "ok"
            self._set_content_available(file)
        else:
            assert result[0]["status"] == "notneeded"

    def _file_is_in_consistent_state(self, file: FileRecord):
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
    def consistent_state(self):
        for e in self.files:
            self._file_is_in_consistent_state(e)


TestDatasetActions = DatasetActions.TestCase
