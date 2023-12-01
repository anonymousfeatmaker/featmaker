# FeatMaker

FeatMaker automatically generates state features & search strategy for symbolic execution.

## Installation
We recommend to use a [docker file](Dockerfile) for easy and fast installation. To install FeatMaker on local, please follow the instructions on [docker file](Dockerfile)
```bash
$ docker build -t featmaker .
$ docker run -it --ulimit='stack=-1:-1' featmaker
```

## How to run FeatMaker
There are two 
