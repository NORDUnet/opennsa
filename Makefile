# Makefile for various small tasks
# NOT used for building
.PHONY: clean docker-build

clean:
	rm -fr _trial_temp
	find . -name "*.pyc"|xargs rm

docker-build:
	docker build -t opennsa --squash docker

