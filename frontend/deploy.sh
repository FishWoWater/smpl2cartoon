#!/bin/bash

rm -r dist

sudo rm -r /var/www/html/smpl2cartoon

npm run build 

sudo cp -r dist /var/www/html/smpl2cartoon
