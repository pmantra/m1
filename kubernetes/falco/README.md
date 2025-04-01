## Falco Setup in Kubernetes Cluster

Falco is being deployed as a k8s daemonSet to our GKE cluster on each cluster nodes. To setup, we will need to create and configure role based access control(RBAC) first.
To bootstrap RBAC setup below, you will need to create a ClusterRoleBinding between oneself and the ClusterAdmin group. e.g.

```bash
$ cd ../../falco
$ kubectl create configmap falco-config --from-file=./falco.yaml --from-file=./rules  # create the configmaps from top level falco folder
$ cd -
$ kubectl create clusterrolebinding "${USER}-cluster-admin" --clusterrole=cluster-admin --user=$(gcloud config get-value account)  # bootstrapping my own clusterole to create service accounts
$ kubectl create -f falco-rbac.yaml  # create the necessary credentials for falco setup
$ kubectl create -f falco-svc.yaml  # create falco service for falco embedded webserver to accept k8s audit events, optional.
$ kubectl create -f falco-daemonset.yaml  # create falco daemonset
$ kubectl get po -l app=maven-falco  # verify that all falco pods have been created - it may take a few minutes, the number of falco pods should match the number of nodes.
```
