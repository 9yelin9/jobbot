#!/bin/bash

path='/home/9yelin9/jobbot'
today=`date +%y%m%d`
nohup python3 manage.py runserver > $path/log/manage_$today.log 2>&1 &
