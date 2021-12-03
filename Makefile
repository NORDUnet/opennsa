# Makefile for various small tasks
# NOT used for building
.PHONY: clean docker-build

clean:
	rm -fr _trial_temp
	find . -name "*.pyc" -exec rm -v {} \; 

down:
	docker-compose down

docker-build: clean down
	docker-compose build  --no-cache

