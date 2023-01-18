from __future__ import annotations

import shlex
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
            'printf "%s" "output on stdout"; printf "%s" "test" > "$1"',
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
    content: str
    dependencies: Optional[List[FileRecord]] = None


class DatasetActions(hst.RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.files = []
        self.content_is_available = defaultdict(dict)

        # TODO: somehow test getexec in subdatasets
        # dataset_paths = da.create_test_dataset(spec="0-2/0-2")
        dataset_paths = da.create_test_dataset(spec="")
        self.datasets = [ddd.Dataset(dataset_path) for dataset_path in dataset_paths]
        for dataset in self.datasets:
            dataset.create(force=True)
        self.root_dataset = self.datasets[0]

    files: hst.Bundle = hst.Bundle("files")

    def teardown(self):
        self.root_dataset.remove(reckless="kill")

    # NOTE: null byte intentionally removed, behaves weird
    @hst.rule(
        target=files,
        data=hs.data(),
        uuid=hs.uuids(version=4),
        content=hs.text(
            alphabet=hs.characters(
                blacklist_categories=("Cs",), blacklist_characters=["\0"]
            )
        ).map(lambda x: x.replace("\r\n", "\n").replace("\r", "\n")),
    )
    def add_getexec_file(self, data, uuid, content):
        dataset = data.draw(hs.sampled_from(self.datasets))
        filename = str(uuid)
        dataset.getexec(
            [
                "bash",
                "-c",
                "printf '%s' 'output on stdout'; printf '%s' {} > \"$1\"".format(
                    shlex.quote(content)
                ),
                "test",
            ],
            path=filename,
        )
        file_record = FileRecord(filename, dataset, content)
        self.files.append(file_record)
        self.content_is_available[dataset][content] = True
        return file_record

    @hst.rule(
        target=files,
        data=hs.data(),
        uuid=hs.uuids(version=4),
        content=hs.text(
            alphabet=hs.characters(
                blacklist_categories=("Cs",), blacklist_characters=["\0"]
            )
        ).map(lambda x: x.replace("\r\n", "\n").replace("\r", "\n")),
        depends_on=hs.lists(files, min_size=1),
    )
    def add_getexec_file_with_dependency(self, data, uuid, content, depends_on):
        dataset = data.draw(hs.sampled_from(self.datasets))
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
            "printf '%s' 'output on stdout'; ({} printf '%s' {}) > \"$1\"".format(
                "; ".join(list(map(lambda x: "cat " + x, depends_on_filenames)) + [""]),
                shlex.quote(content),
            ),
            "test",
        ]
        dataset.getexec(
            cmd,
            path=filename,
            inputs=depends_on_filenames,
        )
        content = (dataset.pathobj / filename).read_text()
        file_record = FileRecord(filename, dataset, content, depends_on)
        self.files.append(file_record)
        self.content_is_available[dataset][content] = True
        for e in depends_on:
            self.content_is_available[e.dataset][e.content]
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
            self.content_is_available[file.dataset][file.content] = True
            if file.dependencies is not None:
                for e in file.dependencies:
                    self.content_is_available[e.dataset][e.content] = True
        else:
            assert result[0]["status"] == "notneeded"

    @hst.invariant()
    def consistent_state(self):
        for e in self.files:
            filepath = e.dataset.pathobj / e.name
            assert filepath.is_symlink()
            assert filepath.exists() == self.content_is_available[e.dataset][e.content]
            if self.content_is_available[e.dataset][e.content]:
                assert filepath.read_text() == e.content


TestDatasetActions = DatasetActions.TestCase
