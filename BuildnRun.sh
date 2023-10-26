# OpenCo Cocom Build 'n' Run Script
#!/bin/bash
# Version 1.0.2

# This simple script builds and runs this directory 's Dockerfile Image
# It also docker tags it based on its git PROJECT BRANCH and TAG , this is useful for pushing to the cocom internal repo when logged into the OpenCo VPN
PROJECTPATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    PROJECT=${PROJECTPATH##*/}
FULL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
# Lowecase the branch
FULL_BRANCH=`echo $FULL_BRANCH|awk '{print tolower($0)}'`
     BRANCH=${FULL_BRANCH##*/}
        TAG=$(git describe --always --tag --abbrev=0)

echo PROJECTPATH=$PROJECTPATH
echo     PROJECT=$PROJECT
echo FULL_BRANCH=$FULL_BRANCH
echo      BRANCH=$BRANCH

echo docker build -t openco/$PROJECT-$BRANCH:$TAG .
echo docker tag -f openco/$PROJECT-$BRANCH:$TAG
echo   openco/$PROJECT-$BRANCH:latest
docker build -t openco/$PROJECT:$BRANCH-$TAG . \
  && \
docker tag openco/$PROJECT:$BRANCH-$TAG \
 openco/$PROJECT:$BRANCH-latest \
  && \
docker tag openco/$PROJECT:$BRANCH-$TAG \
 openco/$PROJECT:$TAG \
  && \
docker tag openco/$PROJECT:$BRANCH-$TAG \
 openco/$PROJECT:latest \
  && \
  ./docker_run.sh
