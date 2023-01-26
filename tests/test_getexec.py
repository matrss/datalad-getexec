from __future__ import annotations

import tempfile
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional

import datalad.api as da
import datalad.distribution.dataset as ddd
import datalad.runner.exception
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
    dataset: ddd.Dataset
    content: bytes
    dependencies: Optional[List[FileRecord]] = None


class DatasetActions(hst.RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.files = []
        self.content_is_available = defaultdict(dict)

    # TODO: somehow test getexec in subdatasets
    datasets: hst.Bundle = hst.Bundle("datasets")
    files: hst.Bundle = hst.Bundle("files")

    @hst.initialize(target=datasets)
    def initial_dataset(self):
        dataset_path = tempfile.mkdtemp()
        dataset = ddd.Dataset(dataset_path)
        dataset.create()
        self.root_dataset = dataset
        return dataset

    def teardown(self):
        self.root_dataset.remove(reckless="kill")

    def _set_content_available(self, file):
        if not self.content_is_available.get(file.dataset, {}).get(file.content, False):
            self.content_is_available[file.dataset][file.content] = True
            if file.dependencies is not None:
                for e in file.dependencies:
                    self._set_content_available(e)

    @hst.rule(
        target=files,
        dataset=datasets,
        uuid=hs.uuids(version=4),
        content=hs.binary(),
        message=hs.one_of(hs.none(), hs.text()),
        depends_on=hs.lists(files),
    )
    def add_getexec_file(self, dataset, uuid, content, message, depends_on):
        filename = str(uuid)
        depends_on_filenames = list(
            map(
                str,
                map(
                    lambda x: (x.dataset.pathobj / x.name).relative_to(dataset.pathobj),
                    depends_on,
                ),
            )
        )
        cmd = [
            "bash",
            "-c",
            "printf 'output on stdout'; ({} printf '{}') > \"$1\"".format(
                "; ".join(list(map(lambda x: "cat " + x, depends_on_filenames)) + [""]),
                content,
            )
            if depends_on
            else "printf 'output on stdout'; printf '{}' > \"$1\"".format(content),
            "test",
        ]
        dataset.getexec(
            cmd,
            path=filename,
            inputs=depends_on_filenames if depends_on else None,
            message=message,
        )
        content = (dataset.pathobj / filename).read_bytes()
        file_record = FileRecord(
            filename, dataset, content, depends_on if depends_on else None
        )
        self.files.append(file_record)
        if file_record.dependencies is not None:
            for dependency in file_record.dependencies:
                self._set_content_available(dependency)
        self._set_content_available(file_record)
        return file_record

    @hst.rule(file=files)
    def drop_file(self, file: FileRecord):
        result = file.dataset.drop(file.name)
        if self.content_is_available[file.dataset][file.content]:
            assert result[0]["status"] == "ok"
            self.content_is_available[file.dataset][file.content] = False
        else:
            assert result[0]["status"] == "notneeded"

    @hst.rule(file=files)
    def get_file(self, file: FileRecord):
        result = file.dataset.get(file.name)
        if not self.content_is_available[file.dataset][file.content]:
            assert result[0]["status"] == "ok"
            self._set_content_available(file)
        else:
            assert result[0]["status"] == "notneeded"

    def _file_is_in_consistent_state(self, file):
        filepath = file.dataset.pathobj / file.name
        assert filepath.is_symlink(), "'{}' is expected to be a symlink".format(
            filepath
        )
        assert (
            filepath.exists() == self.content_is_available[file.dataset][file.content]
        ), "'{}' is expected to exist if and only if it's content '{}' is available".format(
            filepath, file.content
        )
        if self.content_is_available[file.dataset][file.content]:
            assert (
                filepath.read_bytes() == file.content
            ), "'{}' is expected to contain the content '{}'".format(
                filepath, file.content
            )

    @hst.invariant()
    def consistent_state(self):
        for e in self.files:
            self._file_is_in_consistent_state(e)


TestDatasetActions = DatasetActions.TestCase
