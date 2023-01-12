from collections import defaultdict
from contextlib import contextmanager

import datalad.api as da
import datalad.distribution.dataset as ddd
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
    dataset.getexec(["bash", "-c", 'echo -n -e "test" > "$1"', "test"], path="test.txt")
    sibling_uuids = map(lambda x: x["annex-uuid"], dataset.siblings())
    assert datalad_getexec.remote.GETEXEC_REMOTE_UUID in sibling_uuids


class DatasetActions(hst.RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.files = []
        self.content_is_available = defaultdict(dict)

        dataset_paths = da.create_test_dataset(spec="0-2/0-2")
        self.datasets = [ddd.Dataset(dataset_path) for dataset_path in dataset_paths]
        for dataset in self.datasets:
            dataset.create(force=True)
        self.root_dataset = self.datasets[0]

    files: hst.Bundle = hst.Bundle("files")

    def teardown(self):
        self.root_dataset.remove(reckless="kill")

    # NOTE: null byte removed for now, behaves weird
    # NOTE: CR removed for now, since git normalizes to LF and the content equality does
    # not hold
    # NOTE: single-quote has issues because of the quoting in the echo command
    @hst.rule(
        target=files,
        data=hs.data(),
        uuid=hs.uuids(version=4),
        content=hs.text(
            alphabet=hs.characters(
                blacklist_categories=("Cs",), blacklist_characters=["\0", "\r", "'"]
            )
        ),
    )
    def add_getexec_file(self, data, uuid, content):
        dataset = data.draw(hs.sampled_from(self.datasets))
        filename = str(uuid)
        dataset.getexec(
            ["bash", "-c", "echo -n -e '{}' > \"$1\"".format(content), "test"],
            path=filename,
        )
        self.files.append((filename, dataset, content))
        self.content_is_available[dataset][content] = True
        return (filename, dataset, content)

    @hst.rule(file=files)
    def drop_file(self, file):
        filename, dataset, content = file
        dataset.drop(filename)
        self.content_is_available[dataset][content] = False

    @hst.rule(file=files)
    def get_file(self, file):
        filename, dataset, content = file
        dataset.get(filename)
        self.content_is_available[dataset][content] = True

    @hst.invariant()
    def consistent_state(self):
        for filename, dataset, content in self.files:
            filepath = dataset.pathobj / filename
            assert filepath.is_symlink()
            assert filepath.exists() == self.content_is_available[dataset][content]
            if self.content_is_available[dataset][content]:
                assert filepath.read_text() == content


TestDatasetActions = DatasetActions.TestCase
