---
categories: ["Developer"]
tags: ["install", "developer"]
title: "Testing"
linkTitle: "Testing"
date: 2021-12-16
description: >
  Quick Developer Guide
---

How to run the the unit/integration tests for OpenNSA

Make sure all the requirements are installed. Then:

```sh 
./util/pg-test-run      # This will start a Postgres in docker
PYTHONPATH=. trial test
```

Running the CI/CD pipeline locally:

1. Install the CLI tooling according to: https://docs.drone.io/quickstart/cli/

2. Run the pipeline by using `drone exec`.  Please ensure you have docker installed.
