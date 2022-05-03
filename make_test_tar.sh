#!/bin/bash

# make_testtar

rm -rf ./testdir/
mkdir -p ./testdir
touch testdir/testfile{1,2,3,4,5,6,7}.txt
tar czvf testfile.tar.gz ./testdir/
rm -rf testdir/
echo "Done!"