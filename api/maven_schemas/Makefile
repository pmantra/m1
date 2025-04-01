SHELL := bash

# Make sure you've symlinked `maven-schemas/eligibility.proto` from the repo's directory into this one.
# ln -s ../../../maven-schemas/eligibility.proto /path/to/maven/api/maven_schemas/ 
# 
# Run the makefile from the api directory:
# cd ./api
# make -f maven_schemas/Makefile
#
# This is to ensure that the command correctly generates the import paths in `eligibility_pb2_grpc.py` file

.PHONY=python
python:
	python -m grpc_tools.protoc -I. \
		--python_out=. \
		--grpc_python_out=. \
		$(shell find ./maven_schemas -iname "*.proto")

all: python
