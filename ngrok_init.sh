#!/bin/bash

path='/home/9yelin9/jobbot'
today=`date +%y%m%d`
nohup ngrok http 8000 --log=stdout > $path/log/ngrok_$today.log 2>&1 &
