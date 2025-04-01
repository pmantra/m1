## Main Nginx Config testing TLS certificate/key.

This folder includes 3 files that are required for nginx to do runtime syntax checks/linting. They ARE NOT meant for production use.

 * `nginx.key`: private key for TLS setup
 * `nginx.crt`: TLS certificate for TLS setup
 * `dhparams.pem`: DH Params for TLS setup

To recreate these files, you could do the following:

```bash
$ cd nginx/test_tls
$ openssl req -x509 -subj "/C=US/ST=NY/L=New York/O=Maven Clinic Co./CN=*.mvnctl.net" -nodes -days 730 -newkey rsa:2048 -keyout ./nginx.key -out ./nginx.crt
$ openssl dhparam -out ./dhparams.pem 2048
```
