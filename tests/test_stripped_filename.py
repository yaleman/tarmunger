""" tests something """


from pathlib import Path
import tarfile

import pytest

from tarmunger import AlltheData

def test_stripped_filename_targz(tmpdir: pytest.TempdirFactory) -> None:
    """ tests a tar.gz file """
    testfile = Path(str(tmpdir)).with_name("testfile.tar.gz")
    with tarfile.open(str(testfile), 'w|gz') as test_tar:
        test_tar.addfile(
            tarfile.TarInfo(name='foo'),
            Path("pyproject.toml").open('rb'),
            )
    print(testfile)
    testclass = AlltheData(filepath=testfile)
    assert testclass.get_stripped_filename() == testfile.with_name("testfile-stripped.tar.gz")

def test_stripped_filename_tar(tmpdir: pytest.TempdirFactory) -> None:
    """ tests a tar file """
    testfile = Path(str(tmpdir)).with_name("testfile.tar")
    with tarfile.open(testfile, 'w') as test_tar:
        test_tar.addfile(
            tarfile.TarInfo(name='foo'),
            Path("pyproject.toml").open('rb'),
            )
    print(testfile)
    testclass = AlltheData(filepath=testfile)
    assert testclass.get_stripped_filename() == testfile.with_name("testfile-stripped.tar")
