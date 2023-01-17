import shlex
from collections import defaultdict
from contextlib import contextmanager

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
        self.files.append((filename, dataset, content))
        self.content_is_available[dataset][content] = True
        return (filename, dataset, content)

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
                    lambda x: (x[1].pathobj / x[0]).relative_to(dataset.pathobj),
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
        self.files.append((filename, dataset, content))
        self.content_is_available[dataset][content] = True
        return (filename, dataset, content)

    @hst.rule(file=files)
    def drop_file(self, file):
        filename, dataset, content = file
        result = dataset.drop(filename)
        if self.content_is_available[dataset][content]:
            assert result[0]["status"] == "ok"
            self.content_is_available[dataset][content] = False
        else:
            assert result[0]["status"] == "notneeded"

    @hst.rule(file=files)
    def get_file(self, file):
        filename, dataset, content = file
        result = dataset.get(filename)
        if not self.content_is_available[dataset][content]:
            assert result[0]["status"] == "ok"
            self.content_is_available[dataset][content] = True
        else:
            assert result[0]["status"] == "notneeded"

    @hst.invariant()
    def consistent_state(self):
        for filename, dataset, content in self.files:
            filepath = dataset.pathobj / filename
            assert filepath.is_symlink()
            assert filepath.exists() == self.content_is_available[dataset][content]
            if self.content_is_available[dataset][content]:
                assert filepath.read_text() == content


TestDatasetActions = DatasetActions.TestCase
