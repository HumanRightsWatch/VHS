# How to deploy VHS on Azure
Here is a step-by-step guide explaining how to deploy VHS on Microsoft Azure.

This guide assumes the following:

* you already have a Linux virtual machine up and running within Azure
* you can access it with SSH
* Docker and docker-compose are installed on your VM
* you have basic knowledge in Linux command line and Docker

## Get the deployment package
Each time the code of VHS is updated, both the Docker image and the deployment package are automatically built.

To put the deployment package on your VM, on your computer:

* browse https://github.com/HumanRightsWatch/VHS/actions/workflows/ci.yml
* click on the latest successful build
* save the `deployment-package` listed in the *Artifacts* section on your computer
* copy it onto your VM using SSH - [a simple guide](https://www.ssh.com/academy/ssh/scp)

NB: due to GitHub limitation, we cannot provide a direct link to the latest version of the deployment package.

Once you have uploaded the deployment package on your VM, connect to your VM using SSH and unzip the package `unzip deployment-package.zip`. Now you should have, at least, the following files on your VM: 

```
.
├── azure.yml
├── compose
│   └── production
│       ├── postgres
│       │   ├── Dockerfile
│       │   └── maintenance
│       └── traefik
│           ├── Dockerfile
│           └── traefik.yml
├── deployment-package.zip
└── .env
```

## Configure VHS prior to its deployment
First, you have to adapt the file `.env` to your environment. To do so, edit it and set the value of the following variables:

* `DJANGO_SECRET_KEY`: a random string/password
* `DJANGO_ADMIN_URL`: a random string, the URI of the administration panel thar will be accessible at `https://{DJANGO_ALLOWED_HOSTS}/{DJANGO_ADMIN_URL}`
* `DJANGO_ALLOWED_HOSTS`: the domain name pointing to your VHS instance
* `MINIO_ACCESS_KEY`: a random string/password
* `MINIO_SECRET_KEY`: a random string/password
* `POSTGRES_USER`: a random string/password, the Postgres user dedicated to VHS
* `POSTGRES_PASSWORD`: a random string/password associated to the Postgres user
* `AZURE_TENANT`: the ID of the tenant your VHS instance authentication belongs to
* `ADMIN_PASSWORD`: a random password for the local administration account (username: `admin`)

Next, you have to configure the load balancer which will be the entrypoint from the Internet. To do so, edit the file `compose/production/traefik/traefik.yml` and set the value of:

* `22:       email: "<administrator's email>"`: administrator's email address used by Let's Encrypt to reach out
* `31:      rule: "Host(`<the domain name pointing to your VHS instance>`)"`: the same value as `DJANGO_ALLOWED_HOSTS` set in the previous step

Congrats! You have configured VHS.

## Deploy
The final step is starting the VHS stack, to do so simply run the following command:
```shell
docker-compose -f azure.yml up -d
```

After few seconds or minutes, VHS would be accessible at the domain you set before.

You can check the logs at any time by running the following command: 
```shell
docker-compose -f azure.yml logs
```

VHS will be automatically updated on a daily basis.

## Configure the SSO
At its first start, VHS creates an administrator user account with the password you specified earlier. First, connect to the administration panel by browsing `https://{DJANGO_ALLOWED_HOSTS}/{DJANGO_ADMIN_URL}` (username = `admin`). Next, click on *Social apps* > *Add a social app*, select *Microsoft Graph* in the provider list and fill the fields *Client ID* and *Secret key* with the information provided by your Azure administrator.
