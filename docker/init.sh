#!/bin/bash

rsa_key_size=4096
data_path="./docker/nginx"

echo "### Creating self signed certificate for $domain ..."
mkdir -p "$data_path/ssl"
out="$data_path/ssl"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout $out/private.key -out $out/certificate.crt
