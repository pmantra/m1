## Looker Installation Notes

- Prepare a VM node that meets the looker on-premise install [system requirements](https://docs.looker.com/setup-and-management/on-prem-install/installation).
- Our dockerized Looker instance setup is based on the work here: https://github.com/alexhudson/looker-docker
- Looker instances is running on a single GCE node (n1-highmem-2, 2vCPU, 13GB memory) with pod label `name: looker`
- It has a persistent disk attached, where all Looker configurations, models and the actual application jar file are stored.

## Looker Version Upgrade

Current looker version `6.22.12` as of Oct 30, 2019.

- Before upgrade Looker jar file, do a Disk Snapshot for the `looker-data` persistent disk on GCP, label it with date info.
- Looker application releases monthly. The Extended Support Release are released quarterly.
- The application is a single jar file that can be downloaded from 
[Looker's site](https://docs.looker.com/setup-and-management/on-prem-install/download-looker-jar) 
either via browser or via API with license number and account registration email. 
A successful response will contain both the HMAC S3 URL of the intended Looker jar file and an MD5 hash of the jar file. 
- Verify the downloaded jar file with the MD5 hash checksum provided on the download web/api interface.
- Copy the jar file into the pod's looker WORKPATH, which is `/home/looker/looker`
- Swap out the jar file and kill the pod to restart looker instance
- If the pod comes back up running, the upgrade process is done.

References:

- https://docs.looker.com/setup-and-management/on-prem-install/installation
- https://docs.looker.com/setup-and-management/on-prem-mgmt/upgrade
