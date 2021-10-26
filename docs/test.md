How to run the the unit/integration tests for OpenNSA

Make sure all the requirements are installed. Then:

```sh 
./util/pg-test-run      # This will start a Postgres in docker
PYTHONPATH=. trial test
```
