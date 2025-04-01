# [`data-admin`](/api/data_admin/)

Data admin is a python web application that allows Maven workers to control the state of the backend in which the service is running. It is supposed to enable clients to do things that are not possible in production such as resetting the database or creating test data.

## Deployment

At the moment, data admin must be manually deployed to QA environments by updating the deployment image tag to the desired commit hash.

## Authentication

Data admin expects all authentiation to occur at the network layer, and makes no attempt to prove the legitimacy of incoming requests. When deployed locally, requests can only be made from the host machine. On QA, we rely on a google oauth proxy to make sure that only Maven workers have access to the service.
