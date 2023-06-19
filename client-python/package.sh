#!/bin/bash

VERSION=$(git tag --points-at HEAD)
RELEASE="cgos-client-python-$VERSION"
WORKDIR="work/$RELEASE"

mkdir -p $WORKDIR
mkdir -p $WORKDIR/bin
cp src/*.py $WORKDIR/bin
mkdir $WORKDIR/doc
cp doc/*.html $WORKDIR/doc
cp readme.txt sample.cfg simple.cfg $WORKDIR
(
    cd work
    zip -r ${RELEASE}.zip $RELEASE
)
