# Makefile for various small tasks
# NOT used for building
.PHONY: clean

clean:
	rm -fr _trial_temp
	find . -name "*.pyc"|xargs rm

